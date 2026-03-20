from __future__ import annotations

import json
import os
import re
import urllib.request
import urllib.error
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

VERIFY_URL = "https://hub.ag3nts.org/verify"
TASK_NAME = "drone"
POWER_PLANT_ID = "PWR6132PL"
TARGET_SECTOR = "2,4"
FLIGHT_ALT = "8m"
BONUS_POWER_PLANT_ID = "PWR8406PL"
BONUS_SECTOR = "3,1"
BONUS_LED_COLOR = "#FF00FF"

L10_DIR = Path(__file__).resolve().parent


def get_api_key() -> str:
    key = os.environ.get("AI_DEVS_4_API_KEY", "")
    if not key:
        raise RuntimeError("AI_DEVS_4_API_KEY not set in .env")
    return key


def build_instructions() -> list[str]:
    return [
        "hardReset",
        f"setDestinationObject({POWER_PLANT_ID})",
        f"set({TARGET_SECTOR})",
        f"set({FLIGHT_ALT})",
        "set(engineON)",
        "set(100%)",
        "set(destroy)",
        "set(return)",
        "flyToLocation",
    ]


def build_bonus_instructions() -> list[str]:
    return [
        "hardReset",
        f"setDestinationObject({BONUS_POWER_PLANT_ID})",
        f"set({BONUS_SECTOR})",
        f"setLed({BONUS_LED_COLOR})",
        f"set({FLIGHT_ALT})",
        "set(engineON)",
        "set(100%)",
        "set(image)",
        "set(return)",
        "flyToLocation",
    ]


def post_json(url: str, data: dict) -> tuple[dict, int]:
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read().decode("utf-8")), exc.code


def maybe_extract_flag(payload: dict | None) -> str | None:
    if payload is None:
        return None
    serialized = json.dumps(payload, ensure_ascii=False)
    m = re.search(r"\{FLG:[^}]+\}", serialized)
    return m.group(0) if m else None


def run_solution() -> dict:
    api_key = get_api_key()
    instructions = build_instructions()
    payload = {
        "apikey": api_key,
        "task": TASK_NAME,
        "answer": {"instructions": instructions},
    }
    print(f"Sending {len(instructions)} instructions to {VERIFY_URL}")
    print("Instructions:", json.dumps(instructions, ensure_ascii=False))
    response, status = post_json(VERIFY_URL, payload)
    print(f"HTTP {status}: {json.dumps(response, ensure_ascii=False)}")
    result_path = L10_DIR / "verification_result.json"
    result_path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
    return response
