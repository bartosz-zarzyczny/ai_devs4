#!/usr/bin/env python3
"""L12 UI server - firmware task inspector.

Serves the browser UI and exposes endpoints for:
  GET  /api/status          - overall task status
  GET  /api/verification    - saved hub verification result
  GET  /api/agent_log       - agentic loop step log
  POST /api/shell           - proxy a single command to the remote VM shell API
  POST /api/reboot          - trigger VM reboot via the remote shell API

Usage:
    python L12/ui_server.py
    # then open http://localhost:8080
"""

from __future__ import annotations

import http.server
import json
import os
import socketserver
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

L12_DIR = Path(__file__).resolve().parent
load_dotenv(L12_DIR.parent / ".env")
os.chdir(L12_DIR)

API_KEY = os.environ["AI_DEVS_4_API_KEY"]
SHELL_URL = "https://hub.ag3nts.org/api/shell"
PORT = int(os.environ.get("PORT", "8080"))

VERIFICATION_FILE = L12_DIR / "verification_result.json"
AGENT_LOG_FILE = L12_DIR / "agent_log.json"
BONUS_RESULT_FILE = L12_DIR / "bonus_result.json"

# Rate-limit guard for the proxy endpoint
_last_shell: float = 0.0
SHELL_MIN_INTERVAL = 3.0  # seconds


def _proxy_shell(cmd: str) -> dict:
    """Forward a shell command to the remote VM, respecting the rate limit."""
    global _last_shell
    elapsed = time.time() - _last_shell
    if elapsed < SHELL_MIN_INTERVAL:
        time.sleep(SHELL_MIN_INTERVAL - elapsed)
    _last_shell = time.time()

    try:
        resp = requests.post(
            SHELL_URL,
            json={"apikey": API_KEY, "cmd": cmd},
            timeout=30,
        )
    except requests.RequestException as exc:
        return {"error": str(exc)}

    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}

    body["_http_status"] = resp.status_code
    return body


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self.path = "/ui.html"
            return super().do_GET()

        if parsed.path == "/api/status":
            self.write_json(self._status())
            return

        if parsed.path == "/api/verification":
            self.write_json(self._verification())
            return

        if parsed.path == "/api/agent_log":
            self.write_json(self._agent_log())
            return

        if parsed.path == "/api/bonus":
            self.write_json(self._bonus())
            return

        return super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw)
        except Exception:
            body = {}

        parsed = urlparse(self.path)

        if parsed.path == "/api/shell":
            cmd = body.get("cmd", "")
            if not cmd:
                self.write_json({"error": "cmd is required"}, 400)
                return
            result = _proxy_shell(cmd)
            self.write_json(result)
            return

        if parsed.path == "/api/reboot":
            result = _proxy_shell("reboot")
            self.write_json(result)
            return

        if parsed.path == "/api/bonus/run":
            self.write_json(self._run_bonus())
            return

        self.write_json({"error": "not found"}, 404)

    # ------------------------------------------------------------------

    def write_json(self, data, status: int = 200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # quiet

    # ------------------------------------------------------------------

    def _status(self) -> dict:
        verified = VERIFICATION_FILE.exists()
        agent_done = False
        flag = None
        if verified:
            try:
                vr = json.loads(VERIFICATION_FILE.read_text(encoding="utf-8"))
                agent_done = vr.get("code") == 0
                if agent_done:
                    flag = vr.get("message")
            except Exception:
                pass
        agent_log = AGENT_LOG_FILE.exists()
        agent_status = None
        if agent_log:
            try:
                log = json.loads(AGENT_LOG_FILE.read_text(encoding="utf-8"))
                agent_status = log.get("status")
            except Exception:
                pass
        bonus_flag = None
        if BONUS_RESULT_FILE.exists():
            try:
                br = json.loads(BONUS_RESULT_FILE.read_text(encoding="utf-8"))
                bonus_flag = br.get("flag")
            except Exception:
                pass
        return {
            "verified": verified,
            "solved": agent_done,
            "flag": flag,
            "bonus_flag": bonus_flag,
            "agent_log_ready": agent_log,
            "agent_status": agent_status,
        }

    def _verification(self) -> dict:
        if not VERIFICATION_FILE.exists():
            return {"error": "verification_result.json not found - run task.py first"}
        try:
            return json.loads(VERIFICATION_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"error": str(exc)}

    def _agent_log(self) -> dict:
        if not AGENT_LOG_FILE.exists():
            return {"error": "agent_log.json not found - run task.py first"}
        try:
            return json.loads(AGENT_LOG_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"error": str(exc)}

    def _bonus(self) -> dict:
        if not BONUS_RESULT_FILE.exists():
            return {"ready": False, "flag": None}
        try:
            return json.loads(BONUS_RESULT_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"error": str(exc)}

    def _run_bonus(self) -> dict:
        import base64
        result = _proxy_shell("/bin/flaggengenerator schmetterling")
        raw_data = result.get("data", "")
        flag = None
        try:
            flag = base64.b64decode(raw_data).decode("utf-8")
        except Exception:
            flag = raw_data
        out = {"ready": True, "flag": flag, "raw": raw_data, "http_status": result.get("_http_status")}
        BONUS_RESULT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        return out


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print(f"L12 UI server starting on http://localhost:{PORT}")
    print(f"  Verification : {VERIFICATION_FILE}")
    print(f"  Agent log    : {AGENT_LOG_FILE}")
    print("  Press Ctrl+C to stop.")
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
