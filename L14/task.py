#!/usr/bin/env python3
"""
L14 Task Solver — Negotiations

Registers tool endpoints to the hub and polls for verification result.
The agent uses these tools to find cities offering all required items.
"""

import os
import json
import time
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent.parent / ".env")
API_KEY = os.getenv("AI_DEVS_4_API_KEY")
NGROK_URL = os.getenv("NGROK_URL", "https://xxxx.ngrok.io")  # User must set this
HUB_URL = "https://hub.ag3nts.org/verify"
RESULT_FILE = Path(__file__).parent / "verification_result.json"
TASK_NAME = "negotiations"

# Output directories
RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)


def register_tools():
    """Register tool endpoints with the hub."""
    if not API_KEY:
        print("[!] Error: AI_DEVS_4_API_KEY not set in .env")
        return False
    
    if NGROK_URL.startswith("https://xxxx"):
        print("[!] Error: NGROK_URL not configured. Please set it in .env or pass it as argument.")
        print("   Example: NGROK_URL=https://abc123.ngrok.io")
        return False
    
    payload = {
        "apikey": API_KEY,
        "task": TASK_NAME,
        "answer": {
            "tools": [
                {
                    "URL": f"{NGROK_URL}/api/search_item",
                    "description": "Wyszukuje miasta sprzedające podany przedmiot. W polu 'params' podaj nazwę przedmiotu w języku naturalnym (np. 'kabel 10 metrów'). Zwraca listę nazw miast oddzielonych przecinkami."
                },
                {
                    "URL": f"{NGROK_URL}/api/find_all",
                    "description": "Zwraca miasta posiadające WSZYSTKIE podane przedmioty jednocześnie. W polu 'params' podaj nazwy przedmiotów oddzielone przecinkami (np. 'kabel 10m, śruba M8, turbina'). Zwraca listę miast oddzielonych przecinkami."
                }
            ]
        }
    }
    
    print(f"[*] Registering tools with hub...")
    print(f"    Tool 1: {NGROK_URL}/api/search_item")
    print(f"    Tool 2: {NGROK_URL}/api/find_all")
    
    try:
        resp = requests.post(HUB_URL, json=payload, timeout=15)
        print(f"[*] Registration response: {resp.status_code}")
        
        result = resp.json() if resp.text else {}
        print(f"    Result: {json.dumps(result, indent=2)}")
        
        return resp.status_code in [200, 201]
    except Exception as e:
        print(f"[!] Error registering tools: {e}")
        return False


def check_result(delay_seconds: int = 60):
    """Poll hub for verification result."""
    if not API_KEY:
        print("[!] Error: AI_DEVS_4_API_KEY not set in .env")
        return False
    
    print(f"[*] Waiting {delay_seconds} seconds for agent to process...")
    time.sleep(delay_seconds)
    
    payload = {
        "apikey": API_KEY,
        "task": TASK_NAME,
        "answer": {
            "action": "check"
        }
    }
    
    print(f"[*] Checking result from hub...")
    try:
        resp = requests.post(HUB_URL, json=payload, timeout=15)
        print(f"[*] Check response: {resp.status_code}")
        
        result = resp.json() if resp.text else {}
        print(f"    Full response: {json.dumps(result, indent=2)}")
        
        # Save result
        with open(RESULT_FILE, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[+] Result saved to {RESULT_FILE}")
        
        # Extract flag if present
        if "flag" in result:
            print(f"[+] FLAG: {result['flag']}")
        elif "answer" in result and isinstance(result["answer"], dict):
            if "flag" in result["answer"]:
                print(f"[+] FLAG: {result['answer']['flag']}")
        
        return True
    except Exception as e:
        print(f"[!] Error checking result: {e}")
        return False


def main():
    """Main entry point."""
    print(f"[*] L14 Negotiations Task Solver")
    print(f"[*] Task: {TASK_NAME}")
    print(f"[*] Hub: {HUB_URL}")
    
    # Check for --check flag
    if "--check" in sys.argv:
        print("[*] Mode: Check only (no registration)")
        check_result(delay_seconds=0)
        return
    
    # Normal flow: register and check
    if not register_tools():
        print("[!] Failed to register tools")
        return
    
    # Wait for agent processing
    check_result(delay_seconds=60)


if __name__ == "__main__":
    main()
