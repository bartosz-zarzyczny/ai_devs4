#!/usr/bin/env python3
"""L23 - shellaccess: eksploracja katalogu /data na zdalnym serwerze przez shell API.

Wysyla komendy powloki jako answer.cmd do POST https://hub.ag3nts.org/verify
z task="shellaccess". Exploruje katalog /data, szuka informacji o Rafale,
wylicza dzien wczesniejszy i zwraca finalny JSON z data/city/longitude/latitude.

Usage:
    python L23/task.py            # pelny automatyczny solver
    python L23/task.py --explore  # tylko eksploracja /data, bez submitu
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
import os

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

L23_DIR = Path(__file__).resolve().parent
load_dotenv(L23_DIR.parent / ".env")

API_KEY = os.environ["AI_DEVS_4_API_KEY"]
VERIFY_URL = "https://hub.ag3nts.org/verify"
TASK = "shellaccess"

OPERATION_LOG = L23_DIR / "operation_log.jsonl"
FINDINGS_FILE = L23_DIR / "findings.json"
RESULT_FILE = L23_DIR / "verification_result.json"

CALL_DELAY = 2.0  # sekundy miedzy wywolaniami, zeby nie przekroczyc rate limitu
_last_call: float = 0.0


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

def shell_cmd(cmd: str) -> str:
    """Wyslij komende powloki do zdalnego serwera. Zwraca tekst wyjscia."""
    global _last_call
    elapsed = time.time() - _last_call
    if elapsed < CALL_DELAY:
        time.sleep(CALL_DELAY - elapsed)

    payload = {
        "apikey": API_KEY,
        "task": TASK,
        "answer": {"cmd": cmd},
    }

    try:
        resp = requests.post(VERIFY_URL, json=payload, timeout=30)
    except requests.RequestException as exc:
        return f"[network error] {exc}"
    finally:
        _last_call = time.time()

    _log_operation(cmd, resp)

    if resp.status_code == 200:
        try:
            body = resp.json()
        except ValueError:
            return resp.text

        # Hub moze zwrocic flage - zapisz od razu
        msg = body.get("message", "")
        if "{FLG:" in str(msg):
            _save_result(body)
            print(f"[FLAG] {msg}")

        # Wydobadz pole output lub message
        output = body.get("output") or body.get("data") or body.get("message", "")
        if isinstance(output, list):
            return "\n".join(str(x) for x in output)
        return str(output)

    if resp.status_code == 429:
        wait = 30
        try:
            wait = int(resp.json().get("retry_after", 30))
        except Exception:
            pass
        print(f"[rate limit] czekam {wait}s")
        time.sleep(wait)
        _last_call = time.time()
        return f"[rate limit] {resp.status_code}"

    try:
        body = resp.json()
        return f"[error {resp.status_code}] {json.dumps(body, ensure_ascii=False)}"
    except Exception:
        return f"[error {resp.status_code}] {resp.text[:400]}"


def _log_operation(cmd: str, resp: requests.Response) -> None:
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text[:800]}
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cmd": cmd,
        "http_status": resp.status_code,
        "response": body,
    }
    with OPERATION_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _save_result(body: dict) -> None:
    RESULT_FILE.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[result] zapisano do {RESULT_FILE.name}")


def _save_findings(data: dict) -> None:
    FINDINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Discovery pipeline
# ---------------------------------------------------------------------------

def explore_data() -> dict:
    """Eksploruje /data i zbiera ustalenia posrednie. Zwraca słownik findings."""
    print("=== Eksploracja /data ===")
    findings: dict = {}

    # 1. Gdzie jestesmy i co mamy
    print("[1] pwd + ls /data")
    findings["pwd"] = shell_cmd("pwd")
    findings["ls_data"] = shell_cmd("ls -la /data")
    print(findings["ls_data"])

    # 2. Typy plikow
    print("[2] find /data - wszystkie pliki")
    findings["find_all"] = shell_cmd("find /data -type f | head -60")
    print(findings["find_all"])

    # 3. Szukamy slow kluczowych zwiazanych z Rafałem
    print("[3] grep Rafal")
    findings["grep_rafal"] = shell_cmd("grep -ril 'rafal\\|Rafał\\|rafał' /data 2>/dev/null | head -20")
    print(findings["grep_rafal"])

    # 4. Szukamy slow kluczowych: znaleziono, cialo, body, found
    print("[4] grep znaleziono/cialo/body/found")
    findings["grep_found"] = shell_cmd(
        "grep -ril 'znaleziono\\|ciało\\|cialo\\|body found\\|found body\\|odnalezion' /data 2>/dev/null | head -20"
    )
    print(findings["grep_found"])

    _save_findings(findings)
    return findings


def narrow_search(findings: dict) -> dict:
    """Na podstawie wstepnych ustalen zaweza poszukiwania."""
    print("=== Zawezanie poszukiwan ===")

    # Zbierz liste interesujacych plikow
    candidate_files: list[str] = []
    for key in ("grep_rafal", "grep_found"):
        val = findings.get(key, "")
        for line in val.splitlines():
            line = line.strip()
            if line and line.startswith("/"):
                candidate_files.append(line)

    # Jesli nie ma kandydatow, sprobuj szerszego szukania
    if not candidate_files:
        print("[!] Brak kandydatow z grep - szerokie szukanie")
        out = shell_cmd("grep -ril 'rafal\\|rafał\\|Rafal\\|location\\|coordinates\\|wspolrz' /data 2>/dev/null | head -30")
        print(out)
        for line in out.splitlines():
            line = line.strip()
            if line and line.startswith("/"):
                candidate_files.append(line)

    findings["candidate_files"] = list(set(candidate_files))
    print(f"[narrow] kandydaci: {findings['candidate_files']}")

    # Odczytaj zawartosc kandydatow
    contents: dict = {}
    for fpath in findings["candidate_files"][:10]:
        print(f"[read] {fpath}")
        ext = fpath.rsplit(".", 1)[-1].lower() if "." in fpath else ""
        if ext == "json":
            out = shell_cmd(f"cat '{fpath}'")
        else:
            out = shell_cmd(f"cat '{fpath}'")
        contents[fpath] = out
        print(out[:500])

    findings["file_contents"] = contents
    _save_findings(findings)
    return findings


def extract_answer(findings: dict) -> dict | None:
    """Probuje wydobyc date, miasto i wspolrzedne z ustalen. Zwraca slownik lub None."""
    print("=== Ekstrakcja odpowiedzi ===")

    # Proby wyciagniecia danych przez grep bezposrednio z /data
    date_candidates: list[str] = []
    city_candidates: list[str] = []
    lon_candidates: list[str] = []
    lat_candidates: list[str] = []

    # Szukaj dat w formatach YYYY-MM-DD lub DD.MM.YYYY
    out = shell_cmd("grep -roh '[0-9]\\{4\\}-[0-9]\\{2\\}-[0-9]\\{2\\}' /data 2>/dev/null | head -30")
    date_candidates = [d.strip() for d in out.splitlines() if d.strip()]
    print(f"[dates] {date_candidates}")

    # Szukaj wspolrzednych (decimal degrees)
    out = shell_cmd("grep -roh '[0-9]\\{1,3\\}\\.[0-9]\\{4,8\\}' /data 2>/dev/null | head -30")
    coord_candidates = [c.strip() for c in out.splitlines() if c.strip()]
    print(f"[coords] {coord_candidates}")

    # Szukaj nazw miast przez kontekst
    out = shell_cmd("grep -roi 'city.*:\\|miasto.*:\\|\\\"city\\\".*:\\|\\\"miasto\\\".*:' /data 2>/dev/null | head -20")
    print(f"[city grep] {out}")
    city_candidates = [c.strip() for c in out.splitlines() if c.strip()]

    # Szukaj lon/lat explicite
    out_lon = shell_cmd("grep -roi 'longitude\\|lon\\b' /data 2>/dev/null | head -20")
    out_lat = shell_cmd("grep -roi 'latitude\\|lat\\b' /data 2>/dev/null | head -20")
    print(f"[lon] {out_lon[:300]}")
    print(f"[lat] {out_lat[:300]}")

    findings["date_candidates"] = date_candidates
    findings["coord_candidates"] = coord_candidates
    findings["city_candidates"] = city_candidates
    _save_findings(findings)

    # Jesli nie udalo sie zebrac danych, zwroc None - user musi zajrzec do findings
    if not date_candidates or not coord_candidates:
        print("[!] Nie udalo sie automatycznie wydobyc wszystkich danych.")
        print(f"    Sprawdz {FINDINGS_FILE.name} i uruchom manualny UI.")
        return None

    return None  # do uzupelnienia po inspekcji


# ---------------------------------------------------------------------------
# Finalny submit
# ---------------------------------------------------------------------------

def build_and_submit(day: str, city: str, longitude: float, latitude: float) -> dict:
    """Buduje finalny JSON i wysyla go przez echo na zdalnym shellu."""
    answer_json = json.dumps({
        "date": day,
        "city": city,
        "longitude": longitude,
        "latitude": latitude,
    }, ensure_ascii=False)
    # Escapowanie cudzyslowow dla powloki
    answer_escaped = answer_json.replace("'", "'\\''")
    cmd = f"echo '{answer_escaped}'"
    print(f"[submit] cmd: {cmd}")
    output = shell_cmd(cmd)
    print(f"[submit] output huba: {output}")

    # Sprawdz czy dostalismy flage z ostatniego wpisu logu
    if RESULT_FILE.exists():
        return json.loads(RESULT_FILE.read_text(encoding="utf-8"))
    return {"output": output}


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

def run_solver() -> dict:
    print("=== Shellaccess solver ===")
    findings = explore_data()
    findings = narrow_search(findings)
    extract_answer(findings)
    print(f"\nUstalenia zapisano do {FINDINGS_FILE.name}")
    print("Jesli solver nie wydobyl danych automatycznie, uzyj UI do inspekcji.")
    return findings


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="L23 shellaccess solver")
    parser.add_argument("--explore", action="store_true", help="Tylko eksploracja bez submitu")
    args = parser.parse_args()

    if args.explore:
        findings = explore_data()
        findings = narrow_search(findings)
        extract_answer(findings)
    else:
        run_solver()


if __name__ == "__main__":
    main()
