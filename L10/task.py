from __future__ import annotations

import json
import sys

from drone_solver import maybe_extract_flag, run_solution


def main() -> None:
    verification = run_solution()
    flag = maybe_extract_flag(verification)
    if flag:
        print(f"\nFlag found: {flag}")
    else:
        print("\nNo flag pattern found in response.")
        print("Full response:", json.dumps(verification, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
