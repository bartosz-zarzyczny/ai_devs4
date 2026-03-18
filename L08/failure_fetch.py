from __future__ import annotations

import json
import os
import re
from collections import Counter, deque
from pathlib import Path
from typing import Deque

import requests
import tiktoken

L08_DIR = Path(__file__).resolve().parent
REPO_ROOT = L08_DIR.parent
RAW_LOG_NAME = "failure.log"
COMPACT_LOG_NAME = "failure_compact.log"
VERIFICATION_FILE_NAME = "verification_result.json"
HUB_BASE = "https://hub.ag3nts.org/data"
TOKEN_BUDGET = 1500

RAW_LEVEL_PATTERN = re.compile(r"\b(INFO|WARN|WARNING|ERROR|ERRO|CRIT|DEBUG|TRACE|FATAL)\b", re.IGNORECASE)
COMPACT_LEVEL_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}\s+([IWECDFT])\b")
LINE_PATTERN = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) (\d{1,2}):(\d{2}):(\d{2})\] \[(\w+)\] (.*)$")
KNOWN_DEVICES = ["ECCS8", "WTRPMP", "WTANK07", "FIRMWARE", "STMTURB12", "PWR01", "WSTPOOL2"]
LEVEL_SHORT = {
    "INFO": "I",
    "WARN": "W",
    "WARNING": "W",
    "ERRO": "E",
    "ERROR": "E",
    "CRIT": "C",
    "DEBUG": "D",
    "TRACE": "T",
    "FATAL": "F",
}

COMMON_REPLACEMENTS = [
    (re.compile(r"\bPrimary feed acknowledgment\b", re.I), "feed ack"),
    (re.compile(r"\bWaste routing telemetry\b", re.I), "waste telemetry"),
    (re.compile(r"\bCoolant circulation pulse\b", re.I), "coolant pulse"),
    (re.compile(r"\bSteam pressure readback\b", re.I), "steam pressure"),
    (re.compile(r"\bThermal scan\b", re.I), "thermal scan"),
    (re.compile(r"\bBoot sequence checkpoint\b", re.I), "boot checkpoint"),
    (re.compile(r"\bSynchronization token\b", re.I), "sync token"),
    (re.compile(r"\bPower bus handshake\b", re.I), "power bus"),
    (re.compile(r"\bReservoir telemetry\b", re.I), "reservoir telemetry"),
    (re.compile(r"\bService heartbeat\b", re.I), "heartbeat"),
    (re.compile(r"\bActuator response packet\b", re.I), "actuator packet"),
    (re.compile(r"\bBaseline diagnostics\b", re.I), "baseline diag"),
    (re.compile(r"\bInput ripple\b", re.I), "input ripple"),
    (re.compile(r"\bFill trajectory\b", re.I), "fill trend"),
    (re.compile(r"\bPressure jitter\b", re.I), "pressure jitter"),
    (re.compile(r"\bFlow margin\b", re.I), "flow margin"),
    (re.compile(r"\bThermal drift\b", re.I), "thermal drift"),
    (re.compile(r"\bWaste heat relay\b", re.I), "heat relay"),
    (re.compile(r"\breported runaway outlet temperature\b", re.I), "runaway outlet temp"),
    (re.compile(r"\bProtection interlock initiated reactor trip\b", re.I), "trip engaged"),
    (re.compile(r"\bfinal trip complete because\b", re.I), "trip complete because"),
    (re.compile(r"\bsafe shutdown state\b", re.I), "safe shutdown"),
    (re.compile(r"\bcontrol loop latency remains within nominal margin\b", re.I), "control latency nominal"),
    (re.compile(r"\bruntime channel stays online\b", re.I), "runtime online"),
    (re.compile(r"\binput phase balance remains stable\b", re.I), "phase balance stable"),
    (re.compile(r"\bbuffer trend is unchanged\b", re.I), "buffer flat"),
    (re.compile(r"\brotation profile is smooth\b", re.I), "rotation smooth"),
    (re.compile(r"\bstartup profile remains within expected range\b", re.I), "startup ok"),
    (re.compile(r"\bno oscillation detected\b", re.I), "stable"),
    (re.compile(r"\bremains acceptable\b", re.I), "ok"),
    (re.compile(r"\baccepted by control bus\b", re.I), "bus ack"),
    (re.compile(r"\bcompleted successfully\b", re.I), "done"),
    (re.compile(r"\bno corrective action is required\b", re.I), "no action"),
    (re.compile(r"\bmonitoring continues without immediate trip\b", re.I), "monitoring"),
    (re.compile(r"\bcorrective ramp is queued\b", re.I), "corrective ramp queued"),
    (re.compile(r"\bdelayed subsystem poll\b", re.I), "poll delayed"),
    (re.compile(r"\bretry timer is active\b", re.I), "retry timer active"),
    (re.compile(r"\bextended operation may reduce efficiency\b", re.I), "efficiency risk"),
    (re.compile(r"\bavailable coolant inventory is no longer guaranteed\b", re.I), "coolant inventory unsafe"),
    (re.compile(r"\bprotective shutdown path is being enforced\b", re.I), "shutdown enforced"),
    (re.compile(r"\btracking continues without immediate trip\b", re.I), "tracking"),
    (re.compile(r"\bpressure jitter near\b", re.I), "pressure jitter near"),
    (re.compile(r"\bservice heartbeat for\b", re.I), "heartbeat"),
    (re.compile(r"\bpower bus handshake confirmed\b", re.I), "power bus ok"),
    (re.compile(r"\btelemetry sample accepted by control bus\b", re.I), "telemetry bus ack"),
    (re.compile(r"\breports normal transfer demand\b", re.I), "transfer normal"),
    (re.compile(r"\breports rising return temperature\b", re.I), "return temp rising"),
    (re.compile(r"\breports runaway outlet temperature\b", re.I), "runaway outlet temp"),
    (re.compile(r"\brecovery completed with degraded margin\b", re.I), "recovered degraded"),
    (re.compile(r"\btransient disturbed auxiliary pump control\b", re.I), "aux pump disturbed"),
    (re.compile(r"\bfill trajectory slower than expected\b", re.I), "fill slow"),
    (re.compile(r"\bcooling reserve trend keeps falling during load rise\b", re.I), "cooling reserve falling"),
    (re.compile(r"\bcoolant level is below critical reserve for sustained operation\b", re.I), "coolant reserve critical"),
    (re.compile(r"\bcoolant level below critical reserve sustained operation\b", re.I), "coolant reserve critical"),
    (re.compile(r"\bprotection interlock initiated reactor trip\b", re.I), "trip engaged"),
    (re.compile(r"\bconfirms safe shutdown state with all core operations halted\b", re.I), "safe shutdown halted"),
]

