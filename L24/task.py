#!/usr/bin/env python3
"""L24 - goingthere: navigate a rocket across a 3x12 grid avoiding rocks,
neutralising OKO radar traps, and reaching the target base in Grudziadz.

Usage:
    python L24/task.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_KEY = os.environ["AI_DEVS_4_API_KEY"]
OPENROUTER_KEY = os.environ["API_OPEN_ROUTER_KEY"]

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# LLM_MODEL = "openai/gpt-5.4-mini"
# LLM_VALIDATOR_MODEL = "openai/gpt-5.4-nano"

LLM_MODEL = "openai/gpt-5.4"
LLM_VALIDATOR_MODEL = "openai/gpt-5.4-mini"

VERIFY_URL = "https://hub.ag3nts.org/verify"
SCANNER_URL = "https://hub.ag3nts.org/api/frequencyScanner"
MESSAGE_URL = "https://hub.ag3nts.org/api/getmessage"

L24_DIR = Path(__file__).resolve().parent
VERIFICATION_FILE = L24_DIR / "verification_result.json"
BONUS_FILE = L24_DIR / "bonus_result.json"
HINT_LOG_FILE = L24_DIR / "hint_log.json"
HINT_KNOWLEDGE_FILE = L24_DIR / "hint_knowledge.json"

TASK_NAME = "goingthere"
GRAVE_CRASH_STEPS = [6, 4, 2]

MAX_RETRIES = 10
RETRY_DELAY = 2  # seconds between retries
RATE_LIMIT_DELAY = 8
MIN_API_INTERVAL = 0.75

_last_api_call_at = 0.0


def _load_json_file(path: Path, default: object) -> object:
    """Load JSON from disk and fall back to a default value on any error."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


_HINT_LOG: list[dict] = _load_json_file(HINT_LOG_FILE, [])  # type: ignore[assignment]
if not isinstance(_HINT_LOG, list):
    _HINT_LOG = []

_HINT_KNOWLEDGE: dict = _load_json_file(HINT_KNOWLEDGE_FILE, {"entries": {}, "patterns": {}})  # type: ignore[assignment]
if not isinstance(_HINT_KNOWLEDGE, dict):
    _HINT_KNOWLEDGE = {"entries": {}, "patterns": {}}
if not isinstance(_HINT_KNOWLEDGE.get("entries"), dict):
    _HINT_KNOWLEDGE["entries"] = {}
if not isinstance(_HINT_KNOWLEDGE.get("patterns"), dict):
    _HINT_KNOWLEDGE["patterns"] = {}


