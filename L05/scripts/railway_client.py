#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import time
from datetime import UTC, datetime
from typing import Any, Dict, Optional

import requests

URL = "https://hub.ag3nts.org/verify"
DEFAULT_LOG_PATH = os.path.join("logs", "railway_requests.log")


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def mask_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k.lower() in {"apikey", "api_key", "token", "authorization"}:
                out[k] = "***"
            else:
                out[k] = mask_sensitive(v)
        return out
    if isinstance(value, list):
        return [mask_sensitive(v) for v in value]
    return value


def log_entry(log_path: str, direction: str, payload: Optional[Dict[str, Any]] = None, resp: Optional[requests.Response] = None) -> None:
    ensure_parent_dir(log_path)
    entry: Dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "direction": direction,
        "payload": mask_sensitive(payload),
    }
    if resp is not None:
        entry["status"] = resp.status_code
        entry["headers"] = dict(resp.headers)
        try:
            entry["body"] = resp.json()
        except Exception:
            entry["body"] = resp.text
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def post_action(payload: Dict[str, Any]) -> requests.Response:
    return requests.post(URL, json=payload, timeout=60)


def wait_from_headers(resp: requests.Response) -> None:
    # PUZZLE HINT: "Nie będę czekać 4 minuty!" - ignore HTTP Retry-After (=240s) completely!
    # Instead read retry_after from the JSON body, which is a short delay (e.g. 32s).
    try:
        body = resp.json()
        ra = body.get("retry_after")
        if isinstance(ra, (int, float)) and ra > 0:
            wait = min(int(ra) + 1, 60)  # cap at 60s just in case
            print(f"  [wait] Sleeping {wait}s from JSON retry_after={ra} (NOT the 4-min HTTP header)")
            time.sleep(wait)
            return
    except Exception:
        pass
    # No JSON retry_after? Short fallback.
    print("  [wait] No JSON retry_after, short fallback 5s")
    time.sleep(5)


def call_api(payload: Dict[str, Any], log_path: str, max_attempts: int = 60) -> Dict[str, Any]:
    """Retry aggressively — puzzle hint says don't wait 4 minutes!"""
    backoff = 1.0
    for attempt in range(1, max_attempts + 1):
        log_entry(log_path, "out", payload=payload)
        try:
            resp = post_action(payload)
        except Exception as e:
            print(f"Request error attempt={attempt}: {e}")
            time.sleep(min(backoff, 5) + random.random())
            backoff = min(10, backoff * 1.5)
            continue

        log_entry(log_path, "in", payload=payload, resp=resp)

        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text}
            # -925 = temporary outage, just retry
            if isinstance(data, dict) and data.get("code") == -925:
                print(f"  code=-925 (temp outage) on attempt={attempt}, retrying fast...")
                time.sleep(min(backoff, 3) + random.random() * 0.5)
                backoff = min(10, backoff * 1.5)
                continue
            return data

        if resp.status_code in (503, 429):
            print(f"  {resp.status_code} on attempt={attempt} — retrying fast (no long wait)")
            wait_from_headers(resp)  # already patched to only sleep 2s
            time.sleep(min(backoff, 3) + random.random() * 0.5)
            backoff = min(10, backoff * 1.5)
            continue

        print("HTTP error:", resp.status_code, resp.text)
        try:
            resp.raise_for_status()
        except Exception:
            return {"error": resp.text, "status": resp.status_code}

    raise RuntimeError("Max retries reached")


