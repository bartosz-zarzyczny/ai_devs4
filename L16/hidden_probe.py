#!/usr/bin/env python3
"""Helpers for probing hidden OKO user entries by SHA-256 candidate hashes."""

from __future__ import annotations

import hashlib
import os
import re
from html import unescape

import requests
from dotenv import load_dotenv

load_dotenv()

OKO_BASE_URL = "https://oko.ag3nts.org"
OKO_LOGIN = "Zofia"
OKO_PASSWORD = "Zofia2026!"
ACCESS_KEY = os.getenv("AI_DEVS_4_API_KEY", "")

MISSING_MARKERS = (
    "nie został odnaleziony",
    "nie istnieje albo został usunięty",
    "brak wpisu",
)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_candidates(raw: str | list[str]) -> list[str]:
    if isinstance(raw, list):
        items = raw
    else:
        items = re.split(r"[\r\n,;]+", raw)

    seen: set[str] = set()
    normalized: list[str] = []
    for item in items:
        value = item.strip()
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def create_authenticated_session() -> requests.Session:
    if not ACCESS_KEY:
        raise RuntimeError("Missing AI_DEVS_4_API_KEY in environment")

    session = requests.Session()
    response = session.post(
        OKO_BASE_URL + "/",
        data={
            "action": "login",
            "login": OKO_LOGIN,
            "password": OKO_PASSWORD,
            "access_key": ACCESS_KEY,
        },
        timeout=15,
        allow_redirects=True,
    )
    response.raise_for_status()

    if "Wyloguj" not in response.text and "Menu operatora" not in response.text:
        raise RuntimeError("OKO login failed")

    return session


def _strip_html(text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_main_paragraphs(html: str) -> list[str]:
    match = re.search(r"<main\b[\s\S]*?</main>", html, flags=re.IGNORECASE)
    source = match.group(0) if match else html
    paragraphs = re.findall(r"<p\b[^>]*>([\s\S]*?)</p>", source, flags=re.IGNORECASE)
    return [_strip_html(paragraph) for paragraph in paragraphs if _strip_html(paragraph)]


def _extract_heading(html: str) -> str | None:
    match = re.search(r"<h2\b[^>]*>([\s\S]*?)</h2>", html, flags=re.IGNORECASE)
    if not match:
        return None
    heading = _strip_html(match.group(1))
    return heading or None


def probe_candidates(candidates: str | list[str]) -> dict:
    session = create_authenticated_session()
    normalized = normalize_candidates(candidates)

    results = []
    fragments = []

    for candidate in normalized:
        digest = sha256_hex(candidate)
        url = f"{OKO_BASE_URL}/uzytkownicy/{digest}"
        response = session.get(url, timeout=15)
        if response.status_code not in (200, 404):
            response.raise_for_status()

        paragraphs = _extract_main_paragraphs(response.text)
        heading = _extract_heading(response.text)
        combined = " ".join(paragraphs).lower()
        is_missing = any(marker in combined for marker in MISSING_MARKERS)
        fragment = None

        if not is_missing and paragraphs:
            fragment = paragraphs[-1]
            fragments.append(fragment)

        results.append(
            {
                "candidate": candidate,
                "sha256": digest,
                "url": url,
                "status_code": response.status_code,
                "heading": heading,
                "paragraphs": paragraphs,
                "missing": is_missing,
                "fragment": fragment,
            }
        )

    return {
        "count": len(results),
        "results": results,
        "fragments": fragments,
        "joined_fragments": "".join(fragments),
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Probe hidden OKO user entries by SHA-256 candidate hash")
    parser.add_argument(
        "candidates",
        nargs="*",
        help="Candidate words to hash; if omitted, a built-in clue set is used",
    )
    args = parser.parse_args()

    defaults = ["Mickiewicz", "Miłosz", "Milosz", "Cichosza", "Cichosha"]
    payload = args.candidates or defaults
    print(json.dumps(probe_candidates(payload), ensure_ascii=False, indent=2))