#!/usr/bin/env python3
"""L11 - evaluation: find sensor anomalies and report them to the hub."""

from __future__ import annotations

import io
import json
import os
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_KEY = os.environ["AI_DEVS_4_API_KEY"]
OPENROUTER_KEY = os.environ["API_OPEN_ROUTER_KEY"]

HUB_VERIFY_URL = "https://hub.ag3nts.org/verify"
SENSORS_ZIP_URL = "https://hub.ag3nts.org/dane/sensors.zip"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_MODEL = "openai/gpt-4o-mini"

L11_DIR = Path(__file__).resolve().parent
SENSORS_ZIP = L11_DIR / "sensors.zip"
ANOMALIES_FILE = L11_DIR / "anomalies.json"
VERIFICATION_FILE = L11_DIR / "verification_result.json"

# Sensor field mapping: sensor_type_name -> (json_field, min_value, max_value)
SENSOR_RULES: dict[str, tuple[str, float, float]] = {
    "temperature": ("temperature_K", 553.0, 873.0),
    "pressure": ("pressure_bar", 60.0, 160.0),
    "water": ("water_level_meters", 5.0, 15.0),
    "voltage": ("voltage_supply_v", 229.0, 231.0),
    "humidity": ("humidity_percent", 40.0, 80.0),
}
ALL_SENSOR_FIELDS = {v[0] for v in SENSOR_RULES.values()}


# ---------------------------------------------------------------------------
# Step 1: Download sensors.zip (single file, no extraction)
# ---------------------------------------------------------------------------

def download_zip() -> None:
    if SENSORS_ZIP.exists():
        print(f"[skip] {SENSORS_ZIP.name} already present ({SENSORS_ZIP.stat().st_size // 1024} KB)")
        return
    print(f"[download] {SENSORS_ZIP_URL}")
    resp = requests.get(SENSORS_ZIP_URL, timeout=60)
    resp.raise_for_status()
    SENSORS_ZIP.write_bytes(resp.content)
    print(f"[download] saved {len(resp.content) // 1024} KB -> {SENSORS_ZIP}")


def iter_sensors(zip_path: Path):
    """Yield (file_id, raw_text, data_dict) for every .json entry in the zip."""
    with zipfile.ZipFile(zip_path) as zf:
        for name in sorted(zf.namelist()):
            if not name.endswith(".json"):
                continue
            file_id = Path(name).stem
            raw = zf.read(name).decode("utf-8")
            try:
                data = json.loads(raw)
            except Exception as exc:
                yield file_id, raw, None, str(exc)
                continue
            yield file_id, raw, data, None


# ---------------------------------------------------------------------------
# Step 2: Programmatic anomaly detection
# ---------------------------------------------------------------------------

def parse_active_sensors(sensor_type: str) -> list[str]:
    return [s.strip().lower() for s in sensor_type.split("/") if s.strip()]


