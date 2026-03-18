#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

import requests

from failure_fetch import count_tokens, get_api_key

L08_DIR = Path(__file__).resolve().parent
RESULT_FILE = L08_DIR / "hidden_flag_result.json"
PROBE_SEQUENCE = [70, 76, 65, 71]
PROBE_LINE_COUNT = 11


def make_exact_token_text(total_tokens: int, line_count: int = PROBE_LINE_COUNT) -> str:
    if line_count < 1:
        raise ValueError("line_count must be positive")

    # Each newline is tokenized too, so budget for separators explicitly.
    words_total = total_tokens - (line_count - 1)
    if words_total < line_count:
        raise ValueError(f"Cannot build {total_tokens} tokens with {line_count} lines")

    base, extra = divmod(words_total, line_count)
    parts: list[str] = []
    for index in range(line_count):
        word_count = base + (1 if index < extra else 0)
        parts.append("x " * (word_count - 1) + "x")

    text = "\n".join(parts)
    if count_tokens(text) != total_tokens:
        raise AssertionError((count_tokens(text), total_tokens))
    return text


def build_probe_file(total_tokens: int, output_dir: Path | None = None) -> Path:
    directory = output_dir if output_dir is not None else L08_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"hidden_probe_{total_tokens}.log"
    path.write_text(make_exact_token_text(total_tokens), encoding="utf-8")
    return path


def submit_hidden_probe(log_text: str) -> dict:
    payload = {
        "apikey": get_api_key(),
        "task": "failure",
        "answer": json.dumps({"logs": log_text}, ensure_ascii=False),
    }
    response = requests.post("https://hub.ag3nts.org/verify", json=payload, timeout=120)
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    data["status_code"] = response.status_code
    return data


def extract_secret_flag(response: object) -> str | None:
    serialized = json.dumps(response, ensure_ascii=False) if isinstance(response, dict) else str(response)
    match = re.search(r"\{FLG:[^}]+\}", serialized)
    return match.group(0) if match else None


def run_hidden_flag_probe(sequence: list[int] | None = None, output_dir: Path | None = None) -> dict:
    sequence = sequence or PROBE_SEQUENCE
    history: list[dict] = []
    hidden_flag = None

    for expected_token_count in sequence:
        probe_path = build_probe_file(expected_token_count, output_dir=output_dir)
        probe_text = probe_path.read_text(encoding="utf-8")
        response = submit_hidden_probe(probe_text)
        flag = extract_secret_flag(response)

        history.append(
            {
                "token_count": expected_token_count,
                "line_count": probe_text.count("\n") + 1,
                "path": str(probe_path),
                "response": response,
                "letter": response.get("letter") if isinstance(response, dict) else None,
                "flag": flag,
            }
        )

        if flag:
            hidden_flag = flag
            break

    result = {
        "sequence": sequence,
        "history": history,
        "hidden_flag": hidden_flag,
        "success": hidden_flag is not None,
    }
    RESULT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["result_file"] = str(RESULT_FILE)
    return result


if __name__ == "__main__":
    result = run_hidden_flag_probe()
    print(json.dumps(result, ensure_ascii=False, indent=2))