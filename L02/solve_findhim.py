from __future__ import annotations

import argparse
import csv
import json
import math
import os
import time
from pathlib import Path
from typing import Any
from urllib import error, parse, request


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ENV_FILE = ROOT_DIR / ".env"
INPUT_FILE = BASE_DIR / "people_out.csv"
PLANT_FILE = BASE_DIR / "plant.json"
REPORT_FILE = BASE_DIR / "findhim_report.json"
CANDIDATES_FILE = BASE_DIR / "findhim_candidates.json"

PLANTS_URL_TEMPLATE = "https://hub.ag3nts.org/data/{api_key}/findhim_locations.json"
LOCATION_URL = "https://hub.ag3nts.org/api/location"
ACCESSLEVEL_URL = "https://hub.ag3nts.org/api/accesslevel"
VERIFY_URL = "https://hub.ag3nts.org/verify"
TASK_NAME = "findhim"

# City centers used to compare coordinates with known power-plant locations.
# In source data, plants are represented by city names and plant codes.
PLANT_CITY_COORDS = {
    "Zabrze": (50.3086154, 18.7863749),
    "Piotrków Trybunalski": (51.4082625, 19.6961670),
    "Grudziądz": (53.4725120, 18.7618937),
    "Tczew": (54.0869532, 18.8000293),
    "Radom": (51.4022557, 21.1541546),
    "Chelmno": (53.3493915, 18.4235473),
    "Żarnowiec": (50.4832713, 19.8624200),
}


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

        people.append({"name": name, "surname": surname, "birthYear": birth_year})

    return people


