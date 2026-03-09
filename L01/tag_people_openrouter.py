from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any
from urllib import error, request


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ENV_FILE = ROOT_DIR / ".env"
INPUT_FILE = BASE_DIR / "people_out.csv"
OUTPUT_FILE = BASE_DIR / "output.json"
DEFAULT_MODEL = "google/gemini-2.0-flash-lite-001"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
ALLOWED_TAGS = [
    "IT",
    "transport",
    "edukacja",
    "medycyna",
    "praca z ludźmi",
    "praca z pojazdami",
    "praca fizyczna",
]


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def read_people(input_file: Path) -> list[dict[str, str]]:
    with input_file.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_payload_rows(people: list[dict[str, str]]) -> list[dict[str, Any]]:
    payload_rows: list[dict[str, Any]] = []

    for index, person in enumerate(people, start=1):
        payload_rows.append(
            {
                "row_index": index,
                "name": person["name"],
                "surname": person["surname"],
                "gender": person["gender"],
                "born": int(person["birthDate"][:4]),
                "city": person["birthPlace"],
                "job": person["job"],
            }
        )

    return payload_rows


def build_messages(payload_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    system_prompt = (
        "Jesteś klasyfikatorem zawodów. Otrzymasz listę osób z opisem pracy. "
        "Dla każdej osoby dobierz jeden lub więcej tagów wyłącznie z dozwolonej listy. "
        "Nie dodawaj żadnych innych tagów ani komentarzy."
    )
    user_prompt = (
        "Przeanalizuj każdą osobę i przypisz tagi na podstawie opisu pracy.\n"
        "Dozwolone tagi:\n"
        + "\n".join(f"- {tag}" for tag in ALLOWED_TAGS)
        + "\n\n"
        + "Zasady:\n"
        + "1. Zwróć wyłącznie poprawny JSON bez markdownu.\n"
        + "2. Zwróć tablicę obiektów.\n"
        + "3. Każdy obiekt ma dokładnie pola: row_index, tags.\n"
        + "4. Pole tags ma być tablicą unikalnych tagów z dozwolonej listy.\n"
        + "5. Każda osoba musi otrzymać przynajmniej jeden tag.\n"
        + "6. Zachowaj wszystkie osoby i wszystkie row_index dokładnie raz.\n\n"
        + "Dane wejściowe:\n"
        + json.dumps(payload_rows, ensure_ascii=False, indent=2)
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_repair_messages(payload_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    system_prompt = (
        "Jesteś klasyfikatorem zawodów. Musisz przypisać co najmniej jeden tag do każdej osoby, "
        "wybierając najbliższe znaczeniowo tagi z dozwolonej listy."
    )
    user_prompt = (
        "Popraw brakujące tagi dla poniższych osób.\n"
        "Dozwolone tagi:\n"
        + "\n".join(f"- {tag}" for tag in ALLOWED_TAGS)
        + "\n\n"
        + "Zasady:\n"
        + "1. Zwróć wyłącznie poprawny JSON bez markdownu.\n"
        + "2. Zwróć tablicę obiektów.\n"
        + "3. Każdy obiekt ma dokładnie pola: row_index, tags.\n"
        + "4. Każda osoba musi otrzymać przynajmniej jeden tag.\n"
        + "5. Jeśli opis nie pasuje idealnie, wybierz najbliższy sensowny tag zamiast pustej listy.\n\n"
        + "Dane wejściowe:\n"
        + json.dumps(payload_rows, ensure_ascii=False, indent=2)
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def call_openrouter(api_key: str, model: str, messages: list[dict[str, str]]) -> str:
    body = json.dumps(
        {
            "model": model,
            "temperature": 0,
            "messages": messages,
        }
    ).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com",
        "X-Title": "ai_devs4-tagging",
    }

    http_request = request.Request(OPENROUTER_URL, data=body, headers=headers, method="POST")

    try:
        with request.urlopen(http_request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Nie udalo sie polaczyc z OpenRouter: {exc}") from exc

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Nieoczekiwana odpowiedz OpenRouter: {payload}") from exc

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "".join(parts)

    raise RuntimeError(f"Nieobslugiwany format odpowiedzi modelu: {content!r}")


def extract_json_array(raw_content: str) -> list[dict[str, Any]]:
    content = raw_content.strip()

    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    start_index = content.find("[")
    end_index = content.rfind("]")
    if start_index == -1 or end_index == -1 or end_index < start_index:
        raise RuntimeError(f"Model nie zwrocil tablicy JSON: {content}")

    try:
        parsed = json.loads(content[start_index : end_index + 1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Niepoprawny JSON od modelu: {content}") from exc

    if not isinstance(parsed, list):
        raise RuntimeError("Odpowiedz modelu nie jest tablica JSON.")

    return parsed


def normalize_tagging(
    tagging_rows: list[dict[str, Any]],
    expected_indexes: set[int],
    require_non_empty: bool = False,
) -> dict[int, list[str]]:
    normalized: dict[int, list[str]] = {}
    allowed = set(ALLOWED_TAGS)

    for row in tagging_rows:
        if not isinstance(row, dict):
            raise RuntimeError(f"Niepoprawny element odpowiedzi modelu: {row!r}")

        row_index = row.get("row_index")
        tags = row.get("tags")

        if not isinstance(row_index, int):
            raise RuntimeError(f"Brak poprawnego row_index w odpowiedzi modelu: {row!r}")
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise RuntimeError(f"Brak poprawnej listy tags w odpowiedzi modelu: {row!r}")
        if require_non_empty and not tags:
            raise RuntimeError(f"Pusta lista tags w odpowiedzi modelu dla row_index={row_index}")
        if row_index in normalized:
            raise RuntimeError(f"Powtorzony row_index w odpowiedzi modelu: {row_index}")

        cleaned_tags: list[str] = []
        for tag in tags:
            if tag not in allowed:
                raise RuntimeError(f"Niedozwolony tag '{tag}' dla row_index={row_index}")
            if tag not in cleaned_tags:
                cleaned_tags.append(tag)

        normalized[row_index] = cleaned_tags

    received_indexes = set(normalized)
    if received_indexes != expected_indexes:
        missing = sorted(expected_indexes - received_indexes)
        extra = sorted(received_indexes - expected_indexes)
        raise RuntimeError(
            f"Model zwrocil niepelny zestaw indeksow. Missing={missing}, Extra={extra}"
        )

    return normalized


def repair_missing_tags(
    payload_rows: list[dict[str, Any]],
    tagging: dict[int, list[str]],
    api_key: str,
    model: str,
) -> dict[int, list[str]]:
    missing_indexes = [row_index for row_index, tags in tagging.items() if not tags]
    if not missing_indexes:
        return tagging

    repair_rows = [row for row in payload_rows if row["row_index"] in missing_indexes]
    repair_messages = build_repair_messages(repair_rows)
    repair_response = call_openrouter(api_key, model, repair_messages)
    repair_tagging_rows = extract_json_array(repair_response)
    repaired = normalize_tagging(
        repair_tagging_rows,
        expected_indexes=set(missing_indexes),
        require_non_empty=True,
    )
    tagging.update(repaired)
    return tagging


def build_output(people: list[dict[str, str]], tagging: dict[int, list[str]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []

    for index, person in enumerate(people, start=1):
        output.append(
            {
                "name": person["name"],
                "surname": person["surname"],
                "gender": person["gender"],
                "born": int(person["birthDate"][:4]),
                "city": person["birthPlace"],
                "tags": tagging[index],
            }
        )

    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tagowanie osob z people_out.csv przez OpenRouter.")
    parser.add_argument("--model", default=os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL))
    parser.add_argument("--input", default=str(INPUT_FILE))
    parser.add_argument("--output", default=str(OUTPUT_FILE))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_env_file(ENV_FILE)

    api_key = os.getenv("API_OPEN_ROUTER_KEY")
    if not api_key:
        raise RuntimeError("Brak zmiennej API_OPEN_ROUTER_KEY w pliku .env lub srodowisku.")

    input_file = Path(args.input)
    output_file = Path(args.output)

    people = read_people(input_file)
    payload_rows = build_payload_rows(people)
    messages = build_messages(payload_rows)
    raw_response = call_openrouter(api_key, args.model, messages)
    tagging_rows = extract_json_array(raw_response)
    tagging = normalize_tagging(tagging_rows, expected_indexes=set(range(1, len(people) + 1)))
    tagging = repair_missing_tags(payload_rows, tagging, api_key, args.model)
    output_rows = build_output(people, tagging)

    output_file.write_text(json.dumps(output_rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()