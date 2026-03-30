#!/usr/bin/env python3
"""
L16 - OKOeditor: Zapisz help z API
"""

import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("AI_DEVS_4_API_KEY")
HUB_URL = "https://hub.ag3nts.org/verify"

def main():
    payload = {
        "apikey": API_KEY,
        "task": "okoeditor",
        "answer": {
            "action": "help"
        }
    }
    
    print("Pobieranie help z API...")
    response = requests.post(HUB_URL, json=payload)
    result = response.json()
    
    # Zapisz do pliku
    with open("L16/api_help.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"Zapisano do L16/api_help.json")
    print(f"\nZawartość:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
