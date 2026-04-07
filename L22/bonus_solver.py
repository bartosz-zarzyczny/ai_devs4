#!/usr/bin/env python3
"""L22 bonus: secret-file-0502 puzzle.

Trigger: send 3 invalid audio payloads to the phonecall hub endpoint.
The 3rd response reveals:  "secret": "/secret-file-0502"

Solution: GET https://hub.ag3nts.org/secret-file-0502?input[number]=XXXXXXX
where XXXXXXX is a 7-digit number satisfying:
  - no digit 0
  - no digit 7
  - divisible by 7

Usage:
    python L22/bonus_solver.py
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
L22_DIR = Path(__file__).resolve().parent
BONUS_RESULT_FILE = L22_DIR / "bonus_result.json"

load_dotenv(REPO_ROOT / ".env")
API_KEY = os.environ["AI_DEVS_4_API_KEY"]

VERIFY_URL = "https://hub.ag3nts.org/verify"
TASK_NAME = "phonecall"
SECRET_BASE_URL = "https://hub.ag3nts.org"


def trigger_secret_path() -> str | None:
    """Send 3 bad audio payloads; return the secret path from the 3rd response."""
    print("[bonus] starting fresh session...")
    r = requests.post(VERIFY_URL, json={"apikey": API_KEY, "task": TASK_NAME, "answer": {"action": "start"}})
    print(f"[bonus] start: {r.json()}")

    fake = base64.b64encode(b"not an mp3 file at all").decode()
    secret_path = None
    for i in range(1, 4):
        r = requests.post(VERIFY_URL, json={"apikey": API_KEY, "task": TASK_NAME, "answer": {"audio": fake}})
        data = r.json()
        print(f"[bonus] bad upload {i}: {data}")
        if "secret" in data:
            secret_path = data["secret"]
            print(f"[bonus] secret path revealed: {secret_path}")
    return secret_path


def find_valid_number() -> str:
    """Find a 7-digit number with no 0, no 7, divisible by 7."""
    for n in range(1000000, 10000000):
        s = str(n)
        if "0" in s or "7" in s:
            continue
        if n % 7 == 0:
            return s
    raise RuntimeError("no valid number found")


def solve_bonus(secret_path: str) -> str | None:
    """Submit the valid number to the secret endpoint and return the flag."""
    number = find_valid_number()
    print(f"[bonus] trying number: {number}")
    url = SECRET_BASE_URL + secret_path
    r = requests.get(url, params=[("input[number]", number)])
    print(f"[bonus] response: {r.status_code} {r.text[:300]}")
    if r.status_code == 200 and "{FLG:" in r.text:
        return r.text.strip()
    return None


def run_bonus() -> str | None:
    secret_path = trigger_secret_path()
    if not secret_path:
        print("[bonus] failed to get secret path")
        return None

    flag = solve_bonus(secret_path)
    if flag:
        print(f"\n[BONUS] FLAG: {flag}")
        BONUS_RESULT_FILE.write_text(
            json.dumps(
                {
                    "flag": flag,
                    "secret_path": secret_path,
                    "number": find_valid_number(),
                    "constraints": [
                        "7 digits",
                        "no digit 0",
                        "no digit 7",
                        "divisible by 7",
                    ],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"[saved] {BONUS_RESULT_FILE}")
    return flag


if __name__ == "__main__":
    run_bonus()
