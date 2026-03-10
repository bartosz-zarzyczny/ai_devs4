from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from . import download_plant_locations as dpl
from . import fetch_access_levels as fal
from . import fetch_people_locations as fpl
from . import solve_findhim as sf
from . import verify_findhim_candidates as vfc


def fetch_people_locations(api_key: str | None = None, input_path: str | None = None, output_path: str | None = None) -> list[dict[str, Any]]:
    """Programmatic wrapper for fetching people locations.

    Returns the list of results (and writes output JSON to disk).
    """
    fpl.load_env_file(fpl.ENV_FILE)
    api = api_key or os.getenv("AI_DEVS_4_API_KEY")
    if not api:
        raise RuntimeError("Brak AI_DEVS_4_API_KEY.")

    people = fpl.read_people(Path(input_path) if input_path else fpl.INPUT_FILE)
    results: list[dict[str, Any]] = []
    for person in people:
        raw = fpl.post_location(api, person["name"], person["surname"])
        locations = fpl.normalize_locations(raw)
        results.append({"name": person["name"], "surname": person["surname"], "locations": locations})

    out_path = Path(output_path) if output_path else fpl.OUTPUT_FILE
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def fetch_access_levels(api_key: str | None = None, input_path: str | None = None, output_path: str | None = None, name: str | None = None, surname: str | None = None) -> list[dict[str, Any]]:
    """Programmatic wrapper for fetching access levels."""
    fal.load_env_file(fal.ENV_FILE)
    api = api_key or os.getenv("AI_DEVS_4_API_KEY")
    if not api:
        raise RuntimeError("Brak AI_DEVS_4_API_KEY.")

    people = fal.read_people(Path(input_path) if input_path else fal.INPUT_FILE)
    if name or surname:
        if not name or not surname:
            raise RuntimeError("Podaj jednoczesnie name i surname.")
        people = [p for p in people if p["name"].casefold() == name.casefold() and p["surname"].casefold() == surname.casefold()]

    results: list[dict[str, Any]] = []
    for person in people:
        raw = fal.post_access_level(api, person)
        access = fal.extract_access_level(raw)
        results.append({"name": person["name"], "surname": person["surname"], "birthYear": person["birthYear"], "accessLevel": access, "raw": raw})

    out_path = Path(output_path) if output_path else fal.OUTPUT_FILE
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def download_plant_locations(api_key: str | None = None, output_path: str | None = None) -> Any:
    """Programmatic wrapper for downloading plant locations."""
    dpl.load_env_file(dpl.ENV_FILE)
    api = api_key or os.getenv("AI_DEVS_4_API_KEY")
    if not api:
        raise RuntimeError("Brak AI_DEVS_4_API_KEY.")

    url = dpl.DATA_URL_TEMPLATE.format(api_key=api)
    payload = dpl.fetch_json(url)

    out_path = Path(output_path) if output_path else dpl.OUTPUT_FILE
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def solve_findhim(api_key: str | None = None, input_path: str | None = None, plants_path: str | None = None, max_distance_km: float = 2.0, verify: bool = False, sleep_ms: int = 0, report_path: str | None = None, candidates_path: str | None = None) -> dict[str, Any]:
    """Programmatic wrapper for the full findhim pipeline.

    Returns a report dict and writes `candidates` and `report` to disk.
    """
    sf.load_env_file(sf.ENV_FILE)
    api = api_key or os.getenv("AI_DEVS_4_API_KEY")
    if not api:
        raise RuntimeError("Brak AI_DEVS_4_API_KEY.")

    people = sf.read_people(Path(input_path) if input_path else sf.INPUT_FILE)
    if not people:
        raise RuntimeError("Brak poprawnych rekordow w CSV.")

    plants = sf.load_or_fetch_plants(api, Path(plants_path) if plants_path else Path(sf.PLANT_FILE))
    active_plants = sf.get_active_plants(plants)

    candidates: list[dict[str, Any]] = []
    for person in people:
        location_response = sf.post_json(sf.LOCATION_URL, {"apikey": api, "name": person["name"], "surname": person["surname"]})
        locations = sf.normalize_locations(location_response)

        best_distance = float("inf")
        best_city = ""
        best_point = None

        for point in locations:
            lat = point["latitude"]
            lon = point["longitude"]
            for city in active_plants:
                plant_lat, plant_lon = sf.PLANT_CITY_COORDS[city]
                distance = sf.haversine_km(lat, lon, plant_lat, plant_lon)
                if distance < best_distance:
                    best_distance = distance
                    best_city = city
                    best_point = point

        if best_point is None:
            continue

        if best_distance <= max_distance_km:
            access_response = sf.post_json(sf.ACCESSLEVEL_URL, {"apikey": api, "name": person["name"], "surname": person["surname"], "birthYear": person["birthYear"]})
            access_level = sf.extract_access_level(access_response)
            candidates.append({
                "name": person["name"],
                "surname": person["surname"],
                "birthYear": person["birthYear"],
                "accessLevel": access_level,
                "powerPlantCity": best_city,
                "powerPlant": active_plants[best_city]["code"],
                "distanceKm": round(best_distance, 6),
                "closestPoint": best_point,
            })

        if sleep_ms > 0:
            import time

            time.sleep(sleep_ms / 1000)

    if not candidates:
        raise RuntimeError("Nie znaleziono kandydata spelniajacego kryterium odleglosci.")

    candidates.sort(key=lambda row: row["distanceKm"])
    chosen = candidates[0]
    verify_trials: list[dict[str, Any]] = []

    if verify:
        accepted = None
        for candidate in candidates:
            answer = {"name": candidate["name"], "surname": candidate["surname"], "accessLevel": candidate["accessLevel"], "powerPlant": candidate["powerPlant"]}
            ok, verify_response = sf.try_post_json(sf.VERIFY_URL, {"apikey": api, "task": sf.TASK_NAME, "answer": answer})
            verify_trials.append({"answer": answer, "ok": ok, "response": verify_response})
            if ok:
                accepted = candidate
                break

        if accepted is None:
            raise RuntimeError("Endpoint verify odrzucil wszystkich kandydatow.")

        chosen = accepted

    answer = {"name": chosen["name"], "surname": chosen["surname"], "accessLevel": chosen["accessLevel"], "powerPlant": chosen["powerPlant"]}

    report = {
        "task": sf.TASK_NAME,
        "maxDistanceKm": max_distance_km,
        "candidateCount": len(candidates),
        "selected": answer,
        "selectedDebug": chosen,
        "verifyTrials": verify_trials,
    }

    out_cands = Path(candidates_path) if candidates_path else Path(sf.CANDIDATES_FILE)
    out_rep = Path(report_path) if report_path else Path(sf.REPORT_FILE)
    out_cands.parent.mkdir(parents=True, exist_ok=True)
    out_rep.parent.mkdir(parents=True, exist_ok=True)
    out_cands.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    out_rep.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"report": report, "candidates": candidates}


def verify_findhim_candidates(api_key: str | None = None, candidates_path: str | None = None) -> list[tuple[bool, str]]:
    """Programmatic wrapper for verifying candidates via /verify endpoint.

    Returns list of tuples (ok, response_body).
    """
    vfc.load_env_file(vfc.ENV_FILE)
    api = api_key or os.getenv("AI_DEVS_4_API_KEY")
    if not api:
        raise RuntimeError("Brak AI_DEVS_4_API_KEY.")

    path = Path(candidates_path) if candidates_path else Path(vfc.BASE_DIR) / "findhim_candidates.json"
    candidates = json.loads(path.read_text(encoding="utf-8"))
    results: list[tuple[bool, str]] = []
    for candidate in candidates:
        answer = {"name": candidate["name"], "surname": candidate["surname"], "accessLevel": candidate["accessLevel"], "powerPlant": candidate["powerPlant"]}
        ok, body = vfc.verify_answer(api, answer)
        results.append((ok, body))
    return results
