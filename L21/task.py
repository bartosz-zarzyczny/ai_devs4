#!/usr/bin/env python3
"""L21 - radiomonitoring: collect radio intercepts, route by content type,
extract city intel with LLM, submit final transmit report to hub.

Usage:
    python L21/task.py           # full run: start session, listen, analyse, transmit
    python L21/task.py --replay  # re-analyse from saved session_raw.jsonl (no API calls)
    python L21/task.py --listen  # only collect data, skip LLM + transmit
    python L21/task.py --bonus   # solve the hidden /deeper bonus puzzle
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
L21_DIR = Path(__file__).resolve().parent
load_dotenv(REPO_ROOT / ".env")

API_KEY = os.environ["AI_DEVS_4_API_KEY"]
OPENROUTER_KEY = os.environ["API_OPEN_ROUTER_KEY"]

VERIFY_URL = "https://hub.ag3nts.org/verify"
TASK_NAME = "radiomonitoring"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Free model for text extraction (120B GPT-OSS)
LLM_TEXT_MODEL = "openai/gpt-oss-120b:free"
# Vision model for images
LLM_VISION_MODEL = "google/gemma-3-27b-it:free"

MAX_LISTEN_ITERATIONS = 200
INTER_REQUEST_SLEEP = 1.0  # seconds between listen calls

DANE_DIR = L21_DIR / "dane"
SESSION_RAW_FILE = L21_DIR / "session_raw.jsonl"
RESULT_FILE = L21_DIR / "verification_result.json"
BONUS_RESULT_FILE = L21_DIR / "bonus_result.json"

DEEPER_URL = "https://hub.ag3nts.org/deeper"
DEEPER_ENCODER_URL = "https://hub.ag3nts.org/encoder_deeper"
BONUS_MAX_PASSWORD_LEN = 32
BONUS_PROBE_SLEEP = 0.35

# ---------------------------------------------------------------------------
# Hub helpers
# ---------------------------------------------------------------------------


def _hub_post(action_payload: dict) -> dict:
    payload = {
        "apikey": API_KEY,
        "task": TASK_NAME,
        "answer": action_payload,
    }
    resp = requests.post(VERIFY_URL, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def start_session() -> dict:
    print("[hub] Starting session...")
    result = _hub_post({"action": "start"})
    print(f"[hub] start -> {result}")
    return result


def listen_once() -> dict:
    return _hub_post({"action": "listen"})


def transmit_report(city_name: str, city_area: str, warehouses_count: int, phone_number: str) -> dict:
    payload = {
        "action": "transmit",
        "cityName": city_name,
        "cityArea": city_area,
        "warehousesCount": warehouses_count,
        "phoneNumber": phone_number,
    }
    print(f"[hub] Transmitting report: {payload}")
    result = _hub_post(payload)
    print(f"[hub] transmit -> {result}")
    return result


# ---------------------------------------------------------------------------
# Session loop — collect raw signals
# ---------------------------------------------------------------------------

DANE_B64_DIR = DANE_DIR / "64"


# ---------------------------------------------------------------------------
# File helpers (used by both Phase 1 and Phase 2)
# ---------------------------------------------------------------------------


def _ext_for_meta(meta: str) -> str:
    mapping = {
        "application/json": ".json",
        "text/plain": ".txt",
        "text/html": ".html",
        "text/xml": ".xml",
        "text/csv": ".csv",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "audio/mpeg": ".mp3",
        "audio/wav": ".wav",
        "audio/ogg": ".ogg",
    }
    return mapping.get(meta, ".bin")


def _save_to_dane(filename: str, data: bytes) -> Path:
    DANE_DIR.mkdir(parents=True, exist_ok=True)
    path = DANE_DIR / filename
    path.write_bytes(data)
    return path


def _is_end_of_data(resp: dict) -> bool:
    """Detect hub signal that there is no more data to listen to."""
    code = resp.get("code", 100)
    if code not in (100, 200):
        return True
    msg = str(resp.get("message", "")).lower()
    end_keywords = ("no more", "enough data", "no signal", "end of", "finished", "complete", "done")
    return any(kw in msg for kw in end_keywords)


def _save_signal_to_dane(idx: int, resp: dict) -> None:
    """Save signal content to L21/dane/ (text) and L21/dane/64/ (raw base64) during collection."""
    DANE_DIR.mkdir(parents=True, exist_ok=True)
    DANE_B64_DIR.mkdir(parents=True, exist_ok=True)

    if "transcription" in resp:
        text = resp["transcription"]
        path = DANE_DIR / f"signal_{idx:03d}_transcription.txt"
        path.write_text(text, encoding="utf-8")
        print(f"  -> saved text: {path.name}")
        return

    if "attachment" in resp:
        meta = resp.get("meta", "application/octet-stream").lower()
        raw_b64: str = resp["attachment"]

        # save raw base64 to dane/64/
        b64_path = DANE_B64_DIR / f"signal_{idx:03d}.b64"
        b64_path.write_text(raw_b64, encoding="ascii")

        # decode and save to dane/
        try:
            raw_bytes = base64.b64decode(raw_b64)
        except Exception as exc:
            print(f"  -> base64 decode error: {exc}")
            return

        ext = _ext_for_meta(meta)
        decoded_path = DANE_DIR / f"signal_{idx:03d}{ext}"
        decoded_path.write_bytes(raw_bytes)
        print(f"  -> saved b64: {b64_path.name}  decoded: {decoded_path.name} ({len(raw_bytes)} B, {meta})")


def collect_signals() -> list[dict]:
    """Run the listen loop, save every response to session_raw.jsonl and dane/, return list."""
    SESSION_RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
    signals: list[dict] = []

    with SESSION_RAW_FILE.open("w", encoding="utf-8") as fh:
        for i in range(1, MAX_LISTEN_ITERATIONS + 1):
            print(f"[listen] iteration {i}/{MAX_LISTEN_ITERATIONS} ...", end=" ")
            resp = listen_once()
            print(f"code={resp.get('code')} msg={str(resp.get('message', ''))[:60]}")

            # persist raw JSON entry
            fh.write(json.dumps(resp, ensure_ascii=False) + "\n")
            fh.flush()
            signals.append(resp)

            # save content to dane/ immediately
            _save_signal_to_dane(i, resp)

            if _is_end_of_data(resp):
                print("[listen] End-of-data signal received, stopping loop.")
                break

            time.sleep(INTER_REQUEST_SLEEP)

    print(f"[listen] Collected {len(signals)} signal(s). Saved to {SESSION_RAW_FILE}")
    return signals


def load_signals_from_file() -> list[dict]:
    """Load previously collected signals from session_raw.jsonl."""
    if not SESSION_RAW_FILE.exists():
        raise FileNotFoundError(f"No saved session found at {SESSION_RAW_FILE}. Run without --replay first.")
    with SESSION_RAW_FILE.open(encoding="utf-8") as fh:
        signals = [json.loads(line) for line in fh if line.strip()]
    print(f"[replay] Loaded {len(signals)} signal(s) from {SESSION_RAW_FILE}")
    return signals


# ---------------------------------------------------------------------------
# Router — classify and extract content from each signal (pure Python, no LLM)
# ---------------------------------------------------------------------------

# Standard + Polish Morse code tables
_MORSE_TABLE: dict[str, str] = {
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D", ".": "E",
    "..-.": "F", "--.": "G", "....": "H", "..": "I", ".---": "J",
    "-.-": "K", ".-..": "L", "--": "M", "-.": "N", "---": "O",
    ".--.": "P", "--.-": "Q", ".-.": "R", "...": "S", "-": "T",
    "..-": "U", "...-": "V", ".--": "W", "-..-": "X", "-.--": "Y",
    "--..": "Z",
    # digits
    ".----": "1", "..---": "2", "...--": "3", "....-": "4", ".....": "5",
    "-....": "6", "--...": "7", "---..": "8", "----.": "9", "-----": "0",
    # Polish letters (common encoding)
    ".-.--": "Ą", "-.-.": "Ć", "..-..": "Ę", ".-..-.": "Ł",
    "--.--": "Ń", "---.": "Ó", "...-...": "Ś", "--..-.": "Ź", "--..--": "Ż",
    # punctuation
    ".-.-.-": ".", "--..--": ",", "..--..": "?", "-..-." : "/",
}

_NOISE_TOKENS = frozenset([
    "kshhh", "ksssh", "ksssssh", "kshhhhh", "ksssh", "bzzt", "bzzzzzzz",
    "bzzzzt", "bzzzz", "bbzzt", "trzask", "pisk", "szum", "szzzzz",
    "khhhhh", "khhhhhh", "shhhhhh", "shhhhh",
])


def _decode_morse(text: str) -> str | None:
    """Try to decode a TaTi-encoded Morse code string.

    Returns decoded text or None if the text doesn't look like Morse code.
    """
    # Strip leading/trailing static markers like *shhhhhh*
    cleaned = re.sub(r"\*[^*]*\*", " ", text).strip()
    # Quick check: must contain TaTa or TiTi patterns
    if not re.search(r"\b(Ta|Ti){2,}", cleaned):
        return None
    words = re.split(r"\(stop\)", cleaned, flags=re.IGNORECASE)
    decoded_words: list[str] = []
    for word_tokens in words:
        word_tokens = word_tokens.strip()
        if not word_tokens:
            continue
        letter_groups = word_tokens.split()
        decoded_letters: list[str] = []
        for group in letter_groups:
            # Convert TaTi notation to dots/dashes
            morse = re.sub(r"Ta", "-", group)
            morse = re.sub(r"Ti", ".", morse)
            ch = _MORSE_TABLE.get(morse, "?")
            decoded_letters.append(ch)
        decoded_words.append("".join(decoded_letters))
    result = " ".join(decoded_words)
    return result if result.strip("? ") else None


def _is_noise_transcription(text: str) -> bool:
    """Return True if the transcription is mostly radio static/noise.
    
    Two classes of noise tokens:
    1. Literal noise sounds: bzzt, trzask, pisk, etc.
    2. Partially cut words: tokens that start or end with '...' (signal fragments)
    """
    tokens = text.lower().split()
    if not tokens:
        return True
    noise_count = 0
    for t in tokens:
        # literal noise sound
        if any(t.startswith(n) for n in _NOISE_TOKENS):
            noise_count += 1
        # partially cut fragment preceded/followed by static
        elif t.startswith("...") or t.endswith("..."):
            noise_count += 1
    return (noise_count / len(tokens)) > 0.4



def route_signals(signals: list[dict]) -> tuple[list[str], list[dict], list[Path]]:
    """
    Classify each signal using Python only (no LLM).

    Returns:
        gathered_texts  - list of plain text strings
        gathered_json   - list of parsed JSON objects
        pending_images  - list of local file paths for image attachments
    """
    gathered_texts: list[str] = []
    gathered_json: list[dict] = []
    pending_images: list[Path] = []

    img_idx = audio_idx = bin_idx = 0

    for i, resp in enumerate(signals):
        code = resp.get("code", 0)

        # --- text transcription ---
        if "transcription" in resp:
            text = resp["transcription"].strip()
            if not text:
                continue

            # 1. Try Morse decode first (programmatic, free)
            decoded = _decode_morse(text)
            if decoded:
                print(f"[router] signal[{i}] -> Morse decoded: '{decoded}'")
                gathered_texts.append(f"[MORSE DECODED] {decoded}")
                continue

            # 2. Filter out pure radio noise
            if _is_noise_transcription(text):
                print(f"[router] signal[{i}] -> noise transcription, skipping ({len(text)} chars)")
                continue

            print(f"[router] signal[{i}] -> transcription ({len(text)} chars)")
            gathered_texts.append(text)
            continue

        # --- binary attachment ---
        if "attachment" in resp:
            meta = resp.get("meta", "application/octet-stream").lower()
            raw_b64: str = resp["attachment"]

            # decode locally
            try:
                raw_bytes = base64.b64decode(raw_b64)
            except Exception as exc:
                print(f"[router] signal[{i}] base64 decode error: {exc} — skipping")
                continue

            if meta == "application/json":
                try:
                    obj = json.loads(raw_bytes.decode("utf-8"))
                    filename = f"attachment_{i}.json"
                    path = _save_to_dane(filename, raw_bytes)
                    print(f"[router] signal[{i}] -> JSON attachment, saved {path}")
                    gathered_json.append(obj)
                except Exception as exc:
                    print(f"[router] signal[{i}] JSON parse error: {exc} — treating as text")
                    gathered_texts.append(raw_bytes.decode("utf-8", errors="replace"))

            elif meta.startswith("text/"):
                text = raw_bytes.decode("utf-8", errors="replace").strip()
                ext = _ext_for_meta(meta)
                filename = f"attachment_{i}{ext}"
                path = _save_to_dane(filename, raw_bytes)
                print(f"[router] signal[{i}] -> text attachment ({len(text)} chars), saved {path}")
                if text:
                    gathered_texts.append(text)

            elif meta.startswith("image/"):
                ext = _ext_for_meta(meta)
                filename = f"img_{img_idx}{ext}"
                path = _save_to_dane(filename, raw_bytes)
                print(f"[router] signal[{i}] -> image ({meta}, {len(raw_bytes)} B), saved {path}")
                pending_images.append(path)
                img_idx += 1

            elif meta.startswith("audio/"):
                ext = _ext_for_meta(meta)
                filename = f"audio_{audio_idx}{ext}"
                path = _save_to_dane(filename, raw_bytes)
                print(f"[router] signal[{i}] -> audio ({meta}, {len(raw_bytes)} B), saved {path} — skipping LLM")
                audio_idx += 1

            else:
                filename = f"binary_{bin_idx}.bin"
                path = _save_to_dane(filename, raw_bytes)
                print(f"[router] signal[{i}] -> unknown binary ({meta}, {len(raw_bytes)} B), saved {path} — skipping")
                bin_idx += 1

            continue

        # --- noise / no useful keys ---
        print(f"[router] signal[{i}] -> noise (code={code}, no transcription/attachment) — skipping")

    print(
        f"[router] Done. texts={len(gathered_texts)}, json_objects={len(gathered_json)}, images={len(pending_images)}"
    )
    return gathered_texts, gathered_json, pending_images


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """\
You are an intelligence analyst working with intercepted post-apocalyptic Polish radio communications.
The city codenamed "Syjon" is one of the settlements in these recordings.