FILLER_WORDS = re.compile(
    r"\b(?:the|and|is|are|was|were|a|an|to|for|of|on|in|by|with|from|at|as|be|been|being|this|that|it|its|their|during|under|over|more|less|no|not|may|will|continues|continue|remains|remained|removing|without|immediate|current|currently)\b",
    re.I,
)

ENCODING = tiktoken.get_encoding("cl100k_base")


def read_env_key(env_path: Path, var_name: str) -> str | None:
    if not env_path.exists():
        return None
    text = env_path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(rf"^{re.escape(var_name)}\s*=\s*[\"']?(.*?)[\"']?\s*$", text, re.MULTILINE)
    return match.group(1) if match else None


def get_api_key() -> str:
    env_key = os.getenv("AI_DEVS_4_API_KEY")
    if env_key:
        return env_key.strip()

    env_path = REPO_ROOT / ".env"
    file_key = read_env_key(env_path, "AI_DEVS_4_API_KEY")
    if file_key:
        return file_key.strip()

    raise RuntimeError("Brak AI_DEVS_4_API_KEY w pliku .env lub środowisku.")


def build_log_url(api_key: str | None = None, log_name: str = RAW_LOG_NAME) -> str:
    key = api_key or get_api_key()
    return f"{HUB_BASE}/{key}/{log_name}"


def download_failure_log(target_path: Path | None = None, api_key: str | None = None) -> Path:
    destination = Path(target_path) if target_path else L08_DIR / RAW_LOG_NAME
    url = build_log_url(api_key, RAW_LOG_NAME)

    response = requests.get(url, timeout=60)
    response.raise_for_status()
    destination.write_bytes(response.content)
    return destination


def pick_device(body: str) -> str:
    for device in KNOWN_DEVICES:
        if device in body:
            return device
    match = re.search(r"\b([A-Z][A-Z0-9]{2,})\b", body)
    return match.group(1) if match else "UNK"


