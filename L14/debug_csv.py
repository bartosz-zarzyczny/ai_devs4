#!/usr/bin/env python3
"""Quick debug: test CSV list fetching"""

import requests
import re

CSV_URL_BASE = "https://hub.ag3nts.org/dane/s03e04_csv/"
print(f"[*] Fetching from: {CSV_URL_BASE}")

try:
    resp = requests.get(CSV_URL_BASE, timeout=10)
    print(f"[*] Status: {resp.status_code}")
    print(f"[*] Content length: {len(resp.text)} chars")
    print(f"[*] First 800 chars:\n{resp.text[:800]}\n")
    
    pattern = r'href=[\'\"]([\w\-\.]+\.csv)[\'"]'
    files = re.findall(pattern, resp.text)
    print(f"[*] Found {len(files)} CSV files:")
    for f in files:
        print(f"    - {f}")
    
    if files:
        print(f"\n[*] Testing first file...")
        url = CSV_URL_BASE + files[0]
        r2 = requests.get(url, timeout=10)
        print(f"    Status: {r2.status_code}, Lines: {len(r2.text.splitlines())}")
        print(f"    First line: {r2.text.splitlines()[0]}")
except Exception as e:
    print(f"[!] Error: {e}")
