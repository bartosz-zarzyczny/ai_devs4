#!/usr/bin/env python3
"""Probe flaggengenerator with various password candidates."""
import os, time, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
API_KEY = os.environ["AI_DEVS_4_API_KEY"]
SHELL_URL = "https://hub.ag3nts.org/api/shell"


def shell(cmd: str) -> tuple[int, str]:
    time.sleep(4)
    resp = requests.post(SHELL_URL, json={"apikey": API_KEY, "cmd": cmd}, timeout=30)
    body = resp.json()
    result = body.get("data", body.get("message", ""))
    if isinstance(result, list):
        result = "\n".join(result)
    return resp.status_code, str(result)


candidates = [
    # Umlaut-correct butterfly names
    "Bläuling",
    "Weißling",
    "Großer Fuchs",
    "Großfuchs",
    "Kleiner Fuchs",
    "Schillerfalter",
    # Technical German butterfly valve (ECCS/cooling context)
    "Drosselklappe",
    "drosselklappe",
    "Schmetterlingsklappe",
    "Schmetterlingsventil",
    "Klappenventil",
    # Apollo variety - famous protected German butterfly
    "Apollo",
    "Apollofalter",
    # Less tried species
    "Kaisermantel",
    "kaisermantel",
    "Aurorafalter",
    "Aurora",
    "Monarchfalter",
    "Monarch",
    # Old High German forms
    "fifalter",
    "fivalter",
    "vifalter",
    "Schmetterling",
    "Fifalter",
]

for pw in candidates:
    status, result = shell(f"/bin/flaggengenerator {pw}")
    marker = "OK" if status == 200 else "xx"
    print(f"  [{marker}] {pw!r:30s}  {result[:60]}")
