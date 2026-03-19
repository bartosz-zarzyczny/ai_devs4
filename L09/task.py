from __future__ import annotations

import json
from pathlib import Path

from mailbox_client import verify_mailbox_answer


L09_DIR = Path(__file__).resolve().parent
RESULT_PATH = L09_DIR / "verification_result.json"


ANSWER = {
    "password": "RABARBAR25",
    "date": "2026-03-23",
    "confirmation_code": "SEC-c1e598764329cc9c377ef1d029be8ceb",
}


def solve_main_flag() -> dict:
    response = verify_mailbox_answer(
        password=ANSWER["password"],
        date=ANSWER["date"],
        confirmation_code=ANSWER["confirmation_code"],
    )
    RESULT_PATH.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
    return response


def main() -> None:
    response = solve_main_flag()
    print(json.dumps(response, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()