Your task: extract the following four facts about the city called "Syjon":
1. cityName — the real geographic name of the city/village that people call "Syjon". 
   Look for context clues: conversations mention it, the JSON list contains real city names with their data.
   Match the description of Syjon (resources, location, character) to a city in the JSON data.
2. cityArea — the occupiedArea value (km²) for that city from the JSON data (a decimal number).
3. warehousesCount — the number of warehouses/magazynów in Syjon (an integer).
4. phoneNumber — the phone number of the contact person from Syjon (digits only, no separators or spaces).

All texts are in Polish. "Syjon" is a codename — the real city name is different.

Respond ONLY with a valid JSON object, no explanation, no markdown fences:
{"cityName": "...", "cityArea": 12.34, "warehousesCount": 321, "phoneNumber": "123456789"}

If a field cannot be determined, use null.
"""


def _call_openrouter(model: str, messages: list[dict], max_tokens: int = 1024) -> str:
    resp = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        },
        timeout=300,
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    if content is None:
        finish_reason = data["choices"][0].get("finish_reason", "unknown")
        print(f"[llm] WARNING: content=None, finish_reason={finish_reason}")
        print(f"[llm] Full response: {json.dumps(data, ensure_ascii=False)[:500]}")
        raise ValueError(f"LLM returned None content (finish_reason={finish_reason})")
    return content


def _parse_extraction(raw: str) -> dict:
    """Extract JSON dict from LLM response, even if wrapped in markdown fences."""
    raw = raw.strip()
    # strip optional ```json ... ``` fences
    raw = re.sub(r"^```[a-z]*\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def extract_with_llm_text(gathered_texts: list[str], gathered_json: list[dict]) -> dict:
    """Batch all text + JSON into a single cheap model call."""
    parts: list[str] = []
    if gathered_texts:
        parts.append("=== TEXT TRANSCRIPTIONS ===\n" + "\n---\n".join(gathered_texts))
    if gathered_json:
        serialized = "\n---\n".join(json.dumps(obj, ensure_ascii=False, indent=2) for obj in gathered_json)
        parts.append("=== JSON ATTACHMENTS ===\n" + serialized)

    if not parts:
        print("[llm] No text/JSON data to analyse.")
        return {}

    user_content = "\n\n".join(parts)
    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    print(f"[llm] Calling {LLM_TEXT_MODEL} for text extraction (~{len(user_content)} chars)...")
    raw = _call_openrouter(LLM_TEXT_MODEL, messages)
    print(f"[llm] Response: {raw[:200]}")
    return _parse_extraction(raw)


def _image_to_data_url(path: Path) -> str:
    """Encode image file to base64 data URL for vision models."""
    ext_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".gif": "image/gif", ".webp": "image/webp"}
    mime = ext_map.get(path.suffix.lower(), "image/png")
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def extract_with_llm_images(pending_images: list[Path]) -> dict:
    """Call vision model once per image, merge results."""
    merged: dict = {}
    for img_path in pending_images:
        print(f"[llm-vision] Analysing {img_path} with {LLM_VISION_MODEL}...")
        data_url = _image_to_data_url(img_path)
        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyse this image for intelligence about the city codenamed Syjon."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ]
        raw = _call_openrouter(LLM_VISION_MODEL, messages)
        print(f"[llm-vision] Response: {raw[:200]}")
        try:
            result = _parse_extraction(raw)
            for k, v in result.items():
                if v is not None and merged.get(k) is None:
                    merged[k] = v
        except Exception as exc:
            print(f"[llm-vision] Parse error: {exc}")
    return merged


def merge_extractions(*results: dict) -> dict:
    """Merge multiple extraction dicts — first non-null value wins per field."""
    fields = ["cityName", "cityArea", "warehousesCount", "phoneNumber"]
    merged: dict = {}
    for field in fields:
        for r in results:
            v = r.get(field)
            if v is not None:
                merged[field] = v
                break
    return merged


def format_report(extracted: dict) -> dict:
    """Validate and format extracted fields for the transmit call."""
    missing = [f for f in ("cityName", "cityArea", "warehousesCount", "phoneNumber") if extracted.get(f) is None]
    if missing:
        print(f"[report] WARNING: missing fields: {missing}")

    city_area_raw = extracted.get("cityArea")
    if city_area_raw is not None:
        city_area_str = f"{round(float(city_area_raw), 2):.2f}"
    else:
        city_area_str = None

    warehouses = extracted.get("warehousesCount")
    if warehouses is not None:
        warehouses = int(warehouses)

    phone = str(extracted.get("phoneNumber", "") or "").strip()
    # keep digits only
    phone = re.sub(r"\D", "", phone)

    return {
        "cityName": extracted.get("cityName"),
        "cityArea": city_area_str,
        "warehousesCount": warehouses,
        "phoneNumber": phone if phone else None,
    }


def find_bonus_hint(signals: list[dict]) -> tuple[int | None, str | None]:
    for idx, resp in enumerate(signals, start=1):
        text = str(resp.get("transcription", "") or "").strip()
        if not text:
            continue
        decoded = _decode_morse(text)
        if decoded and "DEEPER" in decoded.upper():
            return idx, decoded

    for path in sorted(DANE_DIR.glob("signal_*_transcription.txt")):
        text = path.read_text(encoding="utf-8")
        decoded = _decode_morse(text)
        if decoded and "DEEPER" in decoded.upper():
            match = re.search(r"signal_(\d{3})_transcription\.txt$", path.name)
            idx = int(match.group(1)) if match else None
            return idx, decoded

    return None, None


def _probe_deeper(session: requests.Session, text: str) -> dict:
    while True:
        resp = session.post(DEEPER_ENCODER_URL, json={"text": text}, timeout=30)
        if resp.status_code == 429:
            print("[bonus] Rate limited by /encoder_deeper, sleeping 3.2s...")
            time.sleep(3.2)
            continue
        resp.raise_for_status()
        return resp.json()


def solve_bonus(signals: list[dict] | None = None) -> dict:
    if signals is None:
        if SESSION_RAW_FILE.exists():
            signals = load_signals_from_file()
        else:
            signals = []

    hint_index, hint_decoded = find_bonus_hint(signals)
    if not hint_decoded:
        raise RuntimeError("Could not find the Morse clue with DEEPER in saved signals/dane files.")

    print(f"[bonus] Morse clue found in signal_{hint_index:03d}: {hint_decoded}" if hint_index else f"[bonus] Morse clue: {hint_decoded}")
    print(f"[bonus] Opening hidden page: {DEEPER_URL}")

    session = requests.Session()
    page = session.get(DEEPER_URL, timeout=30)
    page.raise_for_status()

    password = ""
    final_probe: dict | None = None

    for position in range(BONUS_MAX_PASSWORD_LEN):
        matched = False
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            candidate = password + letter
            probe = _probe_deeper(session, candidate)
            correct = set(probe.get("correct") or [])
            print(f"[bonus] probe={candidate!r} encoded={probe.get('encoded', '')!r} correct={sorted(correct)}")
            if position in correct:
                password = candidate
                final_probe = probe
                matched = True
                print(f"[bonus] position {position} -> {letter}")
                break
            time.sleep(BONUS_PROBE_SLEEP)

        if final_probe and final_probe.get("flag"):
            break
        if not matched:
            raise RuntimeError(f"Could not determine bonus password character at position {position}. Partial password={password!r}")

    if not final_probe or not final_probe.get("flag"):
        final_probe = _probe_deeper(session, password)

    flag = final_probe.get("flag") if final_probe else None
    if not flag:
        raise RuntimeError(f"Bonus password {password!r} did not return a flag.")

    result = {
        "pageUrl": DEEPER_URL,
        "encoderUrl": DEEPER_ENCODER_URL,
        "hintSignalIndex": hint_index,
        "hintDecoded": hint_decoded,
        "password": password,
        "encodedTarget": final_probe.get("encoded"),
        "flag": flag,
    }
    BONUS_RESULT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[bonus] bonus_result.json saved: {BONUS_RESULT_FILE}")
    print(f"[bonus] Result: {result}")
    return result


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run(replay: bool = False, listen_only: bool = False) -> None:
    # Phase 1 — collect signals
    if replay:
        signals = load_signals_from_file()
        # also re-save to dane/ so the folder is populated even in replay mode
        for idx, resp in enumerate(signals, start=1):
            _save_signal_to_dane(idx, resp)
    else:
        start_session()
        signals = collect_signals()

    if listen_only:
        print("[main] --listen flag set, stopping after data collection.")
        return

    # Phase 2 — route (pure Python)
    gathered_texts, gathered_json, pending_images = route_signals(signals)

    # Phase 3 — LLM extraction
    text_result = extract_with_llm_text(gathered_texts, gathered_json)
    image_result = extract_with_llm_images(pending_images) if pending_images else {}
    extracted = merge_extractions(text_result, image_result)
    print(f"[extract] Merged result: {extracted}")

    # Phase 4 — format and transmit
    report = format_report(extracted)
    print(f"[report] Final report: {report}")

    missing = [k for k, v in report.items() if v is None]
    if missing:
        print(f"[report] Cannot transmit — missing: {missing}")
        print("[report] Check session_raw.jsonl and dane/ for clues.")
        return

    result = transmit_report(
        city_name=report["cityName"],
        city_area=report["cityArea"],
        warehouses_count=report["warehousesCount"],
        phone_number=report["phoneNumber"],
    )

    RESULT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] verification_result.json saved.")
    print(f"[done] Hub response: {result}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="L21 radiomonitoring solver")
    parser.add_argument("--replay", action="store_true", help="Re-analyse saved session_raw.jsonl without new API calls")
    parser.add_argument("--listen", action="store_true", help="Only collect signals, skip LLM and transmit")
    parser.add_argument("--bonus", action="store_true", help="Solve the hidden /deeper bonus puzzle and save bonus_result.json")
    args = parser.parse_args()

    if args.bonus:
        solve_bonus()
    else:
        run(replay=args.replay, listen_only=args.listen)