def fetch_json(url: str) -> Any:
    http_request = request.Request(url, method="GET")
    try:
        with request.urlopen(http_request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GET {url} zakonczony HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Nie udalo sie polaczyc z serwerem: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Serwer zwrocil niepoprawny JSON dla {url}") from exc


def post_json(url: str, payload: dict[str, Any]) -> Any:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {url} zakonczony HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Nie udalo sie polaczyc z {url}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Serwer zwrocil niepoprawny JSON dla {url}") from exc


def try_post_json(url: str, payload: dict[str, Any]) -> tuple[bool, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=120) as response:
            return True, json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(details)
        except json.JSONDecodeError:
            parsed = {"error": details, "status": exc.code}
        return False, parsed
    except error.URLError as exc:
        return False, {"error": f"Nie udalo sie polaczyc z {url}: {exc}"}
    except json.JSONDecodeError as exc:
        return False, {"error": f"Serwer zwrocil niepoprawny JSON dla {url}: {exc}"}


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_or_fetch_plants(api_key: str, plant_file: Path) -> dict[str, dict[str, Any]]:
    if plant_file.exists():
        payload = json.loads(plant_file.read_text(encoding="utf-8"))
    else:
        payload = fetch_json(PLANTS_URL_TEMPLATE.format(api_key=parse.quote(api_key, safe="")))
        save_json(plant_file, payload)

    plants = payload.get("power_plants") if isinstance(payload, dict) else None
    if not isinstance(plants, dict):
        raise RuntimeError("Nieoczekiwany format pliku/listy elektrowni.")
    return plants


def get_active_plants(plants: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    active: dict[str, dict[str, Any]] = {}
    for city, details in plants.items():
        if not isinstance(details, dict):
            continue
        if not details.get("is_active"):
            continue
        if city not in PLANT_CITY_COORDS:
            continue
        active[city] = details
    if not active:
        raise RuntimeError("Brak aktywnych elektrowni z dostepnymi koordynatami miast.")
    return active


def normalize_locations(raw_response: Any) -> list[dict[str, float]]:
    raw_locations: Any
    if isinstance(raw_response, list):
        raw_locations = raw_response
    elif isinstance(raw_response, dict) and isinstance(raw_response.get("locations"), list):
        raw_locations = raw_response["locations"]
    else:
        raise RuntimeError(f"Nieoczekiwany format odpowiedzi /api/location: {raw_response!r}")

    locations: list[dict[str, float]] = []
    for item in raw_locations:
        if not isinstance(item, dict):
            continue
        lat = item.get("latitude")
        lon = item.get("longitude")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        locations.append({"latitude": float(lat), "longitude": float(lon)})

    if not locations:
        raise RuntimeError("Brak poprawnych koordynatow w odpowiedzi /api/location.")
    return locations


def extract_access_level(raw_response: Any) -> int:
    if isinstance(raw_response, dict):
        value = raw_response.get("accessLevel", raw_response.get("access_level", raw_response.get("level")))
        if isinstance(value, int):
            return value
    if isinstance(raw_response, int):
        return raw_response
    raise RuntimeError(f"Nieoczekiwany format odpowiedzi /api/accesslevel: {raw_response!r}")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rozwiazuje zadanie findhim end-to-end.")
    parser.add_argument("--input", default=str(INPUT_FILE), help="Sciezka do people_out.csv")
    parser.add_argument("--plants", default=str(PLANT_FILE), help="Sciezka do pliku z elektrowniami")
    parser.add_argument("--report", default=str(REPORT_FILE), help="Sciezka pliku raportu finalnego")
    parser.add_argument(
        "--candidates",
        default=str(CANDIDATES_FILE),
        help="Sciezka pliku ze wszystkimi kandydatami i dystansami.",
    )
    parser.add_argument(
        "--max-distance-km",
        type=float,
        default=2.0,
        help="Maksymalny dystans (km) uznawany za 'bardzo blisko'.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("AI_DEVS_4_API_KEY"),
        help="Klucz AI_DEVS_4_API_KEY. Domyslnie z .env/srodowiska.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Wysyla finalna odpowiedz do endpointu /verify.",
    )
    parser.add_argument(
        "--sleep-ms",
        type=int,
        default=0,
        help="Opcjonalna pauza miedzy requestami (ms).",
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
        raise RuntimeError("Brak poprawnych rekordow w CSV.")

    plants = load_or_fetch_plants(api_key, Path(args.plants))
    active_plants = get_active_plants(plants)

    candidates: list[dict[str, Any]] = []
    for person in people:
        location_response = post_json(
            LOCATION_URL,
            {
                "apikey": api_key,
                "name": person["name"],
                "surname": person["surname"],
            },
        )
        locations = normalize_locations(location_response)

        best_distance = float("inf")
        best_city = ""
        best_point: dict[str, float] | None = None

        for point in locations:
            lat = point["latitude"]
            lon = point["longitude"]
            for city in active_plants:
                plant_lat, plant_lon = PLANT_CITY_COORDS[city]
                distance = haversine_km(lat, lon, plant_lat, plant_lon)
                if distance < best_distance:
                    best_distance = distance
                    best_city = city
                    best_point = point

        if best_point is None:
            continue

        if best_distance <= args.max_distance_km:
            access_response = post_json(
                ACCESSLEVEL_URL,
                {
                    "apikey": api_key,
                    "name": person["name"],
                    "surname": person["surname"],
                    "birthYear": person["birthYear"],
                },
            )
            access_level = extract_access_level(access_response)
            candidates.append(
                {
                    "name": person["name"],
                    "surname": person["surname"],
                    "birthYear": person["birthYear"],
                    "accessLevel": access_level,
                    "powerPlantCity": best_city,
                    "powerPlant": active_plants[best_city]["code"],
                    "distanceKm": round(best_distance, 6),
                    "closestPoint": best_point,
                }
            )

        if args.sleep_ms > 0:
            time.sleep(args.sleep_ms / 1000)

    if not candidates:
        raise RuntimeError("Nie znaleziono kandydata spelniajacego kryterium odleglosci.")

    candidates.sort(key=lambda row: row["distanceKm"])

    chosen = candidates[0]
    verify_trials: list[dict[str, Any]] = []

    if args.verify:
        accepted: dict[str, Any] | None = None
        for candidate in candidates:
            answer = {
                "name": candidate["name"],
                "surname": candidate["surname"],
                "accessLevel": candidate["accessLevel"],
                "powerPlant": candidate["powerPlant"],
            }
            verify_payload = {
                "apikey": api_key,
                "task": TASK_NAME,
                "answer": answer,
            }
            ok, verify_response = try_post_json(VERIFY_URL, verify_payload)
            verify_trials.append(
                {
                    "answer": answer,
                    "ok": ok,
                    "response": verify_response,
                }
            )
            if ok:
                accepted = candidate
                print(json.dumps(verify_response, ensure_ascii=False, indent=2))
                break

        if accepted is None:
            raise RuntimeError("Endpoint verify odrzucil wszystkich kandydatow.")

        chosen = accepted

    answer = {
        "name": chosen["name"],
        "surname": chosen["surname"],
        "accessLevel": chosen["accessLevel"],
        "powerPlant": chosen["powerPlant"],
    }

    report = {
        "task": TASK_NAME,
        "maxDistanceKm": args.max_distance_km,
        "candidateCount": len(candidates),
        "selected": answer,
        "selectedDebug": chosen,
        "verifyTrials": verify_trials,
    }

    save_json(Path(args.candidates), candidates)
    save_json(Path(args.report), report)

    print(f"Kandydaci: {len(candidates)}")
    print(f"Wybrany: {answer['name']} {answer['surname']} -> {answer['powerPlant']}")


if __name__ == "__main__":
    main()