def _persist_hint_files() -> None:
    """Persist hint logs and learned knowledge to JSON files."""
    HINT_LOG_FILE.write_text(json.dumps(_HINT_LOG, ensure_ascii=False, indent=2), encoding="utf-8")
    HINT_KNOWLEDGE_FILE.write_text(
        json.dumps(_HINT_KNOWLEDGE, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _normalise_hint(text: str) -> str:
    """Collapse whitespace so the same hint text maps to one stable key."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _new_move_counter() -> dict[str, int]:
    """Create a default move counter dictionary."""
    return {"left": 0, "go": 0, "right": 0}


def _get_hint_entry(hint: str) -> tuple[str, dict]:
    """Return the persistent knowledge entry for a given hint."""
    hint_key = _normalise_hint(hint)
    entries = _HINT_KNOWLEDGE.setdefault("entries", {})
    entry = entries.setdefault(
        hint_key,
        {
            "hint": hint,
            "normalized_hint": hint_key,
            "confirmed_blocked_move": None,
            "blocked_move_votes": _new_move_counter(),
            "blocked_move_rejections": _new_move_counter(),
            "successful_move_examples": [],
            "failed_move_examples": [],
        },
    )
    entry["hint"] = hint
    return hint_key, entry


def _extract_hint_direction_evidence(hint: str) -> tuple[set[str], set[str]]:
    """Return safe and blocked moves explicitly described by a hint."""
    safe_moves: set[str] = set()
    blocked_moves: set[str] = set()

    for clause in re.split(r"[.!?;]", hint.lower()):
        clause = clause.strip()
        if not clause:
            continue
        directions = _directions_from_clause(clause)
        if not directions:
            continue
        if _OBSTACLE_MARKERS.search(clause):
            blocked_moves.update(directions)
        elif _SAFE_MARKERS.search(clause):
            safe_moves.update(directions)

    return safe_moves, blocked_moves


def _hint_signature(hint: str) -> str:
    """Build a coarse semantic signature from safe and dangerous directional clauses."""
    safe_moves, blocked_moves = _extract_hint_direction_evidence(hint)

    safe_part = ",".join(sorted(safe_moves)) or "none"
    blocked_part = ",".join(sorted(blocked_moves)) or "none"
    return f"safe:{safe_part}|blocked:{blocked_part}"


def _get_pattern_entry(hint: str) -> tuple[str, dict]:
    """Return the persistent pattern entry for a semantic hint signature."""
    signature = _hint_signature(hint)
    patterns = _HINT_KNOWLEDGE.setdefault("patterns", {})
    entry = patterns.setdefault(
        signature,
        {
            "signature": signature,
            "examples": [],
            "confirmed_blocked_move": None,
            "blocked_move_votes": _new_move_counter(),
            "blocked_move_rejections": _new_move_counter(),
            "successful_move_examples": [],
            "failed_move_examples": [],
        },
    )
    examples = entry.setdefault("examples", [])
    normalized = _normalise_hint(hint)
    if normalized not in examples:
        examples.append(normalized)
        del examples[:-25]
    return signature, entry


def _best_move_from_entry(entry: dict) -> str | None:
    """Select the strongest move hypothesis from a knowledge entry."""
    confirmed = entry.get("confirmed_blocked_move")
    if confirmed in {"left", "go", "right"}:
        return str(confirmed)

    votes = entry.get("blocked_move_votes", {})
    rejections = entry.get("blocked_move_rejections", {})
    scores = {
        move: int(votes.get(move, 0)) - 2 * int(rejections.get(move, 0))
        for move in ("left", "go", "right")
    }
    best_move = max(scores, key=lambda move: scores[move])
    best_score = scores[best_move]
    if best_score <= 0:
        return None
    if list(scores.values()).count(best_score) > 1:
        return None
    return best_move


def _should_accept_postmortem_correction(record: dict) -> bool:
    """Reject corrections that clearly contradict the literal hint wording."""
    move = record.get("chosen_move")
    if move not in {"left", "go", "right"}:
        return False

    hint = str(record.get("hint", ""))
    safe_moves, explicit_blocked_moves = _extract_hint_direction_evidence(hint)

    if move in safe_moves and move not in explicit_blocked_moves:
        print(
            "  [hint-memory] ignoring contradictory correction: "
            f"hint marks '{move}' as safe"
        )
        return False

    if len(explicit_blocked_moves) == 1 and move not in explicit_blocked_moves:
        expected_move = next(iter(explicit_blocked_moves))
        print(
            "  [hint-memory] ignoring contradictory correction: "
            f"hint points to '{expected_move}', not '{move}'"
        )
        return False

    blocked_move = record.get("blocked_move")
    blocked_move_source = str(record.get("blocked_move_source", ""))
    if blocked_move_source.startswith("manual") and blocked_move in {"left", "go", "right"} and blocked_move != move:
        print(
            "  [hint-memory] ignoring contradictory correction against curated override: "
            f"{blocked_move} != {move}"
        )
        return False

    return True


def _freeze_log_value(value: object) -> object:
    """Convert nested JSON-like structures into hashable values for log deduplication."""
    if isinstance(value, list):
        return tuple(_freeze_log_value(item) for item in value)
    if isinstance(value, dict):
        return tuple(
            sorted(
                (key, _freeze_log_value(item))
                for key, item in value.items()
                if key not in {"timestamp", "first_seen", "last_seen", "repeat_count"}
            )
        )
    return value


def _hint_log_fingerprint(record: dict) -> tuple:
    """Build a stable identity for merging repeated log entries."""
    return tuple(
        sorted(
            (key, _freeze_log_value(value))
            for key, value in record.items()
            if key not in {"timestamp", "first_seen", "last_seen", "repeat_count"}
        )
    )


def _append_or_merge_hint_log(record: dict) -> None:
    """Store a log record or bump the repeat counter for an identical one."""
    fingerprint = _hint_log_fingerprint(record)
    timestamp = record.get("timestamp")

    for existing in reversed(_HINT_LOG):
        if _hint_log_fingerprint(existing) != fingerprint:
            continue
        existing["repeat_count"] = int(existing.get("repeat_count", 1)) + 1
        existing.setdefault("first_seen", existing.get("timestamp", timestamp))
        existing["last_seen"] = timestamp
        return

    log_record = dict(record)
    log_record["repeat_count"] = 1
    log_record["first_seen"] = timestamp
    log_record["last_seen"] = timestamp
    _HINT_LOG.append(log_record)
    del _HINT_LOG[:-500]


def _compact_hint_log() -> bool:
    """Merge already duplicated log entries loaded from disk."""
    compacted: list[dict] = []
    merged_by_fingerprint: dict[tuple, dict] = {}

    for raw_record in _HINT_LOG:
        if not isinstance(raw_record, dict):
            continue

        record = dict(raw_record)
        timestamp = record.get("timestamp")
        record.setdefault("first_seen", record.get("timestamp", timestamp))
        record.setdefault("last_seen", record.get("timestamp", timestamp))
        record["repeat_count"] = int(record.get("repeat_count", 1) or 1)

        fingerprint = _hint_log_fingerprint(record)
        existing = merged_by_fingerprint.get(fingerprint)
        if existing is None:
            compacted.append(record)
            merged_by_fingerprint[fingerprint] = record
            continue

        existing["repeat_count"] += record["repeat_count"]
        if str(record.get("first_seen", "")) < str(existing.get("first_seen", "")):
            existing["first_seen"] = record.get("first_seen")
        if str(record.get("last_seen", "")) > str(existing.get("last_seen", "")):
            existing["last_seen"] = record.get("last_seen")

    compacted = compacted[-500:]
    changed = compacted != _HINT_LOG
    if changed:
        _HINT_LOG[:] = compacted
    return changed


def _update_knowledge_entry(entry: dict, record: dict) -> dict[str, str] | None:
    """Update one knowledge entry from a single observed outcome."""
    move = record.get("chosen_move")
    blocked_move = record.get("blocked_move")
    outcome = str(record.get("outcome", "unknown"))
    crash_reason = str(record.get("crash_reason", ""))

    if blocked_move in {"left", "go", "right"} and outcome in {"success", "planned_crash"} and move != blocked_move:
        entry["blocked_move_votes"][blocked_move] += 1

    postmortem: dict[str, str] | None = None
    if crash_reason == "stone" and move in {"left", "go", "right"}:
        if _should_accept_postmortem_correction(record):
            entry["confirmed_blocked_move"] = move
            entry["blocked_move_votes"][move] += 3
            if blocked_move in {"left", "go", "right"} and blocked_move != move:
                entry["blocked_move_rejections"][blocked_move] += 1
                postmortem = {
                    "corrected_blocked_move": str(move),
                    "previous_blocked_move": str(blocked_move),
                }

    if outcome == "success":
        example = {
            "current_row": record.get("row"),
            "target_row": record.get("target_row"),
            "column": record.get("column"),
            "valid_commands": record.get("valid_commands"),
            "chosen_move": move,
        }
        examples = entry["successful_move_examples"]
        if example not in examples:
            examples.append(example)
            del examples[:-25]

    if outcome in {"crash", "planned_crash"}:
        failed_example = {
            "current_row": record.get("row"),
            "target_row": record.get("target_row"),
            "column": record.get("column"),
            "valid_commands": record.get("valid_commands"),
            "chosen_move": move,
            "crash_reason": crash_reason,
        }
        failures = entry["failed_move_examples"]
        if failed_example not in failures:
            failures.append(failed_example)
            del failures[:-25]

    return postmortem


def _valid_commands_for_row(current_row: int) -> list[str]:
    """Return commands that keep the rocket within board limits."""
    valid_commands: list[str] = []
    for command in ("left", "go", "right"):
        if command == "left":
            next_row = current_row - 1
        elif command == "right":
            next_row = current_row + 1
        else:
            next_row = current_row
        if 1 <= next_row <= 3:
            valid_commands.append(command)
    return valid_commands


def _get_memorized_blocked_move(hint: str) -> str | None:
    """Reuse a previously learned blocked move for an exact or semantic hint match."""
    _, entry = _get_hint_entry(hint)
    move = _best_move_from_entry(entry)
    if move is not None:
        return move

    _, pattern_entry = _get_pattern_entry(hint)
    return _best_move_from_entry(pattern_entry)


def _get_memorized_safe_move(
    hint: str,
    current_row: int,
    target_row: int,
    valid_commands: list[str],
) -> str | None:
    """Reuse a previously successful move for the same hint or semantic pattern."""
    def find_example(examples: object) -> str | None:
        if not isinstance(examples, list):
            return None
        for example in reversed(examples):
            if not isinstance(example, dict):
                continue
            if example.get("current_row") != current_row:
                continue
            if example.get("target_row") != target_row:
                continue
            if example.get("valid_commands") != valid_commands:
                continue
            move = example.get("chosen_move")
            if move in valid_commands:
                return str(move)
        return None

    _, entry = _get_hint_entry(hint)
    move = find_example(entry.get("successful_move_examples", []))
    if move is not None:
        return move

    _, pattern_entry = _get_pattern_entry(hint)
    return find_example(pattern_entry.get("successful_move_examples", []))


def _record_hint_outcome(record: dict) -> None:
    """Persist raw hint attempts and update reusable knowledge from outcomes."""
    hint = str(record.get("hint", ""))
    hint_key, entry = _get_hint_entry(hint)
    pattern_key, pattern_entry = _get_pattern_entry(hint)
    record["hint_key"] = hint_key
    record["pattern_key"] = pattern_key

    postmortem = _update_knowledge_entry(entry, record)
    _update_knowledge_entry(pattern_entry, record)

    if postmortem is not None:
        record["postmortem"] = postmortem
        print(
            "  [hint-memory] corrected blocked move from outcome: "
            f"{postmortem['previous_blocked_move']} -> {postmortem['corrected_blocked_move']}"
        )

    _append_or_merge_hint_log(record)
    _persist_hint_files()

# ---------------------------------------------------------------------------
# HTTP helpers with retry
# ---------------------------------------------------------------------------


def _throttle_api_calls() -> None:
    """Keep a small gap between calls to avoid hub rate limits."""
    global _last_api_call_at
    elapsed = time.time() - _last_api_call_at
    if elapsed < MIN_API_INTERVAL:
        time.sleep(MIN_API_INTERVAL - elapsed)


def _mark_api_call() -> None:
    """Record the timestamp of the last API call."""
    global _last_api_call_at
    _last_api_call_at = time.time()


def _is_rate_limited_message(message: str) -> bool:
    """Return True when the server asks us to slow down."""
    normalized = message.lower()
    return (
        "za czesto wykonujesz zapytania" in normalized
        or "zwolnij" in normalized
        or "too many requests" in normalized
        or "rate limit" in normalized
        or "slow down" in normalized
    )


def _post(url: str, payload: dict, *, retries: int = MAX_RETRIES) -> dict:
    """POST with automatic retry on network/server errors."""
    for attempt in range(1, retries + 1):
        try:
            _throttle_api_calls()
            resp = requests.post(url, json=payload, timeout=30)
            _mark_api_call()
            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError:
                    # Return raw text wrapped so callers can inspect it
                    return {"_raw": resp.text}

            response_text = resp.text
            response_message = response_text
            try:
                response_json = resp.json()
                if isinstance(response_json, dict):
                    response_message = str(response_json.get("message", response_text))
            except ValueError:
                response_json = None

            if resp.status_code == 429 or _is_rate_limited_message(response_message):
                print(
                    f"[warn] POST {url} rate limited, attempt {attempt}/{retries}; "
                    f"waiting {RATE_LIMIT_DELAY}s"
                )
                if attempt < retries:
                    time.sleep(RATE_LIMIT_DELAY)
                    continue
                if isinstance(response_json, dict):
                    response_json["_http_status"] = resp.status_code
                    return response_json
                return {"_raw": response_text, "_http_status": resp.status_code}

            # Structured 4xx responses from the hub often contain useful state
            # like crash information; return them to the caller instead of
            # retrying blindly.
            if 400 <= resp.status_code < 500:
                if isinstance(response_json, dict):
                    response_json["_http_status"] = resp.status_code
                    return response_json
                return {"_raw": response_text, "_http_status": resp.status_code}

            print(f"[warn] POST {url} -> HTTP {resp.status_code}, attempt {attempt}/{retries}")
        except requests.RequestException as exc:
            print(f"[warn] POST {url} network error ({exc}), attempt {attempt}/{retries}")
        if attempt < retries:
            time.sleep(RETRY_DELAY)
    raise RuntimeError(f"POST {url} failed after {retries} attempts")


def _get(url: str, *, retries: int = MAX_RETRIES) -> str:
    """GET with automatic retry; returns raw text."""
    for attempt in range(1, retries + 1):
        try:
            _throttle_api_calls()
            resp = requests.get(url, timeout=30)
            _mark_api_call()
            if resp.status_code == 200:
                if _is_rate_limited_message(resp.text):
                    print(
                        f"[warn] GET {url} rate limited in body, attempt {attempt}/{retries}; "
                        f"waiting {RATE_LIMIT_DELAY}s"
                    )
                    if attempt < retries:
                        time.sleep(RATE_LIMIT_DELAY)
                        continue
                return resp.text

            if resp.status_code == 429 or _is_rate_limited_message(resp.text):
                print(
                    f"[warn] GET {url} rate limited, attempt {attempt}/{retries}; "
                    f"waiting {RATE_LIMIT_DELAY}s"
                )
                if attempt < retries:
                    time.sleep(RATE_LIMIT_DELAY)
                    continue

            print(f"[warn] GET {url} -> HTTP {resp.status_code}, attempt {attempt}/{retries}")
        except requests.RequestException as exc:
            print(f"[warn] GET {url} network error ({exc}), attempt {attempt}/{retries}")
        if attempt < retries:
            time.sleep(RETRY_DELAY)
    raise RuntimeError(f"GET {url} failed after {retries} attempts")


# ---------------------------------------------------------------------------
# Game commands
# ---------------------------------------------------------------------------


def game_command(command: str) -> dict:
    """Send a game command (start / go / left / right) to the hub."""
    payload = {
        "apikey": API_KEY,
        "task": TASK_NAME,
        "answer": {"command": command},
    }
    return _post(VERIFY_URL, payload)


def _is_crash_response(resp: dict | None) -> bool:
    """Return True if the hub response means the rocket crashed or was shot down."""
    if not isinstance(resp, dict):
        return False
    message = str(resp.get("message", "")).lower()
    crash_message = str(resp.get("crashMessage", "")).lower()
    return bool(resp.get("crashed")) or any(
        word in (message + " " + crash_message)
        for word in ("crash", "destroyed", "shot", "zestrzel", "explod")
    )


# ---------------------------------------------------------------------------
# Frequency scanner & disarm
# ---------------------------------------------------------------------------


def _regex_extract(text: str) -> tuple[float, str] | None:
    """Pure-regex extraction of (frequency, detectionCode) from text."""
    # Try clean JSON first
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            freq = float(data["frequency"])
            code = str(data["detectionCode"])
            return freq, code
    except (ValueError, KeyError, TypeError):
        pass

    # Regex on quoted field names
    freq_match = re.search(r'"frequency"\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)', text)
    code_match = re.search(r'"detectionCode"\s*[=:]\s*"([^"]+)"', text)
    if freq_match and code_match:
        return float(freq_match.group(1)), code_match.group(1)

    # Last-resort: looser patterns
    freq_match2 = re.search(r'[Ff]requency[^\d]*([0-9]+(?:\.[0-9]+)?)', text)
    code_match2 = re.search(r'[Dd]etection[Cc]ode[^"\']*["\']([^"\']+)["\']', text)
    if freq_match2 and code_match2:
        return float(freq_match2.group(1)), code_match2.group(1)

    return None


def _extract_openrouter_text(response_json: dict) -> str | None:
    """Extract plain text content from an OpenRouter response."""
    try:
        choice = response_json["choices"][0]
        message = choice.get("message", {})
    except (KeyError, IndexError, TypeError):
        return None

    content = message.get("content")
    if isinstance(content, str):
        stripped = content.strip()
        return stripped or None

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
        joined = "\n".join(parts).strip()
        return joined or None

    return None


def _call_openrouter(prompt: str, *, model: str, tag: str) -> str | None:
    """Call OpenRouter and return normalized text content."""
    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = _extract_openrouter_text(resp.json())
        if content is None:
            print(f"  [{tag}] empty or unsupported OpenRouter response")
            return None
        return content
    except Exception as exc:
        print(f"  [{tag}] request failed: {exc}")
        return None


def _parse_move_keyword(text: str) -> str | None:
    """Extract a single move keyword from model output."""
    if re.search(r"\bgo\b", text, re.IGNORECASE):
        return "go"
    if re.search(r"\bleft\b", text, re.IGNORECASE):
        return "left"
    if re.search(r"\bright\b", text, re.IGNORECASE):
        return "right"
    return None


def _llm_extract(text: str) -> tuple[float, str] | None:
    """Ask a free LLM (OpenRouter) to clean the corrupted scanner JSON.

    Prompt: extract frequency (number) and detectionCode (string).
    Validates the result with regex before accepting it.
    Returns (frequency, detectionCode) or None on failure.
    """
    prompt = (
        "Extract 'frequency' and 'detectionCode' from this corrupted JSON string. "
        "Return only raw JSON with exactly two keys: frequency (number) and detectionCode (string).\n\n"
        + text
    )
    content = _call_openrouter(prompt, model=LLM_MODEL, tag="llm")
    if content is None:
        return None
    print(f"  [llm] cleaned: {content[:200]}")

    # Validate: frequency must be a number, detectionCode a non-empty string
    freq_ok = re.search(r'"frequency"\s*:\s*([0-9]+(?:\.[0-9]+)?)', content)
    code_ok = re.search(r'"detectionCode"\s*:\s*"([^"]+)"', content)
    if freq_ok and code_ok:
        return float(freq_ok.group(1)), code_ok.group(1)

    # Fallback: try parsing LLM output with regex
    return _regex_extract(content)


def _llm_interpret_scanner_status(text: str) -> str | None:
    """Ask an LLM to interpret whether the scanner response means CLEAR or TRAP."""
    prompt = (
        "The scanner returned this corrupted text. Respond with only one word: CLEAR if the message means the scanner is clear, "
        "or TRAP if it means an active radar trap is present. Do not add any explanation.\n\n"
        + text
    )
    content = _call_openrouter(prompt, model=LLM_MODEL, tag="llm")
    if content is None:
        return None
    print(f"  [llm] status interpret: {content}")

    if re.search(r"\bCLEAR\b", content, re.IGNORECASE):
        return "clear"
    if re.search(r"\bTRAP\b", content, re.IGNORECASE):
        return "trap"
    return None


def _extract_scanner_fields(text: str) -> tuple[float, str] | None:
    """Try to extract (frequency, detectionCode) from a (possibly malformed) response.

    Pipeline: 1) clear-check, 2) regex, 3) LLM+regex.
    Returns None if text indicates 'clear' or fields cannot be recovered.
    """
    if re.search(r'c\s*l[e]*a\s*r', text, re.IGNORECASE):
        return None

    result = _regex_extract(text)
    if result is not None:
        return result

    print("  [scanner] regex failed, trying LLM extraction...")
    return _llm_extract(text)


def scan_and_neutralise() -> dict | None:
    """Check the frequency scanner and disarm any active trap before moving."""
    for attempt in range(1, MAX_RETRIES + 1):
        scanner_url = f"{SCANNER_URL}?key={API_KEY}"
        raw = _get(scanner_url)
        print(f"  [scanner] raw: {raw[:120]}")

        status = None
        if re.search(r'c\s*l[e]*a\s*r', raw, re.IGNORECASE):
            status = "clear"
        elif re.search(r'frequency|detectionCode|"frequency"|"detectionCode"', raw, re.IGNORECASE):
            status = "trap"
        else:
            print("  [scanner] unclear text, interpreting with LLM...")
            status = _llm_interpret_scanner_status(raw)

        if status == "clear":
            print("  [scanner] clear - no threat")
            return None
        if status != "trap":
            print(f"  [scanner] unknown scanner status (attempt {attempt}/{MAX_RETRIES}), retrying...")
            time.sleep(RETRY_DELAY)
            continue

        result = _extract_scanner_fields(raw)
        if result is None:
            print(f"  [scanner] trap response unparseable (attempt {attempt}/{MAX_RETRIES}), retrying...")
            time.sleep(RETRY_DELAY)
            continue

        frequency, detection_code = result
        frequency = int(frequency)
        disarm_hash = hashlib.sha1(f"{detection_code}disarm".encode()).hexdigest()
        print(f"  [scanner] trap detected! freq={frequency}, code={detection_code}")
        print(f"  [disarm] hash={disarm_hash}")

        disarm_payload = {
            "apikey": API_KEY,
            "frequency": frequency,
            "disarmHash": disarm_hash,
        }
        resp = _post(SCANNER_URL, disarm_payload)
        print(f"  [disarm] response: {resp}")

        if _is_crash_response(resp):
            print("  [disarm] trap hit the rocket before neutralisation completed")
            return resp

        # Any 200 response here means success; some variants may return a message key
        msg = str(resp.get("message", resp.get("_raw", ""))).lower()
        if "error" in msg or "fail" in msg or "invalid" in msg:
            print(f"  [disarm] disarm failed (attempt {attempt}/{MAX_RETRIES}), retrying scan...")
            time.sleep(RETRY_DELAY)
            continue

        print("  [disarm] trap neutralised")
        return None

    raise RuntimeError("Could not neutralise scanner trap after max retries")


# ---------------------------------------------------------------------------
# Radio hint -> rock row
# ---------------------------------------------------------------------------

# Maritime direction terms mapped to a relative move mentioned in a hint.
_DIRECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r'\bdead\s+ahead\b|\bin front\b|\bfront\b|\bahead\b|\bcentral path\b|\bcenter(?:ed)?\b|'
            r'\bsame line\b|\bbow faces a rock\b|\bcockpit glass\b|\bcurrent heading\b|\bflight line\b|'
            r'\bcurrent line\b|\bforward line\b|\bthrough the middle\b|\broute through the middle\b|\bmiddle ends at a rock\b|'
            r'\bbow\b|\bnose\b|\bstraight out of the cockpit\b|\bforward corridor\b|\broute straight\b|'
            r'\bdirection\s+the\s+craft\s+is\s+already\s+facing\b|\balready\s+facing\b',
            re.IGNORECASE,
        ),
        "go",
    ),
    (
        re.compile(
            r'\bopposite\s+starboard\b|\bport side\b|\boff\s+port\b|\btoward\s+port\b|'
            r'\bport window\b|\bport flank\b|\bport wing\b|\bport lane\b|\bport-side\b|\bport\b|\blarboard\b',
            re.IGNORECASE,
        ),
        "left",
    ),
    (
        re.compile(
            r'\bopposite\s+port\b|\bstarboard side\b|\boff\s+starboard\b|\btoward\s+starboard\b|'
            r'\bstarboard window\b|\bstarboard flank\b|\bstarboard wing\b|\bstarboard lane\b|\bstarboard-side\b|\bstarboard\b',
            re.IGNORECASE,
        ),
        "right",
    ),
]

_OBSTACLE_MARKERS = re.compile(
    r'\brock\b|\bstone\b|\bblocked\b|\bobstacle\b|\bobstruction\b|\boccupied\b|\bhazard\b|\bdanger\b|'
    r'\bclosed\b|\bjammed\b|\bunsafe\b|\btrouble\b|\bthreat\b|\bnot\s+clear\b|\bnot\s+open\b|\bnot\s+free\b',
    re.IGNORECASE,
)

_SAFE_MARKERS = re.compile(
    r'\bclear\b|\bclean\b|\bopen\b|\bfree\b|\bunobstructed\b|\bempty\b|\bsafe\b|'
    r'\bnothing\b|\broom\b|\bno\s+issue\b|\bno\s+warning\b|\bno\s+threat\b|\bnothing\s+sits\b|'
    r'\bnothing\s+pressing\b|\boptions\b',
    re.IGNORECASE,
)

_CURATED_HINT_OVERRIDES: dict[str, str] = {
    "no warning lights show on the sides. the central path is blocked by a rock.": "right",
    "nothing sits off either wing. the rock occupies the path straight ahead.": "right",
    "there is nothing pressing in from port or starboard. the threat stands on the forward line.": "right",
    "the nose is aimed at solid trouble. both side lanes are still free.": "right",
    "the sides give you options, but the route through the middle ends at a rock.": "right",
    "the clean space is in front of the cockpit and out to starboard. the stone is sitting on the port side.": "left",
    "the clean space is in front of the cockpit and out to port. the stone is sitting on the starboard side.": "right",
}

# These phrases are now handled correctly by the general regex+LLM pipeline;
# bonus-mode specific overrides are no longer needed.
_BONUS_HINT_OVERRIDES: dict[str, str] = {}

_MIDDLE_ROUTE_HINT = re.compile(
    r'\bcentral path\b|\bpath straight ahead\b|\bstraight ahead\b|\bforward line\b|'
    r'\bthrough the middle\b|\broute through the middle\b|\bforward corridor\b|\bnose\b|\bmiddle\b',
    re.IGNORECASE,
)

_FORWARD_CENTER_HINT = re.compile(
    r'\bcurrent heading\b|\balready facing\b|\bdirection the craft is already facing\b|'
    r'\bflight line\b|\bcurrent line\b|\bcurrent trajectory\b|\bcockpit glass\b|'
    r'\bdirectly before\b|\bdirectly in front\b|\bstraight ahead\b|\bpointed straight\b|'
    r'\bbow\b|\bnose\b|\bcenter(?:ed)?\b|\bmiddle\b|\bforward\b',
    re.IGNORECASE,
)


def _directions_from_clause(text: str) -> set[str]:
    """Extract relative moves mentioned in a single hint clause."""
    directions: set[str] = set()
    if re.search(
        r'\beither\s+wing\b|\bboth\s+sides\b|\bthe\s+sides\b|\bboth\s+side\s+lanes\b|\bside\s+lanes\b|\beither\s+side\b|\bport\s+or\s+starboard\b',
        text,
    ):
        directions.update({"left", "right"})
    for pattern, move in _DIRECTION_PATTERNS:
        if pattern.search(text):
            directions.add(move)
    return directions


def _regex_interpret_blocked_move(text: str) -> str | None:
    """Return a blocked move from clause-level local regex patterns."""
    safe_moves, blocked_moves = _extract_hint_direction_evidence(text)

    if len(blocked_moves) == 1:
        return next(iter(blocked_moves))

    if not blocked_moves and len(safe_moves) == 2:
        for move in ("left", "go", "right"):
            if move not in safe_moves:
                return move

    return None


def _manual_blocked_move_override(hint: str) -> tuple[str | None, str | None]:
    """Return a curated blocked-move override from exact hints or semantic signatures."""
    hint_key = _normalise_hint(hint)
    exact_match = _CURATED_HINT_OVERRIDES.get(hint_key)
    if exact_match is not None:
        return exact_match, "manual-exact"

    return None, None


def _bonus_blocked_move_override(hint: str) -> tuple[str | None, str | None]:
    """Return bonus-only overrides for phrases that repeatedly derail the 6->4->2 sequence."""
    hint_key = _normalise_hint(hint)
    exact_match = _BONUS_HINT_OVERRIDES.get(hint_key)
    if exact_match is not None:
        return exact_match, "bonus-exact"

    return None, None


def _is_middle_route_hint(hint: str) -> bool:
    """Return True for hints whose wording around the middle route proved misleading."""
    return bool(_MIDDLE_ROUTE_HINT.search(hint))


def _is_forward_center_hint(hint: str) -> bool:
    """Return True for hints describing the obstacle as being on the front/center line."""
    return bool(_FORWARD_CENTER_HINT.search(hint))


def _llm_interpret_blocked_move(text: str) -> dict:
    """Use an LLM pair to determine which move is blocked by the rock."""
    result = {
        "blocked_move": None,
        "primary_raw": None,
        "validator_raw": None,
        "status": "failed",
    }
    prompt = (
        "Interpret this radio hint for a rocket on a 3x12 grid. "
        "Return only one word: left, go, or right. "
        "You must name the BLOCKED path only, meaning the move that would collide with the rock in the next column. "
        "Do not name an available or safe path. "
        "The wording may use older, more elaborate English rather than modern plain English. "
        "The wording may also include sailor slang, maritime idioms, and nautical direction terms. "
        "Treat words like open, clean, clear, free, safe, empty, and unobstructed as describing SAFE directions, not blocked ones. "
        "Treat words like rock, stone, blocked, obstacle, occupied, danger, and hazard as describing the BLOCKED direction. "
        "If the hint says the front/center path is blocked, answer go. "
        "If the hint says port/larboard/left is blocked, answer left. "
        "If the hint says starboard/right is blocked, answer right. "
        "Note: 'where a ship would call port' means left; 'where a ship would call starboard' means right. "
        "Note: 'carries the risk' or 'currently carries the risk' means that side is BLOCKED. "
        "Example: 'open space straight ahead and clean air to the left. The rock is on the starboard side.' -> right. "
        "Example: 'front is blocked, port side is open.' -> go. "
        "Example: 'The hazard sits where a ship would call starboard, while the nose still has room to travel.' -> right. "
        "Example: 'Port and starboard stay friendly. The bow, however, is aimed right at a stone.' -> go. "
        "Example: 'Starboard is the side that currently carries the risk. The bow and port side remain clear.' -> right. "
        "Example: 'The obstacle is resting beside port.' -> left. "
        "Do not return the safe move; return the blocked move only. Do not add any explanation.\n\n"
        + text
    )
    primary_content = _call_openrouter(prompt, model=LLM_MODEL, tag="llm-radio")
    if primary_content is None:
        return result

    result["primary_raw"] = primary_content

    primary_move = _parse_move_keyword(primary_content)
    print(f"  [llm-radio] blocked move: {primary_content}")
    if primary_move is None:
        return result

    validator_prompt = (
        "Validate the interpretation of this radio hint for a rocket on a 3x12 grid. "
        "Return only one word: left, go, or right. "
        "The returned word must be the BLOCKED move that would collide with the rock in the next column. "
        "Do not return a safe or available path. "
        "Assume the hint may use older, more elaborate English and sailor slang or maritime idioms. "
        "Safe directions may be described with words like open, clean, clear, free, safe, empty, and unobstructed. "
        "Blocked directions may be described with words like rock, stone, blocked, obstacle, occupied, danger, and hazard. "
        "Remember: 'where a ship would call port' means left is blocked; 'where a ship would call starboard' means right is blocked. "
        "Do not explain anything.\n\n"
        + text
    )
    validator_content = _call_openrouter(
        validator_prompt,
        model=LLM_VALIDATOR_MODEL,
        tag="llm-radio-check",
    )
    if validator_content is None:
        result["blocked_move"] = primary_move
        result["status"] = "primary-only"
        return result

    result["validator_raw"] = validator_content

    validator_move = _parse_move_keyword(validator_content)
    print(f"  [llm-radio-check] blocked move: {validator_content}")
    if validator_move is None:
        result["blocked_move"] = primary_move
        result["status"] = "primary-only"
        return result
    if validator_move != primary_move:
        print(
            f"  [llm-radio-check] disagreement: primary={primary_move}, "
            f"validator={validator_move}"
        )
        result["status"] = "disagreement"
        return result

    result["blocked_move"] = primary_move
    result["status"] = "consensus"
    return result


def get_blocked_move(
    current_row: int,
    *,
    use_manual_overrides: bool = True,
    use_bonus_overrides: bool = False,
    use_learned_memory: bool = True,
    allow_regex_first: bool = False,
) -> tuple[str | None, str, dict]:
    """Fetch the radio hint and return the blocked move plus metadata."""
    last_record: dict | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        resp = _post(MESSAGE_URL, {"apikey": API_KEY})
        hint = resp.get("hint", resp.get("message", resp.get("_raw", "")))
        print(f"  [radio] hint: {hint}")

        hint_key = _normalise_hint(str(hint))
        if use_bonus_overrides:
            bonus_blocked_move, bonus_source = _bonus_blocked_move_override(str(hint))
            if bonus_blocked_move is not None:
                print(f"  [radio] bonus blocked move: {bonus_blocked_move}")
                return bonus_blocked_move, str(hint), {
                    "hint_key": hint_key,
                    "source": bonus_source,
                    "llm_primary": None,
                    "llm_validator": None,
                    "regex_guess": None,
                }

        if use_manual_overrides:
            manual_blocked_move, manual_source = _manual_blocked_move_override(str(hint))
            if manual_blocked_move is not None:
                print(f"  [radio] curated blocked move: {manual_blocked_move}")
                return manual_blocked_move, str(hint), {
                    "hint_key": hint_key,
                    "source": manual_source,
                    "llm_primary": None,
                    "llm_validator": None,
                    "regex_guess": None,
                }

        if use_learned_memory:
            memory_blocked_move = _get_memorized_blocked_move(str(hint))
            if memory_blocked_move is not None:
                print(f"  [radio] memory blocked move: {memory_blocked_move}")
                return memory_blocked_move, str(hint), {
                    "hint_key": hint_key,
                    "source": "memory-learned",
                    "llm_primary": None,
                    "llm_validator": None,
                    "regex_guess": None,
                }

        if allow_regex_first:
            regex_blocked_move = _regex_interpret_blocked_move(str(hint))
            if regex_blocked_move is not None:
                print(f"  [radio] regex-first blocked move: {regex_blocked_move}")
                return regex_blocked_move, str(hint), {
                    "hint_key": hint_key,
                    "source": "regex-first",
                    "llm_primary": None,
                    "llm_validator": None,
                    "regex_guess": regex_blocked_move,
                }

        llm_result = _llm_interpret_blocked_move(str(hint))
        llm_blocked_move = llm_result.get("blocked_move")
        last_record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "hint": str(hint),
            "blocked_move": llm_blocked_move,
            "blocked_move_source": f"llm-{llm_result.get('status')}",
            "blocked_move_llm_primary": llm_result.get("primary_raw"),
            "blocked_move_llm_validator": llm_result.get("validator_raw"),
            "chosen_move": None,
            "move_source": None,
            "outcome": "unresolved",
            "crash_reason": None,
            "response_message": None,
        }
        if llm_blocked_move is not None:
            print(f"  [radio] LLM interpreted blocked move: {llm_blocked_move}")
            return llm_blocked_move, str(hint), {
                "hint_key": hint_key,
                "source": f"llm-{llm_result.get('status')}",
                "llm_primary": llm_result.get("primary_raw"),
                "llm_validator": llm_result.get("validator_raw"),
                "regex_guess": None,
            }

        if _is_middle_route_hint(str(hint)):
            print("  [radio] middle-route hint without trusted resolution; skipping regex fallback")
            print(f"  [radio] still unrecognised hint (attempt {attempt}/{MAX_RETRIES}): {hint}")
            if attempt >= 9:
                fallback_move = random.choice(_valid_commands_for_row(current_row))
                print(f"  [radio] random move fallback after attempt {attempt}: {fallback_move}")
                last_record["blocked_move_source"] = "random-move-fallback"
                last_record["fallback_move"] = fallback_move
                _record_hint_outcome(last_record)
                return None, str(hint), {
                    "hint_key": hint_key,
                    "source": "random-move-fallback",
                    "llm_primary": llm_result.get("primary_raw"),
                    "llm_validator": llm_result.get("validator_raw"),
                    "regex_guess": None,
                    "fallback_move": fallback_move,
                }
            time.sleep(RETRY_DELAY)
            continue

        regex_blocked_move = _regex_interpret_blocked_move(str(hint))
        if regex_blocked_move is not None:
            print(f"  [radio] fallback regex blocked move: {regex_blocked_move}")
            last_record["blocked_move"] = regex_blocked_move
            last_record["blocked_move_source"] = "regex-fallback"
            last_record["blocked_move_regex"] = regex_blocked_move
            return regex_blocked_move, str(hint), {
                "hint_key": hint_key,
                "source": "regex-fallback",
                "llm_primary": llm_result.get("primary_raw"),
                "llm_validator": llm_result.get("validator_raw"),
                "regex_guess": regex_blocked_move,
            }

        print(f"  [radio] still unrecognised hint (attempt {attempt}/{MAX_RETRIES}): {hint}")

        if attempt >= 9:
            fallback_move = random.choice(_valid_commands_for_row(current_row))
            print(f"  [radio] random move fallback after attempt {attempt}: {fallback_move}")
            last_record["blocked_move_source"] = "random-move-fallback"
            last_record["fallback_move"] = fallback_move
            _record_hint_outcome(last_record)
            return None, str(hint), {
                "hint_key": hint_key,
                "source": "random-move-fallback",
                "llm_primary": llm_result.get("primary_raw"),
                "llm_validator": llm_result.get("validator_raw"),
                "regex_guess": None,
                "fallback_move": fallback_move,
            }

        time.sleep(RETRY_DELAY)

    if last_record is not None:
        _record_hint_outcome(last_record)
    raise RuntimeError(f"Could not determine blocked move from radio hint after {MAX_RETRIES} retries")


# ---------------------------------------------------------------------------
# Piloting logic
# ---------------------------------------------------------------------------


def choose_move(
    current_row: int,
    blocked_move: str,
    col: int,
    target_row: int,
    hint: str,
    *,
    allow_memorized_safe_move: bool = True,
    prefer_bonus_center_escape: bool = False,
) -> tuple[str, dict]:
    """Return a move command plus metadata using deterministic center-first logic."""
    def next_row(command: str) -> int:
        if command == "left":
            return current_row - 1
        if command == "right":
            return current_row + 1
        return current_row

    valid_commands = _valid_commands_for_row(current_row)

    if allow_memorized_safe_move:
        memorized_move = _get_memorized_safe_move(hint, current_row, target_row, valid_commands)
        if memorized_move in valid_commands and memorized_move != blocked_move:
            print(f"  [hint-memory] reusing successful move: {memorized_move}")
            return memorized_move, {
                "source": "memory-success",
                "llm_primary": None,
                "llm_validator": None,
            }

    safe_commands = [command for command in valid_commands if command != blocked_move]

    if not safe_commands:
        raise RuntimeError(f"No safe commands available from row {current_row} with blocked move {blocked_move}")

    # Final step still has to land on the base row.
    if col == 11:
        for command in safe_commands:
            if next_row(command) == target_row:
                return command, {"source": "heuristic-final", "llm_primary": None, "llm_validator": None}

    # 1. Prefer the middle row whenever it is still safely reachable.
    for command in safe_commands:
        if next_row(command) == 2:
            return command, {"source": "heuristic-return-center", "llm_primary": None, "llm_validator": None}

    # Bonus runs repeatedly showed that for middle-row front/center hints,
    # moving toward the target side often crashes and the opposite side survives.
    if prefer_bonus_center_escape and current_row == 2 and blocked_move == "go" and _is_forward_center_hint(hint):
        if target_row < current_row and "right" in safe_commands:
            return "right", {"source": "bonus-center-escape", "llm_primary": None, "llm_validator": None}
        if target_row > current_row and "left" in safe_commands:
            return "left", {"source": "bonus-center-escape", "llm_primary": None, "llm_validator": None}

    # 2. If the middle row is unavailable, go toward the target row.
    if target_row < current_row and "left" in safe_commands:
        return "left", {"source": "heuristic-target", "llm_primary": None, "llm_validator": None}
    if target_row > current_row and "right" in safe_commands:
        return "right", {"source": "heuristic-target", "llm_primary": None, "llm_validator": None}
    if target_row == current_row and "go" in safe_commands:
        return "go", {"source": "heuristic-target", "llm_primary": None, "llm_validator": None}

    # 3. Otherwise take the remaining unblocked option in a stable order.
    for command in ("go", "left", "right"):
        if command in safe_commands:
            return command, {"source": "heuristic-fallback", "llm_primary": None, "llm_validator": None}

    raise RuntimeError(f"Could not choose a move from safe commands: {safe_commands}")


# ---------------------------------------------------------------------------
# Main solver loop
# ---------------------------------------------------------------------------


def run_solver() -> dict:
    """Run one complete attempt (possibly restarting on crash) until success."""
    attempt = 0
    while True:
        attempt += 1
        print(f"\n{'='*60}")
        print(f"[game] Starting attempt #{attempt}")
        result = _start_game()
        if result is not None and not _is_crash_response(result):
            return result


def run_grave_sequence(crash_steps: list[int] | None = None) -> dict:
    """Run the grave riddle sequence with intentional crashes at 6, 4, and 2."""
    planned_steps = crash_steps or GRAVE_CRASH_STEPS
    last_response: dict = {}

    for index, crash_step in enumerate(planned_steps, start=1):
        print(f"\n{'='*60}")
        print(f"[bonus] Stage #{index}: force one crash on step {crash_step}")
        result = _start_game(crash_on_step=crash_step)
        last_response = result or {}
        flag = _extract_flag(last_response)
        if flag:
            print(f"\n[bonus] FLAG: {flag}")
            return last_response

        actual_crash_step = last_response.get("_crash_step") if isinstance(last_response, dict) else None
        if actual_crash_step != crash_step:
            if _is_crash_response(last_response):
                print(
                    f"[bonus] Sequence failed: expected crash on step {crash_step}, "
                    f"got crash on step {actual_crash_step}."
                )
            else:
                print(
                    f"[bonus] Sequence failed: expected crash on step {crash_step}, "
                    "but the run finished without the planned crash."
                )
            return last_response

        print(f"[bonus] Confirmed crash on requested step {crash_step}.")

    print(f"\n{'='*60}")
    print("[bonus] Sequence complete. Sending one more start to check for a flag.")
    final_resp = game_command("start")
    print(f"[bonus] final start response: {json.dumps(final_resp, ensure_ascii=False)}")
    return final_resp


def _start_game(crash_on_step: int | None = None) -> dict | None:
    """Run a single game from start to finish. Returns final hub response on
    success, None if the rocket crashes (caller should restart)."""

    # --- Start ---
    resp = game_command("start")
    print(f"[start] response: {json.dumps(resp, ensure_ascii=False)}")

    # Extract target row from start response.
    # Hub may return fields like: target, targetRow, destination, base_row, etc.
    target_row = _extract_target_row(resp)
    if target_row is None:
        print("[start] WARNING: could not determine target_row from response, defaulting to 2")
        target_row = 2
    print(f"[start] target_row={target_row}")

    col = 1
    row = 2
    move_resp: dict = resp
    bonus_mode = crash_on_step is not None

    for step in range(1, 12):  # columns 1 to 11 inclusive (12th is the base)
        print(f"\n--- Step {step}: col={col}, row={row} ---")

        # A. Scan & neutralise
        scanner_resp = scan_and_neutralise()
        if _is_crash_response(scanner_resp):
            assert isinstance(scanner_resp, dict)
            scanner_resp["_crash_step"] = step
            print("[game] TRAP crash during scan/disarm - restarting")
            return scanner_resp

        # B. Get radio hint -> blocked move in the next column and hint text
        blocked_move, hint, hint_info = get_blocked_move(
            row,
            use_manual_overrides=not bonus_mode,
            use_bonus_overrides=False,
            use_learned_memory=not bonus_mode,
            allow_regex_first=bonus_mode,
        )
        valid_commands = _valid_commands_for_row(row)

        # C. Choose move
        if crash_on_step == step:
            move = str(hint_info.get("fallback_move")) if hint_info.get("source") == "random-move-fallback" else str(blocked_move)
            move_info = {
                "source": "intentional-crash" if hint_info.get("source") != "random-move-fallback" else "random-move-fallback",
                "llm_primary": None,
                "llm_validator": None,
            }
            print(f"  [bonus] forcing crash on step {step} with move '{move}'")
        elif hint_info.get("source") == "random-move-fallback":
            move = str(hint_info["fallback_move"])
            move_info = {
                "source": "random-move-fallback",
                "llm_primary": hint_info.get("llm_primary"),
                "llm_validator": hint_info.get("llm_validator"),
            }
        else:
            move, move_info = choose_move(
                row,
                str(blocked_move),
                col,
                target_row,
                hint,
                allow_memorized_safe_move=not bonus_mode,
                prefer_bonus_center_escape=bonus_mode,
            )
        print(f"  [move] choosing '{move}' (blocked={blocked_move}, cur_row={row}, target_row={target_row})")

        # Execute move
        move_resp = game_command(move)
        print(f"  [move] response: {json.dumps(move_resp, ensure_ascii=False)}")

        crash_reason = str(move_resp.get("crashReason", ""))
        outcome = "success"
        if _is_crash_response(move_resp):
            outcome = "planned_crash" if crash_on_step == step else "crash"

        _record_hint_outcome(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "step": step,
                "column": col,
                "row": row,
                "target_row": target_row,
                "valid_commands": valid_commands,
                "hint": hint,
                "blocked_move": blocked_move,
                "blocked_move_source": hint_info.get("source"),
                "blocked_move_llm_primary": hint_info.get("llm_primary"),
                "blocked_move_llm_validator": hint_info.get("llm_validator"),
                "blocked_move_regex": hint_info.get("regex_guess"),
                "chosen_move": move,
                "move_source": move_info.get("source"),
                "move_llm_primary": move_info.get("llm_primary"),
                "move_llm_validator": move_info.get("llm_validator"),
                "outcome": outcome,
                "crash_reason": crash_reason,
                "response_message": move_resp.get("message"),
            }
        )

        # Update local position
        if move == "left":
            row -= 1
        elif move == "right":
            row += 1
        col += 1

        # Check for crash / game over
        status = str(move_resp.get("status", move_resp.get("message", ""))).lower()
        if any(word in status for word in ("crash", "destroyed", "dead", "fail", "error", "shot", "explod")):
            move_resp["_crash_step"] = step
            print(f"[game] CRASH or SHOT DOWN - restarting ({status})")
            return move_resp

        # Check for victory / flag
        flag = _extract_flag(move_resp)
        if flag:
            print(f"\n[victory] FLAG: {flag}")
            return move_resp

        # Some APIs return the flag only after we reach col 12
        # The loop above runs steps 1-11; after step 11 col becomes 12 which is
        # the base. Check response for flag after the final move.

    # After last move (step 11, col now = 12) - check response once more
    print(f"\n--- Final position: col={col}, row={row} ---")
    return move_resp  # may contain the flag; caller checks


def _extract_target_row(resp: dict) -> int | None:
    """Parse target/base row from the start response."""
    if isinstance(resp.get("base"), dict) and "row" in resp["base"]:
        try:
            return int(resp["base"]["row"])
        except (ValueError, TypeError):
            pass

    if isinstance(resp.get("destination"), dict) and "row" in resp["destination"]:
        try:
            return int(resp["destination"]["row"])
        except (ValueError, TypeError):
            pass

    # Try common field names
    for key in ("target", "targetRow", "target_row", "base", "baseRow", "base_row",
                "destination", "dest", "destRow"):
        if key in resp:
            try:
                return int(resp[key])
            except (ValueError, TypeError):
                pass

    # Nested object with `row` inside a base/destination object
    if "row" in resp and "col" in resp:
        try:
            row = int(resp["row"])
            if 1 <= row <= 3:
                return row
        except (ValueError, TypeError):
            pass

    # Search nested structures
    for val in resp.values():
        if isinstance(val, dict):
            r = _extract_target_row(val)
            if r is not None:
                return r

    # Try regex on the serialised response
    serialised = json.dumps(resp)
    m = re.search(r'"(?:target|base|dest)[_\s]?[Rr]ow"\s*:\s*([123])', serialised)
    if m:
        return int(m.group(1))

    return None


def _extract_flag(resp: dict) -> str | None:
    """Return flag string if found in response, else None."""
    serialised = json.dumps(resp, ensure_ascii=False)
    m = re.search(r'\{FLG:[^}]+\}|\{\{[^}]+\}\}|FLG[_\-][A-Z0-9]+|flag\{[^}]+\}', serialised, re.IGNORECASE)
    if m:
        return m.group(0)
    return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    if _compact_hint_log():
        _persist_hint_files()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--graves",
        action="store_true",
        help="Run the 6->4->2 intentional crash sequence for the grave riddle.",
    )
    parser.add_argument(
        "--grave-step",
        type=int,
        choices=range(1, 12),
        metavar="N",
        help="Run one intentional-crash bonus stage on the given step number.",
    )
    args = parser.parse_args()

    if args.graves and args.grave_step is not None:
        parser.error("Use either --graves or --grave-step, not both.")

    if args.graves:
        final_resp = run_grave_sequence()
        output_file = BONUS_FILE
    elif args.grave_step is not None:
        final_resp = run_grave_sequence([args.grave_step])
        output_file = BONUS_FILE
    else:
        final_resp = run_solver()
        output_file = VERIFICATION_FILE

    print("\n" + "="*60)
    print("[done] Full final response:")
    print(json.dumps(final_resp, ensure_ascii=False, indent=2))

    flag = _extract_flag(final_resp)
    if flag:
        print(f"\n[flag] {flag}")
    else:
        print("\n[info] Flag not auto-detected; check response above.")

    output_file.write_text(
        json.dumps(final_resp, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[saved] {output_file}")


if __name__ == "__main__":
    main()
