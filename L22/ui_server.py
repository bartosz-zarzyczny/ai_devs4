#!/usr/bin/env python3
"""L22 UI server - phonecall task + bonus inspection.

Serves ui.html and exposes API endpoints to run task.py / bonus_solver.py
and stream logs to the browser.

Usage:
    python L22/ui_server.py
    open http://localhost:8082
"""

from __future__ import annotations

import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get("PORT", "8082"))
PORT_FALLBACK_SPAN = 10

L22_DIR = Path(__file__).resolve().parent
RESULT_FILE = L22_DIR / "verification_result.json"
BONUS_RESULT_FILE = L22_DIR / "bonus_result.json"
CONV_LOG = L22_DIR / "conversation.jsonl"

os.chdir(L22_DIR)

# ---------------------------------------------------------------------------
# Pipeline runner (background thread)
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_state: dict = {"running": False, "lines": [], "done": True, "exit_code": None, "mode": None}


def _run(mode: str) -> None:
    global _state
    script = L22_DIR / ("bonus_solver.py" if mode == "bonus" else "task.py")
    cmd = [sys.executable, str(script)]

    with _lock:
        _state = {"running": True, "lines": [], "done": False, "exit_code": None, "mode": mode}

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(L22_DIR),
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for line in proc.stdout:
            with _lock:
                _state["lines"].append(line.rstrip("\n"))
        proc.wait()
        with _lock:
            _state["running"] = False
            _state["done"] = True
            _state["exit_code"] = proc.returncode
    except Exception as exc:
        with _lock:
            _state["lines"].append(f"[ERROR] {exc}")
            _state["running"] = False
            _state["done"] = True
            _state["exit_code"] = -1


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

def _json(data) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def _load_json_file(path: Path) -> dict | None:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _load_conversation() -> list[dict]:
    if not CONV_LOG.exists():
        return []
    entries = []
    with open(CONV_LOG, encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
    return entries


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quiet access log
        pass

    def _send(self, code: int, body: bytes, ct: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/ui.html"):
            html = (L22_DIR / "ui.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
            return

        if path == "/api/status":
            with _lock:
                snap = dict(_state)
            result = _load_json_file(RESULT_FILE)
            bonus = _load_json_file(BONUS_RESULT_FILE)
            self._send(200, _json({"state": snap, "result": result, "bonus": bonus}))
            return

        if path == "/api/conversation":
            self._send(200, _json(_load_conversation()))
            return

        self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/run":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            mode = body.get("mode", "main")  # "main" or "bonus"
            with _lock:
                if _state["running"]:
                    self._send(409, b'{"error":"already running"}')
                    return
            t = threading.Thread(target=_run, args=(mode,), daemon=True)
            t.start()
            self._send(200, _json({"started": True, "mode": mode}))
            return

        self._send(404, b'{"error":"not found"}')


# ---------------------------------------------------------------------------
# Server startup
# ---------------------------------------------------------------------------

def start_server() -> None:
    port = PORT
    for attempt in range(PORT_FALLBACK_SPAN):
        try:
            with socketserver.TCPServer(("", port), Handler) as httpd:
                httpd.allow_reuse_address = True
                print(f"[ui] http://localhost:{port}")
                httpd.serve_forever()
            break
        except OSError:
            port += 1
    else:
        print(f"[ui] could not bind on ports {PORT}-{PORT + PORT_FALLBACK_SPAN - 1}")
        sys.exit(1)


if __name__ == "__main__":
    start_server()
