from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib import error, request


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ENV_FILE = ROOT_DIR / ".env"
OUTPUT_FILE = BASE_DIR / "plant.json"
DATA_URL_TEMPLATE = "https://hub.ag3nts.org/data/{api_key}/findhim_locations.json"


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def fetch_json(url: str) -> object:
    http_request = request.Request(url, method="GET")

    try:
        with request.urlopen(http_request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Pobieranie danych nieudane (HTTP {exc.code}): {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Nie udalo sie polaczyc z serwerem: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Serwer zwrocil niepoprawny JSON.") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pobiera liste elektrowni i ich kody do pliku plant.json."
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("AI_DEVS_4_API_KEY"),
        help="Klucz AI_DEVS_4_API_KEY. Domyslnie pobierany z .env lub srodowiska.",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_FILE),
        help="Sciezka pliku wynikowego JSON.",
    )
    return parser.parse_args()


def main() -> None:
    load_env_file(ENV_FILE)
    args = parse_args()

    api_key = args.api_key or os.getenv("AI_DEVS_4_API_KEY")
    if not api_key:
        raise RuntimeError("Brak AI_DEVS_4_API_KEY w .env/srodowisku lub parametrze --api-key.")

    url = DATA_URL_TEMPLATE.format(api_key=api_key)
    payload = fetch_json(url)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Zapisano dane do: {output_path}")


if __name__ == "__main__":
    main()