def compress_description(body: str, device: str) -> str:
    text = body

    for pattern, replacement in COMMON_REPLACEMENTS:
        text = pattern.sub(replacement, text)

    text = re.sub(rf"\b{re.escape(device)}\b", "", text)
    text = re.sub(r"\b(?:on|from|for|in|at|by)\s+[A-Z][A-Z0-9]{2,}\b", "", text)
    text = text.replace("Protection interlock initiated reactor trip", "trip engaged")

    parts: list[str] = []
    for fragment in re.split(r"[.;]", text):
        fragment = fragment.strip()
        if not fragment:
            continue
        fragment = FILLER_WORDS.sub(" ", fragment)
        fragment = re.sub(r"\s+", " ", fragment).strip(" .,:;")
        fragment = fragment.replace("  ", " ")
        if fragment:
            parts.append(fragment)

    cleaned = "; ".join(parts)
    cleaned = re.sub(r"\b(ack|ok|synced|stable|done|queued|active|flat|nominal|unsafe|enforced|monitoring|risk|low|high|rising|falling|declining|reduced|safe shutdown)\b", lambda m: m.group(1), cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "event"


def transform_failure_line(line: str) -> str | None:
    match = LINE_PATTERN.match(line)
    if not match:
        return None

    date, hour, minute, _second, level, body = match.groups()
    device = pick_device(body)
    short_level = LEVEL_SHORT.get(level.upper(), level[:1].upper())
    description = compress_description(body, device)
    hour_text = str(int(hour))
    return f"{date} {hour_text}:{minute} {short_level} {device}: {description}"


def count_tokens(text: str) -> int:
    return len(ENCODING.encode(text))


def parse_compact_line(line: str) -> tuple[str, str, str] | None:
    match = re.match(r"^(\d{4}-\d{2}-\d{2}) (\d{1,2}:\d{2}) ([IWECDFT]) ([A-Z0-9]+): (.+)$", line)
    if not match:
        return None
    date, time_text, level, device, body = match.groups()
    return date, time_text, level, device, body


def extract_focus_devices(text: str) -> list[str]:
    devices: list[str] = []
    seen: set[str] = set()
    for device in KNOWN_DEVICES:
        if device in text and device not in seen:
            seen.add(device)
            devices.append(device)
    for match in re.findall(r"\b[A-Z][A-Z0-9]{2,}\b", text):
        if match in seen or match in LEVEL_SHORT:
            continue
        if match not in devices:
            devices.append(match)
            seen.add(match)
    return devices


def extract_feedback_text(response: object) -> str:
    if isinstance(response, dict):
        for key in ("feedback", "message", "msg", "error", "reason", "detail", "details", "response", "hint"):
            value = response.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return json.dumps(response, ensure_ascii=False)
    if isinstance(response, str):
        return response
    return str(response)


def select_token_limited_lines(
    source_lines: list[str],
    max_tokens: int = TOKEN_BUDGET,
    focus_devices: list[str] | None = None,
    context_radius: int = 1,
) -> list[str]:
    seen: set[tuple[str, str]] = set()
    candidates: list[tuple[int, int, str, int, int]] = []
    severity_rank = {"C": 3, "E": 2, "W": 1}
    mandatory_indexes: set[int] = set()

    if focus_devices:
        focus_set = {device for device in focus_devices if device}
        for index, raw_line in enumerate(source_lines):
            if any(device in raw_line for device in focus_set):
                for offset in range(-context_radius, context_radius + 1):
                    neighbor = index + offset
                    if 0 <= neighbor < len(source_lines):
                        mandatory_indexes.add(neighbor)

    for index, raw_line in enumerate(source_lines):
        compact = transform_failure_line(raw_line)
        if not compact:
            continue

        parsed = parse_compact_line(compact)
        if not parsed:
            continue

        _date, _time, level, _device, body = parsed
        if level not in severity_rank:
            continue

        key = (level, body)
        if key in seen:
            continue
        seen.add(key)
        priority = severity_rank[level]
        if index in mandatory_indexes:
            priority = 10 + priority
        elif focus_devices and any(device in compact for device in focus_devices):
            priority = 8 + priority
        candidates.append((priority, index, compact, count_tokens(compact + "\n"), severity_rank[level]))

    selected: list[tuple[int, int, str, int, int]] = sorted(
        [item for item in candidates if item[1] in mandatory_indexes],
        key=lambda item: item[1],
    )

    selected_index_set = {item[1] for item in selected}
    total_tokens = count_tokens("\n".join(item[2] for item in selected) + ("\n" if selected else ""))

    pool = [item for item in candidates if item[1] not in selected_index_set]
    pool.sort(key=lambda item: (-item[0], item[1]))

    for item in pool:
        if total_tokens + item[3] > max_tokens:
            continue
        selected.append(item)
        selected_index_set.add(item[1])
        total_tokens += item[3]

    selected.sort(key=lambda item: item[1])
    return [item[2] for item in selected]


def build_compact_failure_log(
    source_path: Path | None = None,
    target_path: Path | None = None,
) -> Path:
    source = Path(source_path) if source_path else L08_DIR / RAW_LOG_NAME
    target = Path(target_path) if target_path else L08_DIR / COMPACT_LOG_NAME

    if not source.exists():
        raise FileNotFoundError(f"Brak pliku wejściowego: {source}")

    transformed: list[str] = []
    with source.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            compact = transform_failure_line(raw_line.rstrip("\r\n"))
            if compact:
                transformed.append(compact)

    target.write_text("\n".join(transformed) + "\n", encoding="utf-8")
    return target


def build_token_limited_failure_log(
    source_path: Path | None = None,
    target_path: Path | None = None,
    max_tokens: int = TOKEN_BUDGET,
    focus_devices: list[str] | None = None,
    context_radius: int = 1,
) -> dict:
    source = Path(source_path) if source_path else L08_DIR / RAW_LOG_NAME
    target = Path(target_path) if target_path else L08_DIR / COMPACT_LOG_NAME

    if not source.exists():
        raise FileNotFoundError(f"Brak pliku wejściowego: {source}")

    source_lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    selected_lines = select_token_limited_lines(
        source_lines,
        max_tokens=max_tokens,
        focus_devices=focus_devices,
        context_radius=context_radius,
    )
    text = "\n".join(selected_lines) + ("\n" if selected_lines else "")
    target.write_text(text, encoding="utf-8")

    return {
        "path": target,
        "line_count": len(selected_lines),
        "token_count": count_tokens(text),
        "max_tokens": max_tokens,
        "focus_devices": focus_devices or [],
    }


def submit_failure_for_verification(
    api_key: str,
    log_path: Path | None = None,
    task_name: str = "failure",
    answer_mode: str = "text",
) -> dict:
    source = Path(log_path) if log_path else L08_DIR / COMPACT_LOG_NAME
    if not source.exists():
        raise FileNotFoundError(f"Brak pliku do weryfikacji: {source}")

    log_text = source.read_text(encoding="utf-8", errors="replace")
    if answer_mode == "lines":
        answer_payload: object = [line for line in log_text.splitlines() if line.strip()]
    elif answer_mode == "object":
        answer_payload = json.dumps({"logs": log_text}, ensure_ascii=False)
    else:
        answer_payload = json.dumps({"logs": log_text}, ensure_ascii=False)

    payload = {
        "apikey": api_key,
        "task": task_name,
        "answer": answer_payload,
    }

    response = requests.post("https://hub.ag3nts.org/verify", json=payload, timeout=120)
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}

    if response.status_code >= 400:
        data = {**data, "status": response.status_code}
    return data


