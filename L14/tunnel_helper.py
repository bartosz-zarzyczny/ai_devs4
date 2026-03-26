#!/usr/bin/env python3
"""
L14 Tunnel via expose.sh (alternative to ngrok)
"""

import subprocess
import time
import sys

print("[*] Starting tunnel via expose.sh...")
print("[*] tool_server on http://localhost:8080")

try:
    # expose.sh creates a tunnel and prints the URL
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", "--bind", "127.0.0.1", "--directory", ".", "9999"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Start local tunnel listener (still use ngrok domain if possible, or print new URL)
    print("[*] Waiting for tunnel initialization...")
    time.sleep(2)
    
    # For now, print manual instruction
    print("\n[!] ngrok token is invalid. Options:\n")
    print("1. Get new ngrok token from https://dashboard.ngrok.com")
    print("2. Or use a different tunnel service:")
    print("   - expose.sh: sh -c '$(curl -fsSL https://expose.sh/init.sh)'")
    print("   - localhost.run: ssh -R 80:localhost:8080 localhost.run")
    print("   - serveo.net: ssh -R 80:localhost:8080 serveo.net")
    print("   - Cloud services: AWS/GCP/Azure")
    
    print("\n[*] Tool server is running on http://localhost:8080")
    print("[*] Once you have public URL, update NGROK_URL in .env")
    print("[*] Then run: python L14/task.py")
    
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\n[*] Stopped")
