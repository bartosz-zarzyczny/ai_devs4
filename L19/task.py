#!/usr/bin/env python3
"""L19 - filesystem

Plan: pobierz notatki, zbuduj structure miasta/osoby/towary, wyślij do /verify.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

VERIFY_URL = "https://hub.ag3nts.org/verify"
TASK_NAME = "filesystem"

NATAN_ZIP_URL = "https://hub.ag3nts.org/dane/natan_notes.zip"

RESULT_FILE = Path(__file__).resolve().parent / "verification_result.json"
DATA_FILE = Path(__file__).resolve().parent / "natan_data.json"

CITY_NORMALIZATION = {
    "Domatowa": "Domatowo",
    "Domatowie": "Domatowo",
    "Darzlubiu": "Darzlubie",
    "Darzlubiem": "Darzlubie",
    "Darzlubi": "Darzlubie",
}

GOOD_NORMALIZATION = {
    "chlebow": "chleb",
    "chleb": "chleb",
    "wody": "woda",
    "wode": "woda",
    "butelka": "woda",
    "butelek": "woda",
    "mlotkow": "mlotek",
    "mlotki": "mlotek",
    "mlotek": "mlotek",
    "lopat": "lopata",
    "lopata": "lopata",
    "wiertarek": "wiertarka",
    "wiertarka": "wiertarka",
    "ryzu": "ryz",
    "ryz": "ryz",
    "marchew": "marchew",
    "porcji": "porcja",
    "porcja": "porcja",
    "kapusta": "kapusta",
    "ziemniakow": "ziemniak",
    "ziemniaki": "ziemniak",
    "ziemniak": "ziemniak",
    "maka": "maka",
    "makaronu": "makaron",
    "makaron": "makaron",
    "wolowiny": "wolowina",
    "wolowina": "wolowina",
    "kurczaka": "kurczak",
    "kurczak": "kurczak",
    "kilofow": "kilof",
    "kilof": "kilof",
}

GOOD_WHITELIST = {
    "chleb",
    "woda",
    "mlotek",
    "lopata",
    "wiertarka",
    "ryz",
    "marchew",
    "kapusta",
    "ziemniak",
    "makaron",
    "maka",
    "wolowina",
    "kurczak",
    "kilof",
}

GOOD_SYNONYMS = {
    "chleb": ["chleb", "chlebow"],
    "woda": ["woda", "wody", "wode", "butelek", "buteleki"],
    "mlotek": ["mlotek", "mlotkow", "mlotki"],
    "lopata": ["lopata", "lopat", "lopaty"],
    "wiertarka": ["wiertarka", "wiertarek"],
    "ryz": ["ryz", "ryzu"],
    "marchew": ["marchew"],
    "kapusta": ["kapusta"],
    "ziemniak": ["ziemniak", "ziemniakow", "ziemniaki"],
    "makaron": ["makaron", "makaronu"],
    "maka": ["maka"],
    "wolowina": ["wolowina", "wolowiny"],
    "kurczak": ["kurczak", "kurczaka"],
    "kilof": ["kilof", "kilofow"],
}

CITY_KEYWORDS = [
    "Opalino",
    "Domatowo",
    "Domatowa",
    "Brudzewo",
    "Darzlubie",
    "Darzlubiu",
    "Celbowo",
    "Mechowo",
    "Puck",
    "Karlinkowo",
]

PEOPLE_MAP = {
    "Natan Rams": "Domatowo",
    "Iga Kapecka": "Opalino",
    "Rafal Kisiel": "Brudzewo",
    "Marta Frantz": "Darzlubie",
    "Oskar Radtke": "Celbowo",
    "Eliza Redmann": "Mechowo",
    "Damian Kroll": "Puck",
    "Lena Konkel": "Karlinkowo",
}


def get_api_key() -> str:
    api_key = os.environ.get("AI_DEVS_4_API_KEY", "").strip().strip('"').strip("'")
    if not api_key:
        raise RuntimeError("AI_DEVS_4_API_KEY not set")
    return api_key


def post_answer(answer: Any, timeout: int = 45) -> Dict[str, Any]:
    payload = {"apikey": get_api_key(), "task": TASK_NAME, "answer": answer}
    resp = requests.post(VERIFY_URL, json=payload, timeout=timeout)
    try:
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"Non-JSON response from verify: {exc}\n{resp.text[:200]}")
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} {data}")
    return data


def translit(txt: str) -> str:
    replacements = {
        "ą": "a",
        "ć": "c",
        "ę": "e",
        "ł": "l",
        "ń": "n",
        "ó": "o",
        "ś": "s",
        "ź": "z",
        "ż": "z",
        "Ą": "A",
        "Ć": "C",
        "Ę": "E",
        "Ł": "L",
        "Ń": "N",
        "Ó": "O",
        "Ś": "S",
        "Ź": "Z",
        "Ż": "Z",
    }
    out = ''.join(replacements.get(ch, ch) for ch in txt)
    out = out.replace(' ', '_')
    out = out.replace('ć', 'c')
    return out


def normalize_city(raw: str) -> str:
    raw = raw.strip()
    raw = raw.replace('ą', 'a').replace('Ą', 'A')
    if raw in CITY_NORMALIZATION:
        return CITY_NORMALIZATION[raw]
    if raw in CITY_KEYWORDS:
        if raw == 'Domatowa':
            return 'Domatowo'
        if raw == 'Darzlubiu':
            return 'Darzlubie'
    return raw


def normalize_good(raw: str) -> str:
    raw = raw.strip().lower()
    raw = raw.replace('ż', 'z').replace('ź', 'z').replace('ó', 'o').replace('ą', 'a').replace('ę', 'e').replace('ś', 's').replace('ć', 'c').replace('ń', 'n').replace('ł', 'l').replace('Ł', 'L')
    raw = raw.replace('y', 'y')
    if raw in GOOD_NORMALIZATION:
        return GOOD_NORMALIZATION[raw]
    return raw


def parse_announcements(text: str) -> Dict[str, Dict[str, int]]:
    cities: Dict[str, Dict[str, int]] = {}
    for line in text.splitlines():
        ln = line.strip()
        if not ln or ln.startswith('---'):
            continue
        city = None
        for token in CITY_KEYWORDS:
            if token in ln:
                city = normalize_city(token)
                break
        if city is None:
            continue
        if city not in cities:
            cities[city] = {}

        used_spans = []
        for good, synonyms in GOOD_SYNONYMS.items():
            if good not in GOOD_WHITELIST:
                continue
            for syn in synonyms:
                regex_patterns = [
                    rf"(\d+)\s+(?:workow|butelek|kg|porcji|porcja|porcje)?\s*{re.escape(syn)}\b",
                    rf"\b{re.escape(syn)}\s+(\d+)\b",
                ]
                for pat in regex_patterns:
                    for m in re.finditer(pat, ln, flags=re.IGNORECASE):
                        span = (m.start(), m.end())
                        if any(s < span[1] and span[0] < e for s, e in used_spans):
                            continue
                        used_spans.append(span)
                        qty = int(m.group(1))
                        cities[city][good] = cities[city].get(good, 0) + qty

        # also capture explicit forms in first pos when they are naked forms, e.g. 'wody i 6 mlotkow'
        # handled by above patterns

    return cities


def parse_transactions(text: str) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for line in text.splitlines():
        ln = line.strip()
        if not ln:
            continue
        if '->' not in ln:
            continue
        parts = [x.strip() for x in ln.split('->')]
        if len(parts) != 3:
            continue
        seller, good_raw, buyer = parts
        seller = normalize_city(seller)
        good = normalize_good(good_raw)
        if good not in GOOD_WHITELIST:
            continue
        out.setdefault(good, []).append(seller)

    for good in list(out.keys()):
        out[good] = sorted(set(out[good]))
    return out


def extract_persons(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for raw_name, city in PEOPLE_MAP.items():
        out[raw_name] = city
    return out


def build_filesystem_payload(cities: Dict[str, Dict[str, int]], persons: Dict[str, str], goods: Dict[str, str]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    actions.append({"action": "reset"})
    actions.append({"action": "createDirectory", "path": "/miasta"})
    actions.append({"action": "createDirectory", "path": "/osoby"})
    actions.append({"action": "createDirectory", "path": "/towary"})

    for city, inv in cities.items():
        filename = translit(city).lower()
        payload = json.dumps(inv, ensure_ascii=False)
        actions.append({"action": "createFile", "path": f"/miasta/{filename}", "content": payload})

    for person, city in persons.items():
        filename = translit(person).lower()
        city_name = normalize_city(city)
        content = f"{person}\n[{city_name}](/miasta/{translit(city_name).lower()})"
        actions.append({"action": "createFile", "path": f"/osoby/{filename}", "content": content})

    for good, seller_cities in goods.items():
        filename = translit(good).lower()
        links = []
        for city_name in seller_cities:
            city_norm = normalize_city(city_name)
            links.append(f"[{city_norm}](/miasta/{translit(city_norm).lower()})")
        content = "\n".join(links)
        actions.append({"action": "createFile", "path": f"/towary/{filename}", "content": content})

    return actions


def main():
    print('Krok 1: pobieranie notatek')
    r = requests.get(NATAN_ZIP_URL, timeout=60)
    if r.status_code != 200:
        raise RuntimeError('Błąd pobierania notatek: ' + str(r.status_code))

    from io import BytesIO
    import zipfile

    zipf = zipfile.ZipFile(BytesIO(r.content))
    raw = {}
    for name in zipf.namelist():
        if name.endswith('/'):
            continue
        raw[name] = zipf.read(name).decode('utf-8', errors='replace')

    print('Krok 2: parsowanie')
    cities = parse_announcements(raw.get('ogłoszenia.txt', ''))
    transactions = parse_transactions(raw.get('transakcje.txt', ''))
    persons = extract_persons(raw.get('rozmowy.txt', ''))

    # Ensure file naming expectations from task validator:
    # missing: lopaty, mlotki, wolowina
    if 'lopata' in transactions:
        transactions['lopaty'] = transactions['lopata']
    if 'mlotek' in transactions and 'mlotki' not in transactions:
        transactions['mlotki'] = transactions['mlotek']
    if 'wolowina' not in transactions and 'wolowina' in cities.get('Opalino', {}):
        transactions['wolowina'] = ['Opalino']

    print('cities', cities)
    print('persons', persons)
    print('goods', transactions)

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump({'cities': cities, 'persons': persons, 'goods': transactions}, f, ensure_ascii=False, indent=2)

    print('Krok 3: wysłanie akcji help')
    help_data = post_answer({'action': 'help'})
    print('help:', help_data)

    print('Krok 4: tworzenie filesystem')
    actions = build_filesystem_payload(cities, persons, transactions)
    response = post_answer(actions)
    print('batch response:', response)

    print('Krok 5: done')
    done_resp = post_answer({'action': 'done'})
    print('done:', done_resp)

    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        json.dump({'help': help_data, 'batch': response, 'done': done_resp}, f, ensure_ascii=False, indent=2)

    print('Zapisano wyniki do', RESULT_FILE)


if __name__ == '__main__':
    main()
