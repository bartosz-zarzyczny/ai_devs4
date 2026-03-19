from __future__ import annotations

import base64
import json
import os
import re
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib import error, request


REPO_ROOT = Path(__file__).resolve().parent.parent
ZMAIL_URL = "https://hub.ag3nts.org/api/zmail"
VERIFY_URL = "https://hub.ag3nts.org/verify"


def _read_env_file(path: Path, key: str) -> str | None:
    if not path.exists():
        return None

    prefix = f"{key}="
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.startswith(prefix):
            continue
        value = line[len(prefix):].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        return value
    return None


def get_api_key() -> str:
    env_key = os.getenv("AI_DEVS_4_API_KEY")
    if env_key:
        return env_key.strip().strip('"').strip("'")

    for candidate in (REPO_ROOT / ".env", REPO_ROOT / ".env_copy"):
        file_key = _read_env_file(candidate, "AI_DEVS_4_API_KEY")
        if file_key:
            return file_key

    raise RuntimeError("Brak AI_DEVS_4_API_KEY w .env lub środowisku.")


def call_zmail(payload: dict[str, Any]) -> dict[str, Any]:
    request_body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        ZMAIL_URL,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"zmail HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Nie udało się połączyć z zmail: {exc}") from exc

    return json.loads(raw)


def zmail_help() -> dict[str, Any]:
    return call_zmail({"apikey": get_api_key(), "action": "help", "page": 1})


def zmail_get_inbox(page: int = 1, per_page: int = 5) -> dict[str, Any]:
    return call_zmail(
        {
            "apikey": get_api_key(),
            "action": "getInbox",
            "page": page,
            "perPage": per_page,
        }
    )


def zmail_get_thread(thread_id: int) -> dict[str, Any]:
    return call_zmail({"apikey": get_api_key(), "action": "getThread", "threadID": thread_id})


def zmail_get_messages(ids: Any) -> dict[str, Any]:
    return call_zmail({"apikey": get_api_key(), "action": "getMessages", "ids": ids})


def zmail_search(query: str, page: int = 1, per_page: int = 5) -> dict[str, Any]:
    return call_zmail(
        {
            "apikey": get_api_key(),
            "action": "search",
            "query": query,
            "page": page,
            "perPage": per_page,
        }
    )


def zmail_reset() -> dict[str, Any]:
    return call_zmail({"apikey": get_api_key(), "action": "reset"})


def verify_mailbox_answer(password: str, date: str, confirmation_code: str) -> dict[str, Any]:
    payload = {
        "apikey": get_api_key(),
        "task": "mailbox",
        "answer": {
            "password": password,
            "date": date,
            "confirmation_code": confirmation_code,
        },
    }
    request_body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        VERIFY_URL,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"verify HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Nie udało się połączyć z verify: {exc}") from exc

    return json.loads(raw)


def decode_gaderypoluki(text: str) -> str:
    mapping = str.maketrans({
        "A": "G",
        "G": "A",
        "D": "E",
        "E": "D",
        "R": "Y",
        "Y": "R",
        "P": "O",
        "O": "P",
        "L": "U",
        "U": "L",
        "K": "I",
        "I": "K",
    })
    return text.translate(mapping)


def extract_zip_attachment(base64_data: str) -> dict[str, str]:
    prefix = "base64,"
    encoded = base64_data.split(prefix, 1)[1] if prefix in base64_data else base64_data
    archive_bytes = base64.b64decode(encoded)

    extracted: dict[str, str] = {}
    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        for name in archive.namelist():
            with archive.open(name) as handle:
                extracted[name] = handle.read().decode("utf-8", errors="replace")
    return extracted


def solve_bonus_flag() -> dict[str, Any]:
    search_queries = ["flag", "Zygfryda", "wandalizmu", "holu"]
    seen_message_ids: set[str] = set()
    candidates: list[dict[str, Any]] = []

    for query in search_queries:
        response = zmail_search(query=query, page=1, per_page=10)
        for item in response.get("items", []):
            message_id = item.get("messageID")
            if not message_id or message_id in seen_message_ids:
                continue
            seen_message_ids.add(message_id)
            candidates.append(item)

    attachment_source = None
    attachment_name = None
    extracted_files: dict[str, str] = {}

    for candidate in candidates:
        message_id = candidate.get("messageID")
        if not message_id:
            continue
        message_response = zmail_get_messages([message_id])
        for message in message_response.get("items", []):
            attachments = message.get("attachment") or []
            for attachment in attachments:
                filename = attachment.get("filename", "")
                data = attachment.get("data", "")
                if filename.lower().endswith(".zip") and data:
                    attachment_source = message
                    attachment_name = filename
                    extracted_files = extract_zip_attachment(data)
                    break
            if extracted_files:
                break
        if extracted_files:
            break

    decoded_files = {
        name: decode_gaderypoluki(content)
        for name, content in extracted_files.items()
    }

    raw_flag = None
    decoded_flag = None
    for content in extracted_files.values():
        match = re.search(r"\{[^{}]+\}", content)
        if match:
            raw_flag = match.group(0)
            break
    for content in decoded_files.values():
        match = re.search(r"\{[^{}]+\}", content)
        if match:
            decoded_flag = match.group(0)
            break

    return {
        "queries": search_queries,
        "candidates": candidates,
        "attachment_source": attachment_source,
        "attachment_name": attachment_name,
        "extracted_files": extracted_files,
        "decoded_files": decoded_files,
        "raw_flag": raw_flag,
        "bonus_flag": decoded_flag,
    }