def find_flag(obj: Any) -> Optional[str]:
    if isinstance(obj, dict):
        for v in obj.values():
            found = find_flag(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = find_flag(v)
            if found:
                return found
    elif isinstance(obj, str):
        i = obj.find("{FLG:")
        if i >= 0:
            j = obj.find("}", i)
            return obj[i : j + 1] if j > i else obj[i:]
    return None


def extract_sequence(help_obj: Dict[str, Any]) -> Optional[list]:
    # Known simple keys
    for k in ("sequence", "steps", "actions", "workflow", "commands"):
        v = help_obj.get(k)
        if isinstance(v, list):
            return v

    # Recursive fallback - first list likely describing actions
    stack = [help_obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for v in cur.values():
                stack.append(v)
        elif isinstance(cur, list):
            if cur and all(isinstance(i, (dict, str)) for i in cur):
                # prefer list containing at least one action-like item
                if any((isinstance(i, str) or (isinstance(i, dict) and ("action" in i or "name" in i))) for i in cur):
                    return cur
            for i in cur:
                stack.append(i)
    return None


def build_route_open_sequence(help_obj: Dict[str, Any], route: str) -> list[Dict[str, Any]]:
    """Build a safe, explicit sequence from documented actions to open the route."""
    help_data = help_obj.get("help") if isinstance(help_obj, dict) else None
    if not isinstance(help_data, dict):
        help_data = help_obj

    actions = help_data.get("actions", []) if isinstance(help_data, dict) else []
    by_name: Dict[str, Dict[str, Any]] = {}
    for a in actions:
        if isinstance(a, dict) and isinstance(a.get("action"), str):
            by_name[a["action"]] = a

    seq: list[Dict[str, Any]] = []

    # According to help notes, setstatus requires reconfigure mode first.
    if "reconfigure" in by_name:
        seq.append({"action": "reconfigure", "route": route})

    if "setstatus" in by_name:
        allowed = by_name["setstatus"].get("allowed_values", [])
        value = "RTOPEN"
        if isinstance(allowed, list) and allowed and "RTOPEN" not in allowed:
            value = str(allowed[0])
        seq.append({"action": "setstatus", "route": route, "value": value})

    if "save" in by_name:
        seq.append({"action": "save", "route": route})

    if "getstatus" in by_name:
        seq.append({"action": "getstatus", "route": route})

    return seq


def step_to_answer(step: Any) -> Dict[str, Any]:
    if isinstance(step, str):
        return {"action": step}
    if isinstance(step, dict):
        if "answer" in step and isinstance(step["answer"], dict):
            return step["answer"]
        if "action" in step:
            return dict(step)
        if "name" in step:
            out = dict(step)
            out["action"] = out.pop("name")
            return out
        # Last-resort: wrap as params
        return {"action": "unknown", "params": step}
    return {"action": str(step)}


def run_auto(apikey: str, help_obj: Dict[str, Any], route: str, log_path: str, confirm: bool) -> Optional[str]:
    seq = build_route_open_sequence(help_obj, route=route)
    if not seq:
        # fallback to generic parsing only if documented actions are missing
        seq = extract_sequence(help_obj)
    if not seq:
        print("Nie udało się wykryć sekwencji akcji w odpowiedzi help.")
        return None

    print(f"Wykryto {len(seq)} kroków. Start wykonania...")
    for idx, step in enumerate(seq, start=1):
        answer = step_to_answer(step)
        print(f"Krok {idx}/{len(seq)} -> {answer}")

        if confirm:
            dec = input("Wykonać ten krok? [y/N]: ").strip().lower()
            if dec not in {"y", "yes"}:
                print("Pomijam krok")
                continue

        payload = {"apikey": apikey, "task": "railway", "answer": answer}
        out = call_api(payload, log_path=log_path)

        flag = find_flag(out)
        if flag:
            return flag

        # If API returns explicit next_action in each step, prioritize it
        next_action = out.get("next_action") if isinstance(out, dict) else None
        if isinstance(next_action, str):
            payload2 = {"apikey": apikey, "task": "railway", "answer": {"action": next_action}}
            out2 = call_api(payload2, log_path=log_path)
            flag2 = find_flag(out2)
            if flag2:
                return flag2

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Railway client")
    parser.add_argument("--apikey", required=False, help="API key or env AI_DEVS_4_API_KEY")
    parser.add_argument("--auto", action="store_true", help="Execute sequence parsed from help")
    parser.add_argument("--confirm", action="store_true", help="Ask before each auto step")
    parser.add_argument("--route", default="x-01", help="Route id to activate (default: x-01)")
    parser.add_argument("--log", default=DEFAULT_LOG_PATH, help="JSONL log file path")
    args = parser.parse_args()

    apikey = args.apikey or os.getenv("AI_DEVS_4_API_KEY")
    if not apikey:
        print("Brak klucza API. Użyj --apikey albo AI_DEVS_4_API_KEY.")
        return 2

    help_payload = {"apikey": apikey, "task": "railway", "answer": {"action": "help"}}
    help_obj = call_api(help_payload, log_path=args.log)

    print(json.dumps(help_obj, indent=2, ensure_ascii=False))

    flag = find_flag(help_obj)
    if flag:
        print("FLAG:", flag)
        return 0

    if args.auto:
        flag = run_auto(apikey, help_obj, route=args.route, log_path=args.log, confirm=args.confirm)
        if flag:
            print("FLAG:", flag)
            return 0
        print("Zakończono auto bez flagi. Sprawdź logi i odpowiedź help.")
        return 1

    print("Brak flagi w help. Uruchom z --auto, aby wykonać sekwencję.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