def check_programmatic(data: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    active_sensors = parse_active_sensors(data.get("sensor_type", ""))

    active_fields: set[str] = set()
    for sensor_name in active_sensors:
        if sensor_name not in SENSOR_RULES:
            reasons.append(f"unknown sensor type: {sensor_name!r}")
            continue
        field, lo, hi = SENSOR_RULES[sensor_name]
        active_fields.add(field)
        value = data.get(field, 0)
        if value == 0:
            reasons.append(f"{field}=0 but sensor '{sensor_name}' is active")
        elif not (lo <= value <= hi):
            reasons.append(f"{field}={value} outside range [{lo}, {hi}]")

    for field in ALL_SENSOR_FIELDS:
        if field not in active_fields:
            value = data.get(field, 0)
            if value != 0:
                reasons.append(f"{field}={value} but sensor is inactive (expected 0)")

    return reasons


def run_checks_from_zip(zip_path: Path) -> tuple[
    dict[str, list[str]],   # programmatic_anomalies
    dict[str, str],          # clean_file_notes  {file_id: operator_note}
    dict[str, str],          # all_raw_lines3    {file_id: line3 raw text}  (for bonus)
    int,                     # total count
]:
    """
    Single-pass scan of the ZIP: run programmatic checks and collect notes for LLM.
    Returns anomalies, notes of clean files, line-3 raw texts, and total file count.
    """
    programmatic_anomalies: dict[str, list[str]] = {}
    clean_file_notes: dict[str, str] = {}
    raw_lines3: dict[str, str] = {}
    total = 0

    with zipfile.ZipFile(zip_path) as zf:
        names = sorted(n for n in zf.namelist() if n.endswith(".json"))
        total = len(names)
        for name in names:
            file_id = Path(name).stem
            raw = zf.read(name).decode("utf-8")
            lines = raw.splitlines()
            # Capture line 3 for bonus AWK decoding
            if len(lines) >= 3:
                raw_lines3[file_id] = lines[2]

            try:
                data = json.loads(raw)
            except Exception as exc:
                programmatic_anomalies[file_id] = [f"JSON parse error: {exc}"]
                continue

            reasons = check_programmatic(data)
            if reasons:
                programmatic_anomalies[file_id] = reasons
            else:
                clean_file_notes[file_id] = data.get("operator_notes", "")

    print(f"[programmatic] {len(programmatic_anomalies)} anomalies, {len(clean_file_notes)} clean files")
    return programmatic_anomalies, clean_file_notes, raw_lines3, total


# ---------------------------------------------------------------------------
# Step 3: LLM-based operator note classification
# ---------------------------------------------------------------------------

def call_llm(messages: list[dict], max_tokens: int = 512) -> str:
    resp = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": LLM_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def classify_notes_batch(indexed_notes: list[tuple[int, str]]) -> set[int]:
    lines = "\n".join(f'{i}: "{note}"' for i, note in indexed_notes)
    system = (
        "You are a sensor data quality checker. "
        "You will receive a numbered list of operator notes from sensor logfiles. "
        "Your task: identify which notes indicate that the operator found a problem, "
        "anomaly, error, or anything unusual. "
        "Notes saying everything is fine, stable, OK, or within expected range are NOT problems. "
        "Respond ONLY with a JSON array of the integer indices of problematic notes. "
        "Example: [0, 3, 7]. If none are problematic, respond with []."
    )
    raw = call_llm(
        [{"role": "system", "content": system}, {"role": "user", "content": f"Operator notes:\n{lines}"}]
    )
    raw = raw.strip()
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1:
        return set()
    try:
        return set(int(i) for i in json.loads(raw[start : end + 1]))
    except (json.JSONDecodeError, ValueError):
        return set()


def run_note_checks(clean_file_notes: dict[str, str], batch_size: int = 100) -> dict[str, str]:
    """
    Classify operator notes of clean files via LLM. Deduplicates to minimise cost.
    Returns {file_id: note} for files whose note indicates a problem.
    """
    note_to_ids: dict[str, list[str]] = defaultdict(list)
    for fid, note in clean_file_notes.items():
        note_to_ids[note].append(fid)

    unique_notes = list(note_to_ids.keys())
    print(f"[llm] {len(clean_file_notes)} clean files -> {len(unique_notes)} unique notes")

    note_is_problem: dict[str, bool] = {}
    for batch_start in range(0, len(unique_notes), batch_size):
        batch = unique_notes[batch_start : batch_start + batch_size]
        indexed = list(enumerate(batch))
        end_idx = batch_start + len(batch)
        print(f"[llm] classifying notes {batch_start+1}-{end_idx}/{len(unique_notes)} ...")
        bad_indices = classify_notes_batch(indexed)
        for i, note in indexed:
            note_is_problem[note] = i in bad_indices

    problem_note_files: dict[str, str] = {}
    for note, is_bad in note_is_problem.items():
        if is_bad:
            for fid in note_to_ids[note]:
                problem_note_files[fid] = note

    print(f"[llm] {len(problem_note_files)} files with problematic operator notes (data was OK)")
    return problem_note_files


# ---------------------------------------------------------------------------
# Step 4: Submit to hub
# ---------------------------------------------------------------------------

def submit_anomalies(anomaly_ids: list[str]) -> dict:
    payload = {
        "apikey": API_KEY,
        "task": "evaluation",
        "answer": {"recheck": anomaly_ids},
    }
    print(f"[submit] Sending {len(anomaly_ids)} anomaly IDs to hub ...")
    resp = requests.post(HUB_VERIFY_URL, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    # 1. Download ZIP (single file)
    download_zip()

    # 2. Single-pass scan from ZIP in memory
    prog_anomalies, clean_notes, raw_lines3, total = run_checks_from_zip(SENSORS_ZIP)

    # 3. LLM note classification for clean files
    note_anomalies = run_note_checks(clean_notes)

    # 4. Merge results
    all_anomaly_ids: set[str] = set(prog_anomalies.keys()) | set(note_anomalies.keys())
    sorted_ids = sorted(all_anomaly_ids)

    report = {
        "total_files": total,
        "programmatic_anomalies": prog_anomalies,
        "note_anomalies": {fid: note for fid, note in note_anomalies.items()},
        "all_anomaly_ids": sorted_ids,
        "count": len(sorted_ids),
    }
    ANOMALIES_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[report] {len(sorted_ids)} total anomalies -> {ANOMALIES_FILE}")

    # 5. Submit
    result = submit_anomalies(sorted_ids)
    VERIFICATION_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[result] {json.dumps(result, ensure_ascii=False)}")

    flag = result.get("message", "") or ""
    if "FLG" in flag or result.get("code") == 0:
        print(f"\nSUCCESS! Response: {flag}")
    else:
        print(f"\nHub response code: {result.get('code')} — {result.get('message')}")


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_KEY = os.environ["AI_DEVS_4_API_KEY"]
OPENROUTER_KEY = os.environ["API_OPEN_ROUTER_KEY"]

HUB_VERIFY_URL = "https://hub.ag3nts.org/verify"
SENSORS_ZIP_URL = "https://hub.ag3nts.org/dane/sensors.zip"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_MODEL = "openai/gpt-4o-mini"

L11_DIR = Path(__file__).resolve().parent
SENSORS_DIR = L11_DIR / "sensors"
ANOMALIES_FILE = L11_DIR / "anomalies.json"
VERIFICATION_FILE = L11_DIR / "verification_result.json"

# Sensor field mapping: sensor_type_name -> (json_field, min_value, max_value)
SENSOR_RULES: dict[str, tuple[str, float, float]] = {
    "temperature": ("temperature_K", 553.0, 873.0),
    "pressure": ("pressure_bar", 60.0, 160.0),
    "water": ("water_level_meters", 5.0, 15.0),
    "voltage": ("voltage_supply_v", 229.0, 231.0),
    "humidity": ("humidity_percent", 40.0, 80.0),
}
ALL_SENSOR_FIELDS = {v[0] for v in SENSOR_RULES.values()}


# ---------------------------------------------------------------------------
# Step 1: Download and extract sensors.zip
# ---------------------------------------------------------------------------

def download_and_extract() -> None:
    if SENSORS_DIR.exists() and any(SENSORS_DIR.iterdir()):
        print(f"[skip] Sensors already extracted to {SENSORS_DIR}")
        return
    print(f"[download] {SENSORS_ZIP_URL}")
    resp = requests.get(SENSORS_ZIP_URL, timeout=60)
    resp.raise_for_status()
    print(f"[extract] {len(resp.content) // 1024} KB -> {SENSORS_DIR}")
    SENSORS_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        zf.extractall(SENSORS_DIR)
    count = sum(1 for _ in SENSORS_DIR.rglob("*.json"))
    print(f"[extract] {count} JSON files extracted")


# ---------------------------------------------------------------------------
# Step 2: Programmatic anomaly detection
# ---------------------------------------------------------------------------

def parse_active_sensors(sensor_type: str) -> list[str]:
    """Return list of active sensor type names from compound sensor_type string."""
    return [s.strip().lower() for s in sensor_type.split("/") if s.strip()]


def check_programmatic(data: dict[str, Any]) -> list[str]:
    """
    Return list of reasons describing programmatic anomalies, empty if none.

    Checks:
    - Active sensor field is within valid range and non-zero
    - Inactive sensor fields are exactly 0
    """
    reasons: list[str] = []
    active_sensors = parse_active_sensors(data.get("sensor_type", ""))

    active_fields: set[str] = set()
    for sensor_name in active_sensors:
        if sensor_name not in SENSOR_RULES:
            reasons.append(f"unknown sensor type: {sensor_name!r}")
            continue
        field, lo, hi = SENSOR_RULES[sensor_name]
        active_fields.add(field)
        value = data.get(field, 0)
        if value == 0:
            reasons.append(f"{field}=0 but sensor '{sensor_name}' is active")
        elif not (lo <= value <= hi):
            reasons.append(f"{field}={value} outside range [{lo}, {hi}]")

    # Inactive fields must be 0
    for field in ALL_SENSOR_FIELDS:
        if field not in active_fields:
            value = data.get(field, 0)
            if value != 0:
                reasons.append(f"{field}={value} but sensor is inactive (expected 0)")

    return reasons


def run_programmatic_checks(json_files: list[Path]) -> tuple[dict[str, list[str]], list[Path]]:
    """
    Scan all files programmatically.

    Returns:
        programmatic_anomalies: {file_id: [reason, ...]}
        clean_files: files that passed all programmatic checks
    """
    programmatic_anomalies: dict[str, list[str]] = {}
    clean_files: list[Path] = []

    for path in json_files:
        file_id = path.stem  # e.g. "0001"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            programmatic_anomalies[file_id] = [f"JSON parse error: {exc}"]
            continue

        reasons = check_programmatic(data)
        if reasons:
            programmatic_anomalies[file_id] = reasons
        else:
            clean_files.append(path)

    print(f"[programmatic] {len(programmatic_anomalies)} anomalies, {len(clean_files)} clean files")
    return programmatic_anomalies, clean_files


# ---------------------------------------------------------------------------
# Step 3: LLM-based operator note classification
# ---------------------------------------------------------------------------

def call_llm(messages: list[dict], max_tokens: int = 512) -> str:
    """Call OpenRouter LLM and return the text response."""
    resp = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": LLM_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def classify_notes_batch(indexed_notes: list[tuple[int, str]]) -> set[int]:
    """
    Send a batch of indexed operator notes to the LLM.

    Returns set of indices of notes that indicate a problem/anomaly.
    The LLM is asked to return ONLY the indices of problematic notes as JSON.
    """
    lines = "\n".join(f'{i}: "{note}"' for i, note in indexed_notes)
    system = (
        "You are a sensor data quality checker. "
        "You will receive a numbered list of operator notes from sensor logfiles. "
        "Your task: identify which notes indicate that the operator found a problem, "
        "anomaly, error, or anything unusual. "
        "Notes saying everything is fine, stable, OK, or within expected range are NOT problems. "
        "Respond ONLY with a JSON array of the integer indices of problematic notes. "
        "Example: [0, 3, 7]. If none are problematic, respond with []."
    )
    user = f"Operator notes:\n{lines}"
    raw = call_llm([{"role": "system", "content": system}, {"role": "user", "content": user}])
    # Extract JSON array from response
    raw = raw.strip()
    # Find the first '[' and last ']'
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1:
        return set()
    try:
        indices = json.loads(raw[start : end + 1])
        return set(int(i) for i in indices)
    except (json.JSONDecodeError, ValueError):
        return set()


def run_note_checks(clean_files: list[Path], batch_size: int = 100) -> dict[str, str]:
    """
    For programmatically clean files, classify operator notes via LLM.

    Deduplicates notes to minimize LLM calls.
    Returns {file_id: note} for files whose note indicates a problem.
    """
    # Load notes and deduplicate
    file_notes: dict[str, str] = {}  # file_id -> note
    for path in clean_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            file_notes[path.stem] = data.get("operator_notes", "")
        except Exception:
            pass

    # Map unique notes to their file IDs
    note_to_ids: dict[str, list[str]] = defaultdict(list)
    for fid, note in file_notes.items():
        note_to_ids[note].append(fid)

    unique_notes = list(note_to_ids.keys())
    print(f"[llm] {len(file_notes)} clean files -> {len(unique_notes)} unique notes")

    # Classify notes in batches
    note_is_problem: dict[str, bool] = {}
    for batch_start in range(0, len(unique_notes), batch_size):
        batch = unique_notes[batch_start : batch_start + batch_size]
        indexed = list(enumerate(batch))
        end_idx = batch_start + len(batch)
        print(f"[llm] classifying notes {batch_start+1}-{end_idx}/{len(unique_notes)} ...")
        bad_indices = classify_notes_batch(indexed)
        for i, note in indexed:
            note_is_problem[note] = i in bad_indices

    # Collect file IDs with problematic notes (data is OK but operator says problem)
    problem_note_files: dict[str, str] = {}
    for note, is_bad in note_is_problem.items():
        if is_bad:
            for fid in note_to_ids[note]:
                problem_note_files[fid] = note

    print(f"[llm] {len(problem_note_files)} files with problematic operator notes (data was OK)")
    return problem_note_files


# ---------------------------------------------------------------------------
# Step 4: Submit to hub
# ---------------------------------------------------------------------------

def submit_anomalies(anomaly_ids: list[str]) -> dict:
    """Submit anomaly file IDs to the evaluation endpoint."""
    payload = {
        "apikey": API_KEY,
        "task": "evaluation",
        "answer": {"recheck": anomaly_ids},
    }
    print(f"[submit] Sending {len(anomaly_ids)} anomaly IDs to hub ...")
    resp = requests.post(HUB_VERIFY_URL, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    # 1. Download & extract
    download_and_extract()

    # Collect all JSON files
    json_files = sorted(SENSORS_DIR.rglob("*.json"))
    if not json_files:
        print("ERROR: No JSON files found in sensors directory.")
        sys.exit(1)
    print(f"[load] {len(json_files)} sensor files found")

    # 2. Programmatic checks
    prog_anomalies, clean_files = run_programmatic_checks(json_files)

    # 3. LLM note classification for clean files
    note_anomalies = run_note_checks(clean_files)

    # 4. Merge results
    all_anomaly_ids: set[str] = set(prog_anomalies.keys()) | set(note_anomalies.keys())
    sorted_ids = sorted(all_anomaly_ids)

    # Save detailed anomaly info for inspection
    report = {
        "total_files": len(json_files),
        "programmatic_anomalies": prog_anomalies,
        "note_anomalies": {fid: note for fid, note in note_anomalies.items()},
        "all_anomaly_ids": sorted_ids,
        "count": len(sorted_ids),
    }
    ANOMALIES_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[report] {len(sorted_ids)} total anomalies -> {ANOMALIES_FILE}")

    # 5. Submit
    result = submit_anomalies(sorted_ids)
    VERIFICATION_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[result] {json.dumps(result, ensure_ascii=False)}")

    flag = result.get("message", "") or ""
    if "FLG" in flag or result.get("code") == 0:
        print(f"\nSUCCESS! Response: {flag}")
    else:
        print(f"\nHub response code: {result.get('code')} — {result.get('message')}")


if __name__ == "__main__":
    main()
