#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import unicodedata
import warnings
import gzip
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

warnings.filterwarnings("ignore", message=r"urllib3 v2 only supports OpenSSL 1\.1\.1\+.*")

import requests
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parent.parent
L20_DIR = Path(__file__).resolve().parent
load_dotenv(REPO_ROOT / ".env")

VERIFY_URL = "https://hub.ag3nts.org/verify"
TASK_NAME = "foodwarehouse"
FOOD_URL = "https://hub.ag3nts.org/dane/food4cities.json"

FOOD_FILE = L20_DIR / "food4cities.json"
HELP_FILE = L20_DIR / "help_response.json"
DB_DUMP_FILE = L20_DIR / "db_dump.json"
DISCOVERY_FILE = L20_DIR / "discovery_report.json"
ORDERS_FILE = L20_DIR / "orders_state.json"
RESULT_FILE = L20_DIR / "verification_result.json"
BONUS_FILE = L20_DIR / "bonus_result.json"
LOG_FILE = L20_DIR / "operation_log.jsonl"
MAX_RETRIES = 6
MIN_REQUEST_INTERVAL_SECONDS = 2.2

_LAST_REQUEST_TS = 0.0

CITY_ALIASES = {
    "opalino": ["opalino"],
    "domatowo": ["domatowo", "domatowa", "domatowie"],
    "brudzewo": ["brudzewo"],
    "darzlubie": ["darzlubie", "darzlubiu", "darzlubiem"],
    "celbowo": ["celbowo"],
    "mechowo": ["mechowo"],
    "puck": ["puck"],
    "karlinkowo": ["karlinkowo"],
}

DESTINATION_KEYWORDS = (
    "destination",
    "dest",
    "warehouse",
    "warehouseid",
    "locationid",
    "cityid",
    "code",
)

USER_KEYWORDS = (
    "user",
    "creator",
    "employee",
    "worker",
    "person",
    "login",
    "name",
    "surname",
)

ID_KEYWORDS = (
    "id",
    "userid",
    "creatorid",
    "employeeid",
    "personid",
)


class SolverError(RuntimeError):
    pass

def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_log(entry: Dict[str, Any]) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_api_key() -> str:
    api_key = os.environ.get("AI_DEVS_4_API_KEY", "").strip().strip('"').strip("'")
    if not api_key:
        raise SolverError("AI_DEVS_4_API_KEY not set in environment or .env")
    return api_key


def throttle_requests() -> None:
    global _LAST_REQUEST_TS
    now = time.monotonic()
    wait_for = MIN_REQUEST_INTERVAL_SECONDS - (now - _LAST_REQUEST_TS)
    if wait_for > 0:
        time.sleep(wait_for)
    _LAST_REQUEST_TS = time.monotonic()


def post_answer(answer: Dict[str, Any], *, timeout: int = 60) -> Dict[str, Any]:
    payload = {"apikey": get_api_key(), "task": TASK_NAME, "answer": answer}
    for attempt in range(1, MAX_RETRIES + 1):
        throttle_requests()
        response = requests.post(VERIFY_URL, json=payload, timeout=timeout)
        try:
            data = response.json()
        except Exception as exc:
            raise SolverError(f"Non-JSON response from verify: {exc}; body={response.text[:1000]}")
        append_log(
            {
                "ts": time.time(),
                "attempt": attempt,
                "request": payload,
                "response": data,
                "status": response.status_code,
            }
        )
        rate_limited = response.status_code == 429 or data.get("code") == -9999
        if rate_limited and attempt < MAX_RETRIES:
            time.sleep(min(20 * attempt, 90))
            continue
        if response.status_code != 200:
            raise SolverError(f"HTTP {response.status_code}: {data}")
        return data
    raise SolverError("Unexpected retry flow termination")


def fetch_requirements() -> Dict[str, Dict[str, int]]:
    response = requests.get(FOOD_URL, timeout=60)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise SolverError("food4cities.json has unexpected shape")
    save_json(FOOD_FILE, data)
    return data


