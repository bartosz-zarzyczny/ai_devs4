#!/usr/bin/env python3
"""Check CSV structure"""

import requests
import csv
from io import StringIO

CSV_URL_BASE = "https://hub.ag3nts.org/dane/s03e04_csv/"

for filename in ["cities.csv", "connections.csv", "items.csv"]:
    print(f"\n=== {filename} ===")
    try:
        resp = requests.get(CSV_URL_BASE + filename, timeout=10)
        lines = resp.text.splitlines()
        print(f"Total lines: {len(lines)}")
        print(f"First 3 lines:")
        for i, line in enumerate(lines[:3]):
            print(f"  {i}: {line}")
        
        # Parse header
        reader = csv.DictReader(StringIO(resp.text))
        if reader.fieldnames:
            print(f"Columns: {reader.fieldnames}")
            # Show first row
            for i, row in enumerate(reader):
                if i == 0:
                    print(f"Sample row 1: {row}")
                if i >= 1:
                    break
    except Exception as e:
        print(f"Error: {e}")
