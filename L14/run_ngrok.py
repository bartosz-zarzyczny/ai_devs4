#!/usr/bin/env python3
"""
Quick ngrok tunnel launcher for L14 tool server
"""

import os
import time
from pyngrok import ngrok
from dotenv import load_dotenv

load_dotenv()

# Get ngrok authtoken
auth_token = os.getenv("NGROK_API_KEY")
ngrok_domain = os.getenv("NGROK_DOMAIN")

if not auth_token:
    print("[!] Error: NGROK_API_KEY not set in .env")
    exit(1)

print(f"[*] Configuring ngrok with authtoken...")
ngrok.set_auth_token(auth_token)

print(f"[*] Starting ngrok tunnel on port 8080...")
try:
    # Connect ngrok tunnel
    public_url = ngrok.connect(8080, "http")
    print(f"[+] Ngrok tunnel active: {public_url}")
    print(f"[*] Keep this running while L14 task executes...")
    print(f"[*] Press Ctrl+C to stop")
    
    # Keep running
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n[*] Stopping ngrok...")
    ngrok.kill()
    print("[*] Done")