def extract_table_names(show_tables_result: Dict[str, Any]) -> List[str]:
    explicit = show_tables_result.get("tables")
    if isinstance(explicit, list) and all(isinstance(item, str) for item in explicit):
        return [item for item in explicit if item.lower() != "sqlite_sequence"]

    candidates: List[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            lower = value.lower().strip()
            if lower and lower not in {"ok", "success", "done"}:
                if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", value):
                    candidates.append(value)
                for match in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", value):
                    candidates.append(match)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if normalize_text(key) in {"table", "tables", "name"}:
                    walk(item)
                else:
                    walk(item)

    walk(show_tables_result)
    seen = set()
    ordered: List[str] = []
    for name in candidates:
        if name.lower() == "sqlite_sequence":
            continue
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def rows_from_query_result(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    row_keys = ("rows", "result", "data", "items", "values", "reply")
    for key in row_keys:
        value = result.get(key)
        if isinstance(value, list):
            dict_rows = [item for item in value if isinstance(item, dict)]
            if dict_rows:
                return dict_rows
    if isinstance(result.get("reply"), dict):
        nested = rows_from_query_result(result["reply"])
        if nested:
            return nested
    return []


def query_table(table_name: str) -> Dict[str, Any]:
    return post_answer({"tool": "database", "query": f"select * from {table_name}"})


def query_database(query: str) -> Dict[str, Any]:
    return post_answer({"tool": "database", "query": query})


def discover_database() -> Dict[str, Any]:
    tables_result = post_answer({"tool": "database", "query": "show tables"})
    tables = extract_table_names(tables_result)
    dump: Dict[str, Any] = {"show_tables": tables_result, "tables": {}}
    for table in tables:
        try:
            result = query_table(table)
        except Exception as exc:
            dump["tables"][table] = {"error": str(exc)}
            continue
        dump["tables"][table] = result
    save_json(DB_DUMP_FILE, dump)
    return dump


def run_discovery(requirements: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
    help_result = post_answer({"tool": "help"})
    save_json(HELP_FILE, help_result)
    db_dump = discover_database()
    orders = post_answer({"tool": "orders", "action": "get"})
    save_json(ORDERS_FILE, orders)

    discovery = {
        "requirements": requirements,
        "help": help_result,
        "orders": orders,
        "database": summarize_database(db_dump, requirements),
        "destination_map": fetch_destination_map(requirements),
        "creator": select_creator(),
    }
    save_json(DISCOVERY_FILE, discovery)
    return discovery


def load_cached_discovery(requirements: Dict[str, Dict[str, int]]) -> Optional[Dict[str, Any]]:
    if not DISCOVERY_FILE.exists():
        return None
    try:
        data = json.loads(DISCOVERY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("requirements") != requirements:
        return None
    if not isinstance(data.get("destination_map"), dict):
        return None
    if not isinstance(data.get("creator"), dict):
        return None
    return data


def summarize_database(db_dump: Dict[str, Any], requirements: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
    cities = list(requirements.keys())
    table_summaries: Dict[str, Any] = {}
    destination_candidates: Dict[str, List[Dict[str, Any]]] = {city: [] for city in cities}
    creator_candidates: List[Dict[str, Any]] = []

    for table_name, raw_result in db_dump.get("tables", {}).items():
        rows = rows_from_query_result(raw_result)
        table_summaries[table_name] = {
            "row_count": len(rows),
            "columns": sorted({key for row in rows for key in row.keys()}),
        }
        if rows:
            collect_destination_candidates(table_name, rows, destination_candidates)
            creator_candidates.extend(collect_creator_candidates(table_name, rows))

    best_destinations = {}
    for city, matches in destination_candidates.items():
        unique = []
        seen = set()
        for match in matches:
            key = json.dumps(match, sort_keys=True, ensure_ascii=False)
            if key not in seen:
                seen.add(key)
                unique.append(match)
        best_destinations[city] = unique

    creator_candidates = dedupe_dicts(creator_candidates)
    signature_hints = build_signature_hints(db_dump)
    return {
        "tables": table_summaries,
        "destination_candidates": best_destinations,
        "creator_candidates": creator_candidates,
        "signature_hints": signature_hints,
    }


def collect_destination_candidates(
    table_name: str,
    rows: Sequence[Dict[str, Any]],
    destination_candidates: Dict[str, List[Dict[str, Any]]],
) -> None:
    for row in rows:
        row_texts = [normalize_text(value) for value in row.values() if value is not None]
        for city, aliases in CITY_ALIASES.items():
            if not any(alias in value for alias in aliases for value in row_texts):
                continue
            candidate_fields = {}
            for key, value in row.items():
                norm_key = normalize_text(key)
                if any(marker in norm_key for marker in DESTINATION_KEYWORDS):
                    candidate_fields[key] = value
                if norm_key == "id" and isinstance(value, (int, str)):
                    candidate_fields[key] = value
            if candidate_fields:
                destination_candidates[city].append(
                    {"table": table_name, "row": row, "destination_fields": candidate_fields}
                )


def collect_creator_candidates(table_name: str, rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for row in rows:
        normalized_keys = [normalize_text(key) for key in row.keys()]
        if not any(any(marker in key for marker in USER_KEYWORDS) for key in normalized_keys):
            continue
        id_fields = {key: value for key, value in row.items() if normalize_text(key) in ID_KEYWORDS or key.lower() == "id"}
        name_fields = {key: value for key, value in row.items() if any(marker in normalize_text(key) for marker in USER_KEYWORDS)}
        if id_fields and name_fields:
            candidates.append({"table": table_name, "row": row, "id_fields": id_fields, "name_fields": name_fields})
    return candidates


def dedupe_dicts(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def build_signature_hints(db_dump: Dict[str, Any]) -> Dict[str, Any]:
    hint_tables = []
    for table_name, raw_result in db_dump.get("tables", {}).items():
        rows = rows_from_query_result(raw_result)
        columns = sorted({normalize_text(key) for row in rows for key in row.keys()})
        if any("sha" in col or "hash" in col or "sign" in col for col in columns):
            hint_tables.append({"table": table_name, "columns": columns})
    return {"likely_tables": hint_tables}


def extract_message_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        parts = []
        for key in ("message", "description", "reply", "info", "result"):
            if key in payload:
                parts.append(extract_message_text(payload[key]))
        return "\n".join(part for part in parts if part)
    if isinstance(payload, list):
        return "\n".join(extract_message_text(item) for item in payload)
    return ""


def pick_destination_map(discovery: Dict[str, Any]) -> Dict[str, Any]:
    direct_map = discovery.get("destination_map")
    if isinstance(direct_map, dict) and direct_map:
        return direct_map

    mapping: Dict[str, Any] = {}
    candidates = discovery["database"]["destination_candidates"]
    for city, items in candidates.items():
        exact_values = []
        for item in items:
            for value in item["destination_fields"].values():
                if value is not None and str(value).strip() != "":
                    exact_values.append(value)
        distinct = []
        seen = set()
        for value in exact_values:
            marker = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, dict) else str(value)
            if marker not in seen:
                seen.add(marker)
                distinct.append(value)
        if len(distinct) == 1:
            mapping[city] = distinct[0]
    return mapping


def pick_creator(discovery: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    direct_creator = discovery.get("creator")
    if isinstance(direct_creator, dict) and direct_creator.get("row"):
        return direct_creator

    candidates = discovery["database"]["creator_candidates"]
    if len(candidates) == 1:
        return candidates[0]

    preferred = []
    for candidate in candidates:
        row = candidate["row"]
        norm = {normalize_text(key): str(value).lower() for key, value in row.items()}
        joined = " ".join(norm.values())
        if any(token in joined for token in ("warehouse", "magazyn", "admin", "manager", "food")):
            preferred.append(candidate)
    if len(preferred) == 1:
        return preferred[0]
    return None


def generate_signature(creator_row: Dict[str, Any], destination: Any) -> str:
    login = creator_row.get("login")
    birthday = creator_row.get("birthday")
    if not login or not birthday:
        raise SolverError("Selected creator row is missing login or birthday required by signatureGenerator")
    response = post_answer(
        {
            "tool": "signatureGenerator",
            "action": "generate",
            "login": login,
            "birthday": birthday,
            "destination": destination,
        }
    )
    signature = extract_signature_from_response(response)
    if not signature:
        raise SolverError(f"Could not extract signature from signatureGenerator response: {response}")
    return signature


def extract_signature_from_response(response: Dict[str, Any]) -> Optional[str]:
    if not isinstance(response, dict):
        return None
    for key, value in response.items():
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value.lower()):
            return value.lower()
        if isinstance(value, dict):
            nested = extract_signature_from_response(value)
            if nested:
                return nested
    return None


def fetch_destination_map(requirements: Dict[str, Dict[str, int]]) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    for city in requirements:
        city_name = city.title()
        response = query_database(f"select destination_id, name from destinations where lower(name)=lower('{city_name}')")
        rows = rows_from_query_result(response)
        if len(rows) != 1 or "destination_id" not in rows[0]:
            raise SolverError(f"Could not resolve destination for city {city_name}: {response}")
        mapping[city] = int(rows[0]["destination_id"])
    return mapping


def select_creator() -> Dict[str, Any]:
    response = query_database(
        "select user_id, login, name_surname, birthday, role, is_active from users where role = 2 and is_active = 1 order by user_id limit 1"
    )
    rows = rows_from_query_result(response)
    if len(rows) != 1:
        raise SolverError(f"Could not select a unique active transport user: {response}")
    row = rows[0]
    return {
        "table": "users",
        "row": row,
        "id_fields": {"user_id": row["user_id"]},
        "name_fields": {"login": row.get("login"), "name_surname": row.get("name_surname")},
    }


def decode_base64_with_padding(value: str) -> bytes:
    for padding in range(5):
        try:
            return base64.b64decode(value + ("=" * padding))
        except Exception:
            continue
    raise SolverError("Could not decode base64 payload for bonus")


def discover_bonus() -> Dict[str, Any]:
    response = query_database(
        "select login, name_surname, birthday from users where role = 6 order by birthday desc"
    )
    rows = rows_from_query_result(response)
    if not rows:
        raise SolverError("No rows returned for Vibe Coder bonus query")

    joined = "".join(str(row.get("name_surname", "")) for row in rows)
    decoded = decode_base64_with_padding(joined)
    try:
        message = gzip.decompress(decoded).decode("utf-8")
    except Exception as exc:
        raise SolverError(f"Could not decode gzip payload for bonus: {exc}")

    match = re.search(r"\{FLG:[^}]+\}", message)
    result = {
        "question": "Nie jestem za stary na VibeCodera?",
        "message": match.group(0) if match else message,
        "decoded_text": message,
        "method": "SELECT users where role = 6 order by birthday desc -> join name_surname -> base64 -> gzip",
        "source": {
            "table": "users",
            "query": "select login, name_surname, birthday from users where role = 6 order by birthday desc",
            "count": len(rows),
            "logins": [row.get("login") for row in rows],
        },
    }
    save_json(BONUS_FILE, result)
    return result


def normalize_requirements_for_compare(data: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
    normalized = {}
    for city, items in data.items():
        normalized[normalize_text(city)] = {normalize_text(name): int(count) for name, count in items.items()}
    return normalized


def extract_orders_payload(orders_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("orders", "items", "result", "data"):
        value = orders_response.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def compare_orders(requirements: Dict[str, Dict[str, int]], orders_response: Dict[str, Any]) -> Dict[str, Any]:
    required = normalize_requirements_for_compare(requirements)
    actual_orders = extract_orders_payload(orders_response)
    actual: Dict[str, Dict[str, int]] = {}
    for order in actual_orders:
        city_hint = ""
        for key in ("title", "name", "destination", "city"):
            if order.get(key):
                city_hint += " " + str(order[key])
        city = None
        norm_hint = normalize_text(city_hint)
        for canonical, aliases in CITY_ALIASES.items():
            if any(alias in norm_hint for alias in aliases):
                city = canonical
                break
        if not city:
            continue
        items = {}
        order_items = order.get("items")
        if isinstance(order_items, dict):
            for name, value in order_items.items():
                items[normalize_text(name)] = int(value)
        elif isinstance(order_items, list):
            for entry in order_items:
                if isinstance(entry, dict) and entry.get("name") is not None:
                    items[normalize_text(entry["name"])] = int(entry.get("items", entry.get("count", 0)))
        actual[city] = items
    return {"required": required, "actual": actual, "matches": required == actual}


def create_order(title: str, creator_id: Any, destination: Any, signature: str) -> Dict[str, Any]:
    return post_answer(
        {
            "tool": "orders",
            "action": "create",
            "title": title,
            "creatorID": creator_id,
            "destination": destination,
            "signature": signature,
        }
    )


def append_items(order_id: Any, items: Dict[str, int]) -> Dict[str, Any]:
    return post_answer({"tool": "orders", "action": "append", "id": order_id, "items": items})


def reset_orders() -> Dict[str, Any]:
    return post_answer({"tool": "reset"})


def done() -> Dict[str, Any]:
    return post_answer({"tool": "done"})


def order_id_from_response(response: Dict[str, Any]) -> Any:
    for key in ("id", "orderID", "orderId", "object"):
        if key in response:
            return response[key]
    for key in ("order", "result", "data", "reply"):
        nested = response.get(key)
        if isinstance(nested, dict):
            result = order_id_from_response(nested)
            if result is not None:
                return result
    return None


def run_solver(*, allow_reset: bool = True, skip_done: bool = False, refresh_discovery: bool = False) -> Dict[str, Any]:
    requirements = fetch_requirements()
    discovery = None if refresh_discovery else load_cached_discovery(requirements)
    if discovery is None:
        discovery = run_discovery(requirements)

    destination_map = pick_destination_map(discovery)
    creator = pick_creator(discovery)
    if len(destination_map) != len(requirements):
        raise SolverError(
            "Could not infer a unique destination for every city. Check discovery_report.json and complete mapping manually."
        )
    if creator is None:
        raise SolverError("Could not infer a unique creator row. Check discovery_report.json.")

    creator_id = next(iter(creator["id_fields"].values()))
    plan = {
        "creator": creator,
        "creatorID": creator_id,
        "destination_map": destination_map,
    }

    if allow_reset:
        reset_orders()

    created_orders = []
    for city, items in requirements.items():
        destination = destination_map[city]
        signature = generate_signature(creator["row"], destination)
        response = create_order(
            title=f"Dostawa dla {city.title()}",
            creator_id=creator_id,
            destination=destination,
            signature=signature,
        )
        order_id = order_id_from_response(response)
        if order_id is None:
            raise SolverError(f"Could not extract order id for city {city}: {response}")
        append_response = append_items(order_id, items)
        created_orders.append(
            {
                "city": city,
                "destination": destination,
                "signature": signature,
                "create": response,
                "append": append_response,
                "id": order_id,
            }
        )

    orders_after = post_answer({"tool": "orders", "action": "get"})
    save_json(ORDERS_FILE, orders_after)
    comparison = compare_orders(requirements, orders_after)
    if not comparison["matches"]:
        raise SolverError(f"Orders mismatch after creation: {json.dumps(comparison, ensure_ascii=False)}")

    verification = None
    if not skip_done:
        verification = done()
        save_json(RESULT_FILE, verification)

    result = {
        "requirements": requirements,
        "plan": plan,
        "created_orders": created_orders,
        "orders_after": orders_after,
        "comparison": comparison,
        "verification": verification,
    }
    return result


def cli(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="L20 foodwarehouse solver")
    parser.add_argument("--discovery-only", action="store_true", help="Fetch requirements and run help/database discovery without mutating orders")
    parser.add_argument("--skip-done", action="store_true", help="Create orders but skip final done verification")
    parser.add_argument("--no-reset", action="store_true", help="Do not call reset before creating orders")
    parser.add_argument("--refresh-discovery", action="store_true", help="Ignore cached discovery_report.json and query API again")
    args = parser.parse_args(argv)

    try:
        requirements = fetch_requirements()
        if args.discovery_only:
            discovery = run_discovery(requirements)
            print(json.dumps(discovery, ensure_ascii=False, indent=2))
            return 0
        result = run_solver(
            allow_reset=not args.no_reset,
            skip_done=args.skip_done,
            refresh_discovery=args.refresh_discovery,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())