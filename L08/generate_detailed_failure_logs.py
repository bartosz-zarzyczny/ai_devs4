#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

import requests

from failure_fetch import get_api_key

L08_DIR = Path(__file__).resolve().parent
SOURCE_FILE = L08_DIR / "failure.log"

LINE_PATTERN = re.compile(r'^\[(\d{4}-\d{2}-\d{2}) (\d{1,2}):(\d{2}):(\d{2})\] \[(\w+)\] (.*)$')

DEVICE_GROUPS = {
    "cooling": {"ECCS8", "WTRPMP", "WTANK07"},
    "power": {"PWR01", "FIRMWARE"},
    "heat": {"STMTURB12", "WSTPOOL2"},
    "all": {"ECCS8", "WTRPMP", "WTANK07", "FIRMWARE", "STMTURB12", "PWR01", "WSTPOOL2"},
}

FAILURE_TYPES = {
    "ECCS8": {
        "warn": "cooling headroom loss",
        "erro": "cooling control fault",
        "crit": "thermal runaway / reactor trip",
    },
    "WTRPMP": {
        "warn": "flow margin degradation",
        "erro": "pump suction / mechanical stress",
        "crit": "primary circulation loss",
    },
    "WTANK07": {
        "warn": "inventory / refill drift",
        "erro": "coolant reserve loss",
        "crit": "critical water reserve exhaustion",
    },
    "PWR01": {
        "warn": "power stability ripple",
        "erro": "auxiliary feed disturbance",
        "crit": "critical load shedding",
    },
    "FIRMWARE": {
        "warn": "control loop timing drift",
        "erro": "validation / watchdog fault",
        "crit": "startup safety gate failure",
    },
    "STMTURB12": {
        "warn": "steam pressure jitter",
        "erro": "turbine feedback loop fault",
        "crit": "energy conversion collapse",
    },
    "WSTPOOL2": {
        "warn": "waste heat relay saturation",
        "erro": "heat rejection bottleneck",
        "crit": "heat sink boundary breach",
    },
}

IMPACT = {
    "ECCS8": "reactor cooling margin drops",
    "WTRPMP": "coolant circulation becomes unstable",
    "WTANK07": "reservoir reserve can no longer be trusted",
    "PWR01": "auxiliary systems lose stable feed",
    "FIRMWARE": "automatic control enters degraded mode",
    "STMTURB12": "thermal conversion efficiency drops",
    "WSTPOOL2": "dissipation path saturates",
}

ACTION = {
    "ECCS8": "monitor / ramp / trip",
    "WTRPMP": "inspect / throttle / trip",
    "WTANK07": "reconcile / refill / shutdown",
    "PWR01": "stabilize / shed / isolate",
    "FIRMWARE": "retry / lock / safety stop",
    "STMTURB12": "damping / correction / stop",
    "WSTPOOL2": "relieve / tune / protect",
}


def classify(level: str, device: str) -> tuple[str, str, str]:
    level_key = level.lower()
    failure_type = FAILURE_TYPES.get(device, {}).get(level_key, "anomaly")
    impact = IMPACT.get(device, "system risk increases")
    action = ACTION.get(device, "observe")
    return failure_type, impact, action


def parse_source() -> list[tuple[str, str, str, str, str]]:
    events: list[tuple[str, str, str, str, str]] = []
    for raw_line in SOURCE_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LINE_PATTERN.match(raw_line)
        if not match:
            continue
        date, hour, minute, _second, level, body = match.groups()
        if level.upper() == "INFO":
            continue
        device = next((d for d in FAILURE_TYPES if d in body), "UNK")
        failure_type, impact, action = classify(level, device)
        short_time = f"{int(hour)}:{minute}"
        events.append((date, short_time, level[:1].upper(), device, f"type={failure_type}; impact={impact}; action={action}; note={body}"))
    return events


def filter_events(events: Iterable[tuple[str, str, str, str, str]], devices: set[str]) -> list[str]:
    lines: list[str] = []
    for date, time_text, level, device, note in events:
        if device not in devices:
            continue
        lines.append(f"{date} {time_text} {level} {device} | {note}")
    return lines


def write_variant(name: str, lines: list[str]) -> Path:
    path = L08_DIR / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def submit_variant(path: Path) -> dict:
    payload = {
        "apikey": get_api_key(),
        "task": "failure",
        "answer": json.dumps({"logs": path.read_text(encoding="utf-8")}, ensure_ascii=False),
    }
    response = requests.post("https://hub.ag3nts.org/verify", json=payload, timeout=120)
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    data["status_code"] = response.status_code
    return data


def main() -> None:
    events = parse_source()
    variants = {
        "failure_detailed_all.log": filter_events(events, DEVICE_GROUPS["all"]),
        "failure_detailed_cooling.log": filter_events(events, DEVICE_GROUPS["cooling"]),
        "failure_detailed_power.log": filter_events(events, DEVICE_GROUPS["power"]),
        "failure_detailed_heat.log": filter_events(events, DEVICE_GROUPS["heat"]),
    }

    print("Generuję pliki logów:")
    created: list[Path] = []
    for filename, lines in variants.items():
        path = write_variant(filename, lines)
        created.append(path)
        print(f"- {path.name}: {len(lines)} linii")

    print("\nWysyłka po kolei do API:")
    for path in created:
        result = submit_variant(path)
        print(f"[{path.name}] {result}")


if __name__ == "__main__":
    main()
