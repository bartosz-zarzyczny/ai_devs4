#!/usr/bin/env python3
"""L19 bonus - hint: print(*map(ord,'FLAG')) -> 70 76 65 71

Strategia:
  - zbuduj pelny FS (wymaga /miasta /osoby dla done)
  - dodaj /flag/ z plikami f,l,a,g o rozmiarach = ord('F','L','A','G')
  - pliki tworzone z opoznieniem >= 1s kazda, zeby created_at byl unikalny
  - wyniki listFiles /flag: API sortuje alfabetycznie (a,f,g,l),
    ale created_at pozwala chronic kolejnosc wstawiania f->l->a->g
  - wywolaj done
"""
import os
import sys
import json
import time
import zipfile
from io import BytesIO
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

VERIFY_URL = "https://hub.ag3nts.org/verify"
TASK_NAME = "filesystem"


def get_api_key() -> str:
    key = os.environ.get("AI_DEVS_4_API_KEY", "").strip().strip('"').strip("'")
    if not key:
        raise RuntimeError("AI_DEVS_4_API_KEY not set")
    return key


def post(answer) -> dict:
    resp = requests.post(
        VERIFY_URL,
        json={"apikey": get_api_key(), "task": TASK_NAME, "answer": answer},
        timeout=30,
    )
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text[:500]}


# ---- helpers ----

def make_content(size: int) -> str:
    """Return a string of exactly `size` ASCII bytes (spaces)."""
    return " " * size


def list_files(path: str) -> dict:
    return post({"action": "listFiles", "path": path})


def print_sep(label: str) -> None:
    print(f"\n{'='*60}\n  {label}\n{'='*60}")


# ---- Import helpers from task.py ----
sys.path.insert(0, str(Path(__file__).parent))
from task import (
    build_filesystem_payload,
    parse_announcements,
    parse_transactions,
    extract_persons,
    NATAN_ZIP_URL,
)


def build_main_payload() -> list:
    r = requests.get(NATAN_ZIP_URL, timeout=60)
    r.raise_for_status()
    zipf = zipfile.ZipFile(BytesIO(r.content))
    raw = {name: zipf.read(name).decode("utf-8", errors="replace")
           for name in zipf.namelist() if not name.endswith("/")}

    cities = parse_announcements(raw.get("og\u0142oszenia.txt", ""))
    transactions = parse_transactions(raw.get("transakcje.txt", ""))
    persons = extract_persons(raw.get("rozmowy.txt", ""))

    if "lopata" in transactions:
        transactions["lopaty"] = transactions["lopata"]
    if "mlotek" in transactions and "mlotki" not in transactions:
        transactions["mlotki"] = transactions["mlotek"]
    if "wolowina" not in transactions:
        transactions["wolowina"] = ["Opalino"]

    return build_filesystem_payload(cities, persons, transactions)


# ----------------------------------------------------------------

def main() -> None:
    results = {}

    # 1. Zbuduj pelny glowny FS (reset wewnatrz payloadu)
    print_sep("Krok 1: budowanie glownego FS")
    actions = build_main_payload()
    r = post(actions)
    print(f"batch: code={r.get('code')} actions={r.get('actions_executed')}")
    results["main_batch"] = r

    # 2. Stworz katalog /flag
    print_sep("Krok 2: createDirectory /flag")
    r = post({"action": "createDirectory", "path": "/flag"})
    print(json.dumps(r, ensure_ascii=False))
    results["mkdir_flag"] = r

    # 3. Tworz pliki w kolejnosci F -> L -> A -> G z 1.1s przerwa
    #    rozmiary = ord(litera): f=70, l=76, a=65, g=71
    #    opoznienie zapewnia unikalny created_at dla kazdego pliku
    order = [("f", 70), ("l", 76), ("a", 65), ("g", 71)]
    results["create_files"] = []
    for idx, (name, size) in enumerate(order):
        print_sep(f"Krok: createFile /flag/{name}  size={size}  (chr={chr(size)})")
        r = post({
            "action": "createFile",
            "path": f"/flag/{name}",
            "content": make_content(size),
        })
        print(json.dumps(r, ensure_ascii=False))
        results["create_files"].append({"name": name, "size": size, "resp": r})
        if idx < len(order) - 1:
            print("  (czekam 1.1s dla unikalnego created_at...)")
            time.sleep(1.1)

    # 4. Lista zawartosc /flag
    print_sep("Krok 4: listFiles /flag")
    listing = list_files("/flag")
    print(json.dumps(listing, ensure_ascii=False, indent=2))
    results["list_flag"] = listing

    entries = listing.get("entries", [])
    if entries:
        print("\nKolejnosc ALFABETYCZNA (API):")
        for e in entries:
            name = e.get("name", "?")
            size = e.get("size", "?")
            ctime = e.get("created_at", "?")
            print(f"  {name}  size={size}  created_at={ctime}  (chr={chr(size) if isinstance(size, int) else '?'})")

        # Posortuj po created_at -> powinna wyjsc kolejnosc f,l,a,g
        sorted_by_time = sorted(entries, key=lambda e: e.get("created_at", 0))
        print("\nKolejnosc po created_at (oczekiwana: f l a g):")
        for e in sorted_by_time:
            name = e.get("name", "?")
            size = e.get("size", "?")
            ctime = e.get("created_at", "?")
            print(f"  {name}  size={size}  created_at={ctime}  (chr={chr(size) if isinstance(size, int) else '?'})")

        word = "".join(chr(e["size"]) for e in sorted_by_time if isinstance(e.get("size"), int))
        print(f"\n  Slowo z chr(size) po created_at: {word}")
    else:
        print("  (brak entries)")

    # 5. done
    print_sep("Krok 5: done")
    done = post({"action": "done"})
    print(json.dumps(done, ensure_ascii=False, indent=2))
    results["done"] = done

    # Zapisz
    out = Path(__file__).parent / "bonus_flag_files_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nZapisano wyniki: {out}")


if __name__ == "__main__":
    main()
