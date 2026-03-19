from __future__ import annotations

import json
from pathlib import Path

from mailbox_client import solve_bonus_flag


L09_DIR = Path(__file__).resolve().parent
RESULT_PATH = L09_DIR / "bonus_flag_result.json"


def main() -> None:
    result = solve_bonus_flag()
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()