from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any
from urllib import error, request


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ENV_FILE = ROOT_DIR / ".env"
INPUT_FILE = BASE_DIR / "people_out.csv"
OUTPUT_FILE = BASE_DIR / "locations.json"
LOCATION_URL = "https://hub.ag3nts.org/api/location"


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_people(input_path: Path) -> list[dict[str, str]]:
    with input_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    people: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for row in rows:
        name = (row.get("name") or "").strip()
        surname = (row.get("surname") or "").strip()
        if not name or not surname:
            continue

        key = (name, surname)
        if key in seen:
            continue
        seen.add(key)

        people.append({"name": name, "surname": surname})

    return people


def post_location(api_key: str, name: str, surname: str) -> Any:
    payload = {
        "apikey": api_key,
        "name": name,
        "surname": surname,
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        LOCATION_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Location HTTP {exc.code} dla {name} {surname}: {details}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(f"Nie udalo sie polaczyc z endpointem location: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Niepoprawny JSON odpowiedzi dla {name} {surname}.") from exc


def normalize_locations(raw_response: Any) -> list[Any]:
    if isinstance(raw_response, list):
        return raw_response

    if isinstance(raw_response, dict):
        if isinstance(raw_response.get("locations"), list):
            return raw_response["locations"]
        if isinstance(raw_response.get("message"), list):
            return raw_response["message"]

    raise RuntimeError(f"Nieoczekiwany format odpowiedzi: {raw_response!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pobiera lokalizacje osob z people_out.csv przez endpoint /api/location."
    )
    parser.add_argument("--input", default=str(INPUT_FILE), help="Sciezka do people_out.csv")
    parser.add_argument(
        "--output",
        default=str(OUTPUT_FILE),
        help="Sciezka pliku wynikowego JSON.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("AI_DEVS_4_API_KEY"),
        help="Klucz AI_DEVS_4_API_KEY. Domyslnie z .env/srodowiska.",
    )
    return parser.parse_args()


def main() -> None:
    load_env_file(ENV_FILE)
    args = parse_args()

    api_key = args.api_key or os.getenv("AI_DEVS_4_API_KEY")
    if not api_key:
        raise RuntimeError("Brak AI_DEVS_4_API_KEY w .env/srodowisku lub parametrze --api-key.")

    people = read_people(Path(args.input))
    if not people:
        raise RuntimeError("Brak poprawnych rekordow (name, surname) w pliku CSV.")

    results: list[dict[str, Any]] = []
    for person in people:
        raw_response = post_location(api_key, person["name"], person["surname"])
        locations = normalize_locations(raw_response)
        results.append(
            {
                "name": person["name"],
                "surname": person["surname"],
                "locations": locations,
            }
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Przetworzono osob: {len(results)}")
    print(f"Zapisano wynik do: {output_path}")


if __name__ == "__main__":
    main()