"""
Rejestracja endpointu w AI Devs Hub.

Uruchomić po tym, jak serwer jest dostępny publicznie przez ngrok:
  python -m L03.submit
"""
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

AI_DEVS_API_KEY = os.environ["AI_DEVS_4_API_KEY"]
NGROK_DOMAIN = os.environ.get("NGROK_DOMAIN", "")
HUB_VERIFY_URL = "https://hub.ag3nts.org/verify"

PUBLIC_URL = f"https://{NGROK_DOMAIN}/"
SESSION_ID = "l03session06"


def submit():
    payload = {
        "apikey": AI_DEVS_API_KEY,
        "task": "proxy",
        "answer": {
            "url": PUBLIC_URL,
            "sessionID": SESSION_ID,
        },
    }
    print(f"Zgłaszam endpoint: {PUBLIC_URL}  (sessionID={SESSION_ID})")
    resp = requests.post(HUB_VERIFY_URL, json=payload, timeout=15)
    print(f"Status HTTP: {resp.status_code}")
    print(resp.text)


if __name__ == "__main__":
    submit()
