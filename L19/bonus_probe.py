#!/usr/bin/env python3
"""L19 bonus - odczyt /flag/

Wskazowka: print(*map(ord,'FLAG')) -> 70 76 65 71
Flaga siedzi w /flag/ na wirtualnym filesystemie.
Strategia:
  1. Natan: zbuduj glowny filesystem (reset + createFiles)
  2. Przed done: listFiles /flag (moze sie pojawia po zbudowaniu)
  3. Proba: stworz /flag/ i listFiles
  4. Wywolaj done
"""
import os
import sys
import json
import zipfile
import re
from io import BytesIO
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

VERIFY_URL = "https://hub.ag3nts.org/verify"
TASK_NAME = "filesystem"
NATAN_ZIP_URL = "https://hub.ag3nts.org/dane/natan_notes.zip"


def get_api_key() -> str:
    key = os.environ.get("AI_DEVS_4_API_KEY", "").strip().strip('"').strip("'")
    if not key:
        raise RuntimeError("AI_DEVS_4_API_KEY not set")
    return key


def post_answer(answer) -> dict:
    payload = {"apikey": get_api_key(), "task": TASK_NAME, "answer": answer}
    resp = requests.post(VERIFY_URL, json=payload, timeout=30)
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text[:500]}


def try_list(path: str) -> dict:
    return post_answer({"action": "listFiles", "path": path})


# ---- Import helpers from task.py ----
sys.path.insert(0, str(Path(__file__).parent))
from task import (
    build_filesystem_payload,
    parse_announcements,
    parse_transactions,
    extract_persons,
    PEOPLE_MAP,
)


def build_main_payload() -> list:
    r = requests.get(NATAN_ZIP_URL, timeout=60)
    r.raise_for_status()
    zipf = zipfile.ZipFile(BytesIO(r.content))
    raw = {name: zipf.read(name).decode('utf-8', errors='replace')
           for name in zipf.namelist() if not name.endswith('/')}

    cities = parse_announcements(raw.get('ogłoszenia.txt', ''))
    transactions = parse_transactions(raw.get('transakcje.txt', ''))
    persons = extract_persons(raw.get('rozmowy.txt', ''))

    if 'lopata' in transactions:
        transactions['lopaty'] = transactions['lopata']
    if 'mlotek' in transactions and 'mlotki' not in transactions:
        transactions['mlotki'] = transactions['mlotek']
    if 'wolowina' not in transactions:
        transactions['wolowina'] = ['Opalino']

    return build_filesystem_payload(cities, persons, transactions)


if __name__ == "__main__":
    results = {}

    # Krok 1: zbuduj glowny filesystem (bez /flag/)
    print("=== Krok 1: budowanie glownego filesystemu (bez /flag/) ===")
    actions = build_main_payload()
    batch_resp = post_answer(actions)
    print(f"Batch response (first 300): {json.dumps(batch_resp, ensure_ascii=False)[:300]}")
    results['batch'] = batch_resp

    # Krok 2: done - moze system sam stworzy /flag/
    print("\n=== Krok 2: done ===")
    done_resp = post_answer({"action": "done"})
    print(json.dumps(done_resp, ensure_ascii=False, indent=2))
    results['done'] = done_resp

    # Krok 3: listFiles / po done
    print("\n=== Krok 3: listFiles / (po done) ===")
    root_after = try_list("/")
    print(json.dumps(root_after, ensure_ascii=False, indent=2))
    results['root_after_done'] = root_after

    # Krok 4: listFiles /flag po done
    print("\n=== Krok 4: listFiles /flag (po done) ===")
    flag_after = try_list("/flag")
    print(json.dumps(flag_after, ensure_ascii=False, indent=2))
    results['flag_after_done'] = flag_after

    # Krok 5: listFiles /flaga po done
    print("\n=== Krok 5: listFiles /flaga ===")
    flaga_after = try_list("/flaga")
    print(json.dumps(flaga_after, ensure_ascii=False, indent=2))
    results['flaga_after_done'] = flaga_after

    # Krok 6: listFiles /bonus po done
    print("\n=== Krok 6: listFiles /bonus ===")
    bonus_after = try_list("/bonus")
    print(json.dumps(bonus_after, ensure_ascii=False, indent=2))
    results['bonus_after_done'] = bonus_after

    # Krok 7: sprawdz listFiles dla wszystkich katalogow z /
    # (entries z root - jesli jest jakas odpowiedz)
    entries = root_after.get("entries", [])
    for entry in entries:
        name = entry.get("name")
        if name:
            print(f"\n=== listFiles /{name} ===")
            sub = try_list(f"/{name}")
            print(json.dumps(sub, ensure_ascii=False, indent=2))
            results[f'list_{name}'] = sub

    # Save
    out_file = Path(__file__).resolve().parent / "bonus_probe_responses.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nZapisano do {out_file}")