def process_verification_feedback(response: object) -> dict:
    feedback_text = extract_feedback_text(response)
    devices = extract_focus_devices(feedback_text)
    success = False
    if isinstance(response, dict):
        response_text = json.dumps(response, ensure_ascii=False)
        success = any(marker in response_text for marker in ("FLG", "flag", "success", "correct", "ok"))
    return {
        "success": success,
        "feedback": feedback_text,
        "focus_devices": devices,
    }


def run_verification_cycle(
    api_key: str,
    source_path: Path | None = None,
    target_path: Path | None = None,
    max_tokens: int = TOKEN_BUDGET,
    answer_mode: str = "text",
    max_rounds: int = 3,
) -> dict:
    history: list[dict] = []
    focus_devices: list[str] = []
    compact_path = Path(target_path) if target_path else (L08_DIR / COMPACT_LOG_NAME)
    source = Path(source_path) if source_path else (L08_DIR / RAW_LOG_NAME)

    for round_index in range(1, max_rounds + 1):
        compact_info = build_token_limited_failure_log(
            source_path=source,
            target_path=compact_path,
            max_tokens=max_tokens,
            focus_devices=focus_devices,
        )
        response = submit_failure_for_verification(api_key, compact_path, answer_mode=answer_mode)
        analysis = process_verification_feedback(response)
        history.append(
            {
                "round": round_index,
                "compact": {
                    "path": str(compact_info["path"]),
                    "line_count": compact_info["line_count"],
                    "token_count": compact_info["token_count"],
                    "focus_devices": compact_info["focus_devices"],
                },
                "response": response,
                "analysis": analysis,
            }
        )

        if analysis["success"]:
            break

        if analysis["focus_devices"]:
            focus_devices = analysis["focus_devices"]

    result = {
        "history": history,
        "final": history[-1] if history else {},
        "success": bool(history and history[-1]["analysis"].get("success")),
        "compact_file": str(compact_path),
    }
    verification_file = L08_DIR / VERIFICATION_FILE_NAME
    verification_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["verification_file"] = str(verification_file)
    return result


