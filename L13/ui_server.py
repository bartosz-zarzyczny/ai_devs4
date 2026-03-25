#!/usr/bin/env python3
"""
L13: Reactor — UI server.

Serves ui.html and proxies commands to hub.ag3nts.org/verify.
Maintains the last known game state so the browser can poll it.

Usage:
    python L13/ui_server.py
    # Then open http://localhost:8013/ in a browser.
"""

from __future__ import annotations

import http.server
import json
import os
import threading
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_KEY = os.environ.get("AI_DEVS_4_API_KEY", "")
HUB_URL = "https://hub.ag3nts.org/verify"
TASK = "reactor"
PORT = int(os.environ.get("PORT", "8013"))

L13_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_last_response: dict = {}


def _call_hub(command: str) -> dict:
    payload = {
        "apikey": API_KEY,
        "task": TASK,
        "answer": {"command": command},
    }
    resp = requests.post(HUB_URL, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # noqa: N802
        pass  # suppress access log noise

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, mime: str = "text/html; charset=utf-8") -> None:
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # --- GET ---

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path in ("/", "/ui.html"):
            self._send_file(L13_DIR / "ui.html")
            return

        if path == "/api/state":
            with _lock:
                self._send_json(_last_response)
            return

        self.send_response(404)
        self.end_headers()

    # --- POST ---

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path == "/api/command":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                req = json.loads(body)
                command = str(req.get("command", "wait"))
                result = _call_hub(command)
                with _lock:
                    global _last_response
                    _last_response = result
                self._send_json(result)
            except Exception as exc:
                self._send_json({"error": str(exc)}, 500)
            return

        self.send_response(404)
        self.end_headers()

    # --- OPTIONS (CORS preflight) ---

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if not API_KEY:
        print("ERROR: AI_DEVS_4_API_KEY not set in .env")
        return

    server = http.server.HTTPServer(("localhost", PORT), Handler)
    print(f"Reactor UI server: http://localhost:{PORT}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
