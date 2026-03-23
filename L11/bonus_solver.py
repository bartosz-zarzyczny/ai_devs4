#!/usr/bin/env python3
"""L11 bonus: find the unique suspicious JSON, decode the AWK flag from decode.txt."""

from __future__ import annotations

import json
import os
import re
import zipfile
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_KEY = os.environ["AI_DEVS_4_API_KEY"]
HUB_VERIFY_URL = "https://hub.ag3nts.org/verify"
DECODE_URL = "https://hub.ag3nts.org/dane/decode.txt"

L11_DIR = Path(__file__).resolve().parent
SENSORS_ZIP = L11_DIR / "sensors.zip"
BONUS_RESULT_FILE = L11_DIR / "bonus_result.json"

AWK_B_POSITIONS = [44, 60, 66, 74, 76]  # 1-indexed


def step1_trigger_bonus():
    """Send the 5 bonus IDs to hub and get the decode.txt URL."""
    bonus_ids = ["9132", "1522", "2306", "1048", "2119"]
    payload = {"apikey": API_KEY, "task": "evaluation", "answer": {"recheck": bonus_ids}}
    resp = requests.post(HUB_VERIFY_URL, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    print(f"[bonus trigger] {result}")
    return result.get("message", "")


def step2_get_decode_script():
    """Download decode.txt from hub."""
    resp = requests.get(DECODE_URL, timeout=20)
    resp.raise_for_status()
    script = resp.text
    print(f"[decode.txt]\n{script}")
    return script


def step3_find_unique_json():
    """
    Search for the unique JSON where the AWK script produces a readable flag.

    The AWK script (FS='"'):
      NR==3: line = '  "timestamp": ...'
             $2 = 'timestamp', a = substr('timestamp',1,4) = 'time'
      NR==9: line = '  "operator_notes": "TEXT",'
             $4 = TEXT
             b = chars at 1-indexed positions 44,60,66,74,76

    The unique file will have operator_notes where those 5 positions are all
    letters (and together spell a real word).
    """
    if not SENSORS_ZIP.exists():
        print(f"[ERROR] sensors.zip not found at {SENSORS_ZIP}")
        return [], [], [], []

    from collections import Counter

    candidates = []
    with zipfile.ZipFile(SENSORS_ZIP) as zf:
        names = sorted(n for n in zf.namelist() if n.endswith(".json"))
        print(f"[search] scanning {len(names)} files from {SENSORS_ZIP.name}...")
        for name in names:
            file_id = Path(name).stem
            try:
                raw = zf.read(name).decode("utf-8")
                lines = raw.splitlines()
            except Exception:
                continue

            # NR==3 in AWK is 1-indexed, Python index 2
            if len(lines) < 9:
                continue

            line3 = lines[2]  # e.g. '  "timestamp": 1234,'
            # split by '"': ['  ', 'timestamp', ': 1234,']
            parts3 = line3.split('"')
            if len(parts3) < 3:
                continue
            a = parts3[1][:4]  # first 4 chars of field name on line 3

            line9 = lines[8]  # e.g. '  "operator_notes": "TEXT",'
            parts9 = line9.split('"')
            # $4 = parts9[3] (0-indexed) in AWK FS='"'
            if len(parts9) < 4:
                continue
            note_text = parts9[3]  # the actual notes value

            # Extract b: chars at 1-indexed positions 44,60,66,74,76
            b_chars = []
            valid = True
            for pos in AWK_B_POSITIONS:
                idx = pos - 1  # convert to 0-indexed
                if idx >= len(note_text):
                    valid = False
                    break
                b_chars.append(note_text[idx])
            if not valid:
                continue

            b = "".join(b_chars).upper()
            flag_candidate = f"{{FLG:{a.upper()}{b}}}"

            is_timestamp_line = "timestamp" in line3
            all_alpha = b.replace("_", "").isalpha()

            if all_alpha:
                candidates.append({
                    "file_id": file_id,
                    "a": a.upper(),
                    "b": b,
                    "flag": flag_candidate,
                    "line3_field": parts3[1] if len(parts3) > 1 else "",
                    "note_text": note_text,
                    "is_standard_line3": is_timestamp_line,
                })

    print(f"[search] found {len(candidates)} candidates with all-alpha b")

    non_std = [c for c in candidates if not c["is_standard_line3"]]
    std = [c for c in candidates if c["is_standard_line3"]]
    b_counts = Counter(c["b"] for c in std)
    unique_b = [c for c in std if b_counts[c["b"]] == 1]

    print(f"\n=== Non-standard line3 ({len(non_std)}) ===")
    for c in non_std[:10]:
        print(f"  {c['file_id']}: line3_field={c['line3_field']!r}  flag={c['flag']}  note={c['note_text'][:60]!r}")

    print(f"\n=== Standard line3, unique b value ({len(unique_b)}) ===")
    for c in unique_b[:10]:
        print(f"  {c['file_id']}: flag={c['flag']}  note={c['note_text'][:60]!r}")

    # The truly unique file has a note with TWO sentences (a mid-sentence period
    # not at the very end), while all other notes are single sentences.
    two_sentence = [
        c for c in unique_b
        if re.search(r'\.\s+[A-Z]', c["note_text"])
    ]
    print(f"\n=== Unique b AND two-sentence note ({len(two_sentence)}) ===")
    for c in two_sentence:
        print(f"  {c['file_id']}: flag={c['flag']}  note={c['note_text']!r}")

    return non_std, unique_b, candidates, two_sentence


def step4_record_flag(flag: str) -> None:
    """Record the decoded bonus flag (no hub submission needed — decoding IS the solution)."""
    print(f"\n{'='*55}")
    print(f"BONUS FLAG DECODED: {flag}")
    print(f"{'='*55}")
    print("File: 2137.json (inside sensors.zip)")
    print("Note: 'The report looks completely normal. I will go to check status of all other devices.'")
    print("AWK: a=TIME (substr('timestamp',1,4)), b=GUARD (positions 44,60,66,74,76 of note)")
    print(f"{'='*55}\n")


def main():
    # Step 1: trigger the bonus
    decode_url = step1_trigger_bonus()
    print(f"Decode URL: {decode_url}")

    # Step 2: get decode script
    script = step2_get_decode_script()

    # Step 3: find the unique JSON
    non_std, unique_b, all_candidates, two_sentence = step3_find_unique_json()

    # Pick best candidate: two-sentence note with unique b is the suspicious file
    best = None
    if two_sentence:
        best = two_sentence[0]
        print(f"\n[best] Two-sentence note + unique b: {best['file_id']} -> {best['flag']}")
    elif non_std:
        best = non_std[0]
        print(f"\n[best] Non-standard line3 file: {best['file_id']} -> {best['flag']}")
    elif unique_b:
        best = unique_b[0]
        print(f"\n[best] Unique b value file: {best['file_id']} -> {best['flag']}")
    elif all_candidates:
        # Most likely among all: pick the one anomaly file
        anom_file = L11_DIR / "anomalies.json"
        anomaly_ids = set()
        if anom_file.exists():
            anom_data = json.loads(anom_file.read_text(encoding="utf-8"))
            anomaly_ids = set(anom_data.get("all_anomaly_ids", []))
        anomaly_candidates = [c for c in all_candidates if c["file_id"] in anomaly_ids]
        if anomaly_candidates:
            best = anomaly_candidates[0]
            print(f"\n[best] Anomaly file candidate: {best['file_id']} -> {best['flag']}")

    if best:
        result = {
            "file_id": best["file_id"],
            "flag": best["flag"],
            "a": best["a"],
            "b": best["b"],
            "note_text": best["note_text"],
        }
        BONUS_RESULT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[saved] {BONUS_RESULT_FILE}")

        step4_record_flag(best["flag"])
    else:
        print("[ERROR] No suitable candidate found.")


if __name__ == "__main__":
    main()
