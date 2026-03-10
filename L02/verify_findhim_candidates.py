from __future__ import annotations

import json
import os
from pathlib import Path
from urllib import error, request


ROOT_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = ROOT_DIR / "L02"
ENV_FILE = ROOT_DIR / ".env"
VERIFY_URL = "https://hub.ag3nts.org/verify"


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def verify_answer(api_key: str, answer: dict[str, object]) -> tuple[bool, str]:
    payload = {
        "apikey": api_key,
        "task": "findhim",
        "answer": answer,
    }

    http_request = request.Request(
        VERIFY_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=120) as response:
            body = response.read().decode("utf-8", errors="replace")
            return True, body
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        return False, details


def main() -> None:
    load_env_file(ENV_FILE)
    api_key = os.getenv("AI_DEVS_4_API_KEY")
    if not api_key:
        raise RuntimeError("Brak AI_DEVS_4_API_KEY.")

    candidates = json.loads((BASE_DIR / "findhim_candidates.json").read_text(encoding="utf-8"))

    for candidate in candidates:
        answer = {
            "name": candidate["name"],
            "surname": candidate["surname"],
            "accessLevel": candidate["accessLevel"],
            "powerPlant": candidate["powerPlant"],
        }

        ok, response_body = verify_answer(api_key, answer)
        status = "OK" if ok else "ERR"
        print(f"{status} {answer['name']} {answer['surname']} -> {response_body}")


if __name__ == "__main__":
    main()
