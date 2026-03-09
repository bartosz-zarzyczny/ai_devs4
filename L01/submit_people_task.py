from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib import error, request


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ENV_FILE = ROOT_DIR / ".env"
ANSWER_FILE = BASE_DIR / "output.json"
VERIFY_URL = "https://hub.ag3nts.org/verify"
TASK_NAME = "people"


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_answer(answer_path: Path) -> list[dict[str, object]]:
    payload = json.loads(answer_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("Plik output.json musi zawierać tablicę obiektów.")
    return payload


def submit_answer(api_key: str, answer: list[dict[str, object]]) -> dict[str, object]:
    body = json.dumps(
        {
            "apikey": api_key,
            "task": TASK_NAME,
            "answer": answer,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    http_request = request.Request(
        VERIFY_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Verify HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Nie udalo sie polaczyc z endpointem verify: {exc}") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wysyla wynik zadania people do endpointu verify.")
    parser.add_argument("--answer", default=str(ANSWER_FILE))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_env_file(ENV_FILE)

    api_key = os.getenv("AI_DEVS_4_API_KEY")
    if not api_key:
        raise RuntimeError("Brak zmiennej AI_DEVS_4_API_KEY w pliku .env lub srodowisku.")

    answer = load_answer(Path(args.answer))
    result = submit_answer(api_key, answer)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()