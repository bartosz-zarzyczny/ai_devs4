from __future__ import annotations

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


L17_DIR = Path(__file__).resolve().parent
REPO_ROOT = L17_DIR.parent
VERIFY_URL = "https://hub.ag3nts.org/verify"
TASK_NAME = "windpower"

VERIFICATION_FILE = L17_DIR / "verification_result.json"
DOCUMENTATION_FILE = L17_DIR / "documentation.json"
WEATHER_FILE = L17_DIR / "weather_report.json"
TURBINE_FILE = L17_DIR / "turbine_report.json"
POWERPLANT_FILE = L17_DIR / "powerplant_report.json"
SCHEDULE_FILE = L17_DIR / "schedule.json"

load_dotenv(REPO_ROOT / ".env")


@dataclass(frozen=True)
class ConfigPoint:
    timestamp: str
    wind_ms: float
    pitch_angle: int
    turbine_mode: str


def get_api_key() -> str:
    api_key = os.environ.get("AI_DEVS_4_API_KEY", "").strip().strip('"').strip("'")
    if not api_key:
        raise RuntimeError("AI_DEVS_4_API_KEY not set in .env")
    return api_key


def post_answer(answer: dict[str, Any], *, timeout: int = 45) -> dict[str, Any]:
    payload = {
        "apikey": get_api_key(),
        "task": TASK_NAME,
        "answer": answer,
    }
    response = requests.post(VERIFY_URL, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_deficit_kw(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)
    numbers = [float(match) for match in re.findall(r"\d+(?:\.\d+)?", text)]
    if not numbers:
        raise ValueError(f"Cannot parse power deficit from {value!r}")
    return max(numbers)


def parse_yield_value(value: str) -> float:
    if "-" in value:
        left, right = value.split("-", 1)
        return (float(left) + float(right)) / 2.0
    return float(value)


def build_wind_curve(documentation: dict[str, Any]) -> list[tuple[float, float]]:
    curve: list[tuple[float, float]] = []
    for item in documentation["windPowerYieldPercent"]:
        if "windMs" in item:
            curve.append((float(item["windMs"]), parse_yield_value(item["yieldPercent"])))
            continue
        if item.get("windMsRange") == "12-14":
            curve.append((12.0, parse_yield_value(item["yieldPercent"])))
    curve.sort(key=lambda pair: pair[0])
    return curve


def pitch_factor(documentation: dict[str, Any], pitch_angle: int) -> float:
    for item in documentation["pitchAngleYieldPercent"]:
        if int(item["pitchAngleDeg"]) == int(pitch_angle):
            return parse_yield_value(item["yieldPercent"]) / 100.0
    raise ValueError(f"Unsupported pitch angle: {pitch_angle}")


def estimate_wind_yield_percent(curve: list[tuple[float, float]], wind_ms: float, cutoff: float) -> float:
    if wind_ms < curve[0][0]:
        return 0.0
    if wind_ms >= cutoff:
        return 0.0
    for (left_wind, left_yield), (right_wind, right_yield) in zip(curve, curve[1:]):
        if wind_ms <= right_wind:
            span = right_wind - left_wind
            if span <= 0:
                return left_yield
            ratio = (wind_ms - left_wind) / span
            return left_yield + ratio * (right_yield - left_yield)
    return curve[-1][1]


def estimate_power_kw(documentation: dict[str, Any], wind_ms: float, pitch_angle: int) -> float:
    rated_power_kw = float(documentation["ratedPowerKw"])
    cutoff = float(documentation["safety"]["cutoffWindMs"])
    curve = build_wind_curve(documentation)
    wind_yield_percent = estimate_wind_yield_percent(curve, wind_ms, cutoff)
    return rated_power_kw * (wind_yield_percent / 100.0) * pitch_factor(documentation, pitch_angle)


def queue_get_requests() -> None:
    params = ("weather", "powerplantcheck")
    with ThreadPoolExecutor(max_workers=len(params)) as executor:
        list(executor.map(lambda param: post_answer({"action": "get", "param": param}), params))


def poll_results(expected_sources: set[str], *, timeout_seconds: float) -> dict[str, dict[str, Any]]:
    started_at = time.monotonic()
    results: dict[str, dict[str, Any]] = {}
    while time.monotonic() - started_at < timeout_seconds:
        response = post_answer({"action": "getResult"})
        source = response.get("sourceFunction")
        if source in expected_sources:
            results[source] = response
            if results.keys() >= expected_sources:
                return results
        time.sleep(0.5)
    missing = sorted(expected_sources - results.keys())
    raise TimeoutError(f"Timed out waiting for queued results: {missing}")


def choose_production_slot(
    documentation: dict[str, Any],
    weather_report: dict[str, Any],
    powerplant_report: dict[str, Any],
) -> ConfigPoint:
    cutoff = float(documentation["safety"]["cutoffWindMs"])
    min_operational = float(documentation["safety"]["minOperationalWindMs"])
    required_power_kw = parse_deficit_kw(powerplant_report.get("powerDeficitKw", 0))

    candidates: list[tuple[float, str, float]] = []
    for entry in weather_report["forecast"]:
        wind_ms = float(entry["windMs"])
        if not (min_operational <= wind_ms < cutoff):
            continue
        estimated_power = estimate_power_kw(documentation, wind_ms, pitch_angle=0)
        candidates.append((estimated_power, entry["timestamp"], wind_ms))

    if not candidates:
        raise RuntimeError("No viable production slot found in forecast.")

    viable = [item for item in candidates if item[0] >= required_power_kw]
    if viable:
        estimated_power, timestamp, wind_ms = max(viable, key=lambda item: (item[0], -_timestamp_rank(item[1])))
        return ConfigPoint(timestamp=timestamp, wind_ms=wind_ms, pitch_angle=0, turbine_mode="production")

    estimated_power, timestamp, wind_ms = max(candidates, key=lambda item: (item[0], -_timestamp_rank(item[1])))
    raise RuntimeError(
        f"Best forecast slot {timestamp} only yields {estimated_power:.2f} kW, below required {required_power_kw:.2f} kW."
    )


def _timestamp_rank(timestamp: str) -> int:
    return int(re.sub(r"\D", "", timestamp))


def next_timestamp(weather_report: dict[str, Any], timestamp: str) -> tuple[str, float] | None:
    forecast = weather_report["forecast"]
    for index, entry in enumerate(forecast):
        if entry["timestamp"] != timestamp:
            continue
        if index + 1 >= len(forecast):
            return None
        next_entry = forecast[index + 1]
        return str(next_entry["timestamp"]), float(next_entry["windMs"])
    return None


def build_schedule(
    documentation: dict[str, Any],
    weather_report: dict[str, Any],
    powerplant_report: dict[str, Any],
) -> list[ConfigPoint]:
    cutoff = float(documentation["safety"]["cutoffWindMs"])
    points: dict[str, ConfigPoint] = {}

    for entry in weather_report["forecast"]:
        wind_ms = float(entry["windMs"])
        if wind_ms > cutoff:
            timestamp = str(entry["timestamp"])
            points[timestamp] = ConfigPoint(
                timestamp=timestamp,
                wind_ms=wind_ms,
                pitch_angle=90,
                turbine_mode="idle",
            )

    production = choose_production_slot(documentation, weather_report, powerplant_report)
    points[production.timestamp] = production

    schedule = [points[key] for key in sorted(points)]
    if len(schedule) != 4:
        raise RuntimeError(f"Expected exactly 4 config points, got {len(schedule)}")
    return schedule


def queue_unlock_codes(points: list[ConfigPoint]) -> None:
    with ThreadPoolExecutor(max_workers=len(points)) as executor:
        list(
            executor.map(
                lambda point: post_answer(
                    {
                        "action": "unlockCodeGenerator",
                        "startDate": point.timestamp.split()[0],
                        "startHour": point.timestamp.split()[1],
                        "windMs": point.wind_ms,
                        "pitchAngle": point.pitch_angle,
                    }
                ),
                points,
            )
        )


def collect_unlock_codes(points: list[ConfigPoint], *, timeout_seconds: float) -> dict[str, str]:
    expected = {point.timestamp for point in points}
    codes: dict[str, str] = {}
    started_at = time.monotonic()
    while time.monotonic() - started_at < timeout_seconds:
        response = post_answer({"action": "getResult"})
        if response.get("sourceFunction") != "unlockCodeGenerator":
            time.sleep(0.5)
            continue
        signed = response.get("signedParams", {})
        timestamp = f"{signed.get('startDate', '')} {signed.get('startHour', '')}".strip()
        unlock_code = response.get("unlockCode")
        if timestamp in expected and unlock_code:
            codes[timestamp] = str(unlock_code)
            if codes.keys() >= expected:
                return codes
        time.sleep(0.25)
    missing = sorted(expected - codes.keys())
    raise TimeoutError(f"Timed out waiting for unlock codes: {missing}")


def submit_config(points: list[ConfigPoint], unlock_codes: dict[str, str]) -> dict[str, Any]:
    configs: dict[str, dict[str, Any]] = {}
    for point in points:
        unlock_code = unlock_codes.get(point.timestamp)
        if not unlock_code:
            raise RuntimeError(f"Missing unlock code for {point.timestamp}")
        configs[point.timestamp] = {
            "pitchAngle": point.pitch_angle,
            "turbineMode": point.turbine_mode,
            "unlockCode": unlock_code,
        }
    return post_answer({"action": "config", "configs": configs})


def queue_final_turbinecheck() -> dict[str, Any]:
    return post_answer({"action": "get", "param": "turbinecheck"})


def schedule_as_dict(points: list[ConfigPoint], unlock_codes: dict[str, str]) -> dict[str, Any]:
    return {
        "task": TASK_NAME,
        "configs": {
            point.timestamp: {
                "windMs": point.wind_ms,
                "pitchAngle": point.pitch_angle,
                "turbineMode": point.turbine_mode,
                "unlockCode": unlock_codes[point.timestamp],
            }
            for point in points
        },
    }


def solve() -> dict[str, Any]:
    start_response = post_answer({"action": "start"})
    session_timeout = float(start_response.get("sessionTimeout", 40))

    documentation = post_answer({"action": "get", "param": "documentation"})
    save_json(DOCUMENTATION_FILE, documentation)

    queue_get_requests()
    queued_results = poll_results({"weather", "powerplantcheck"}, timeout_seconds=max(12.0, session_timeout - 8.0))
    weather_report = queued_results["weather"]
    powerplant_report = queued_results["powerplantcheck"]
    save_json(WEATHER_FILE, weather_report)
    save_json(POWERPLANT_FILE, powerplant_report)

    points = build_schedule(documentation, weather_report, powerplant_report)
    queue_unlock_codes(points)
    unlock_codes = collect_unlock_codes(points, timeout_seconds=max(8.0, session_timeout - 12.0))
    save_json(SCHEDULE_FILE, schedule_as_dict(points, unlock_codes))

    config_response = submit_config(points, unlock_codes)
    final_turbinecheck = queue_final_turbinecheck()
    done_response = post_answer({"action": "done"})

    save_json(TURBINE_FILE, final_turbinecheck)
    save_json(VERIFICATION_FILE, done_response)

    result = {
        "start": start_response,
        "documentation": documentation,
        "initialReports": queued_results,
        "schedule": schedule_as_dict(points, unlock_codes),
        "configResponse": config_response,
        "finalTurbinecheck": final_turbinecheck,
        "verification": done_response,
    }
    return result


_RUN_LOCK = threading.Lock()


def main() -> None:
    with _RUN_LOCK:
        result = solve()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()