def _summarize_log(
    path: Path | None = None,
    head_limit: int = 80,
    tail_limit: int = 40,
) -> dict:
    log_path = Path(path) if path else L08_DIR / RAW_LOG_NAME
    source_url = None
    try:
        source_url = build_log_url(log_name=log_path.name)
    except Exception:
        source_url = None

    info = {
        "path": str(log_path),
        "exists": log_path.exists(),
        "size_bytes": log_path.stat().st_size if log_path.exists() else 0,
        "line_count": 0,
        "head": [],
        "tail": [],
        "levels": {},
        "first_nonempty": None,
        "last_nonempty": None,
        "source_url": source_url,
    }

    if not log_path.exists():
        return info

    tail: Deque[str] = deque(maxlen=max(1, tail_limit))
    levels = Counter()
    head: list[str] = []
    first_nonempty = None
    last_nonempty = None
    line_count = 0

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\r\n")
            line_count += 1

            if len(head) < max(1, head_limit):
                head.append(line)
            tail.append(line)

            if line.strip():
                if first_nonempty is None:
                    first_nonempty = line
                last_nonempty = line

            compact_level_match = COMPACT_LEVEL_PATTERN.match(line)
            if compact_level_match:
                levels[compact_level_match.group(1).upper()] += 1
            else:
                level_match = RAW_LEVEL_PATTERN.search(line)
                if level_match:
                    level = level_match.group(1).upper()
                    if level == "WARNING":
                        level = "WARN"
                    elif level == "ERROR":
                        level = "ERRO"
                    levels[level] += 1

    info.update(
        {
            "line_count": line_count,
            "head": head,
            "tail": list(tail),
            "levels": dict(sorted(levels.items())),
            "first_nonempty": first_nonempty,
            "last_nonempty": last_nonempty,
        }
    )
    return info


def summarize_failure_log(
    path: Path | None = None,
    head_limit: int = 80,
    tail_limit: int = 40,
) -> dict:
    return _summarize_log(path, head_limit=head_limit, tail_limit=tail_limit)


def summarize_compact_log(
    path: Path | None = None,
    head_limit: int = 40,
    tail_limit: int = 20,
) -> dict:
    summary = _summarize_log(path or (L08_DIR / COMPACT_LOG_NAME), head_limit=head_limit, tail_limit=tail_limit)
    if summary.get("exists"):
        try:
            summary["token_count"] = count_tokens((Path(summary["path"]).read_text(encoding="utf-8", errors="replace")))
        except Exception:
            summary["token_count"] = None
    return summary


def render_summary_text(summary: dict, label: str = "failure.log") -> str:
    if not summary.get("exists"):
        return f"Plik {label} nie został jeszcze pobrany."

    lines = [
        f'Plik: {summary["path"]}',
        f'Rozmiar: {summary["size_bytes"]} B',
        f'Liczba linii: {summary["line_count"]}',
    ]

    levels = summary.get("levels") or {}
    if levels:
        lines.append("Poziomy: " + ", ".join(f"{name}={count}" for name, count in levels.items()))

    if summary.get("first_nonempty"):
        lines.append("Pierwsza niepusta: " + summary["first_nonempty"])
    if summary.get("last_nonempty"):
        lines.append("Ostatnia niepusta: " + summary["last_nonempty"])

    return "\n".join(lines)
