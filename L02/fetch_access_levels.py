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
OUTPUT_FILE = BASE_DIR / "access_levels.json"
ACCESSLEVEL_URL = "https://hub.ag3nts.org/api/accesslevel"


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_birth_year(value: str) -> int:
    value = value.strip()
    if len(value) < 4 or not value[:4].isdigit():
        raise RuntimeError(f"Niepoprawna data urodzenia: {value!r}")
    return int(value[:4])


def read_people(input_path: Path) -> list[dict[str, Any]]:
    with input_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    people: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()

    for row in rows:
        name = (row.get("name") or "").strip()
        surname = (row.get("surname") or "").strip()
        birth_date = (row.get("birthDate") or "").strip()
        if not name or not surname or not birth_date:
            continue

        birth_year = parse_birth_year(birth_date)
        key = (name, surname, birth_year)
        if key in seen:
            continue
        seen.add(key)

        people.append(
            {
                "name": name,
                "surname": surname,
                "birthYear": birth_year,
            }
        )

    return people


def post_access_level(api_key: str, person: dict[str, Any]) -> Any:
    payload = {
        "apikey": api_key,
        "name": person["name"],
        "surname": person["surname"],
        "birthYear": person["birthYear"],
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        ACCESSLEVEL_URL,
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
            f"Accesslevel HTTP {exc.code} dla {person['name']} {person['surname']}: {details}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(f"Nie udalo sie polaczyc z endpointem accesslevel: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Niepoprawny JSON odpowiedzi dla {person['name']} {person['surname']}."
        ) from exc


def extract_access_level(raw_response: Any) -> Any:
    if isinstance(raw_response, dict):
        for key in ("accessLevel", "access_level", "level", "message"):
            if key in raw_response:
                return raw_response[key]
    return raw_response


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pobiera poziom dostepu osob z people_out.csv przez endpoint /api/accesslevel."
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
    parser.add_argument("--name", help="Imie pojedynczej osoby do sprawdzenia.")
    parser.add_argument("--surname", help="Nazwisko pojedynczej osoby do sprawdzenia.")
    return parser.parse_args()


def main() -> None:
    load_env_file(ENV_FILE)
    args = parse_args()

    api_key = args.api_key or os.getenv("AI_DEVS_4_API_KEY")
    if not api_key:
        raise RuntimeError("Brak AI_DEVS_4_API_KEY w .env/srodowisku lub parametrze --api-key.")

    people = read_people(Path(args.input))
    if not people:
        raise RuntimeError("Brak poprawnych rekordow (name, surname, birthDate) w pliku CSV.")

    if args.name or args.surname:
        if not args.name or not args.surname:
            raise RuntimeError("Podaj jednoczesnie --name i --surname, aby odpytywac pojedyncza osobe.")
        filtered = [
            p
            for p in people
            if p["name"].casefold() == args.name.casefold()
            and p["surname"].casefold() == args.surname.casefold()
        ]
        if not filtered:
            raise RuntimeError("Nie znaleziono wskazanej osoby w CSV.")
        people = filtered

    results: list[dict[str, Any]] = []
    for person in people:
        raw_response = post_access_level(api_key, person)
        access_level = extract_access_level(raw_response)
        results.append(
            {
                "name": person["name"],
                "surname": person["surname"],
                "birthYear": person["birthYear"],
                "accessLevel": access_level,
                "raw": raw_response,
            }
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Przetworzono osob: {len(results)}")
    print(f"Zapisano wynik do: {output_path}")


if __name__ == "__main__":
    main()