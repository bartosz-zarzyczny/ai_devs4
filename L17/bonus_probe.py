from __future__ import annotations

import json
import re
import time
from pathlib import Path

from task import post_answer, save_json


L17_DIR = Path(__file__).resolve().parent
BONUS_RESULT_FILE = L17_DIR / "bonus_result.json"
FLAG_RE = re.compile(r"\{FLG:[^}]+\}")

BONUS_SEQUENCE = [
    {
        "startDate": "2020-02-02",
        "startHour": "20:11:02",
        "windMs": 4.4,
        "pitchAngle": 0,
    },
    {
        "startDate": "2020-02-02",
        "startHour": "20:11:02",
        "windMs": 5.5,
        "pitchAngle": 0,
    },
    {
        "startDate": "2020-02-02",
        "startHour": "20:11:02",
        "windMs": 4.4,
        "pitchAngle": 0,
    },
]


def run_bonus_probe() -> dict:
    start_response = post_answer({"action": "start"})
    queued = []
    for item in BONUS_SEQUENCE:
        response = post_answer({"action": "unlockCodeGenerator", **item})
        queued.append(response)

    results: list[dict] = []
    flag = None
    for _ in range(12):
        response = post_answer({"action": "getResult"})
        results.append(response)
        match = FLAG_RE.search(json.dumps(response, ensure_ascii=False))
        if match:
            flag = match.group(0)
            break
        time.sleep(0.5)

    output = {
        "start": start_response,
        "sequence": BONUS_SEQUENCE,
        "queued": queued,
        "results": results,
        "flag": flag,
    }
    save_json(BONUS_RESULT_FILE, output)
    return output


def main() -> None:
    result = run_bonus_probe()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()