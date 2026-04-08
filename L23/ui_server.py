#!/usr/bin/env python3
"""L23 - shellaccess: lokalny serwer HTTP do inspekcji i recznego wykonywania komend.

Endpoints:
  GET  /                  - ui.html
  GET  /api/status        - stan plikow lokalnych (findings, log, wynik)
  POST /api/shell         - wyslij komende do zdalnego serwera
  POST /api/explore       - uruchom automatyczna eksploracje /data
  POST /api/submit        - wyslij finalny answer JSON przez echo na shellu

Usage:
    python L23/ui_server.py
    # Otworz http://localhost:8023/
"""

from __future__ import annotations

import http.server
import json
import socketserver
import threading
from pathlib import Path
from urllib.parse import urlparse

from task import (
    FINDINGS_FILE,
    OPERATION_LOG,
    RESULT_FILE,
    build_and_submit,
    explore_data,
    narrow_search,
    shell_cmd,
)

L23_DIR = Path(__file__).resolve().parent
PORT = 8023


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def _read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    lines = []
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if raw:
                try:
                    lines.append(json.loads(raw))
                except Exception:
                    lines.append({"raw": raw})
    except Exception:
        pass
    return lines


# ---------------------------------------------------------------------------
# Background runner
# ---------------------------------------------------------------------------

_runner_lock = threading.Lock()
_runner_result: dict = {}


def _run_explore_bg() -> None:
    global _runner_result
    try:
        findings = explore_data()
        findings = narrow_search(findings)
        with _runner_lock:
            _runner_result = {"status": "done", "findings": findings}
    except Exception as exc:
        with _runner_lock:
            _runner_result = {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: N802
        pass

    def _send_json(self, data, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, mime: str = "text/html; charset=utf-8") -> None:
        if not path.exists():
            self.send_response(404)
            self.end_headers()
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path in ("/", "/ui.html"):
            self._send_file(L23_DIR / "ui.html")
            return

        if path == "/api/status":
            log = _read_jsonl(OPERATION_LOG)
            self._send_json({
                "findings": _read_json(FINDINGS_FILE),
                "log": log[-50:],  # ostatnie 50 wpisow
                "verification": _read_json(RESULT_FILE),
                "runner": _runner_result,
            })
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            body = {}

        if path == "/api/shell":
            cmd = body.get("cmd", "").strip()
            if not cmd:
                self._send_json({"error": "cmd jest wymagany"}, 400)
                return
            output = shell_cmd(cmd)
            log = _read_jsonl(OPERATION_LOG)
            last = log[-1] if log else {}
            self._send_json({"cmd": cmd, "output": output, "raw_response": last.get("response")})
            return

        if path == "/api/explore":
            with _runner_lock:
                if _runner_result.get("status") == "running":
                    self._send_json({"status": "already running"})
                    return
                _runner_result.clear()
                _runner_result["status"] = "running"
            t = threading.Thread(target=_run_explore_bg, daemon=True)
            t.start()
            self._send_json({"status": "started"})
            return

        if path == "/api/submit":
            day = body.get("date", "")
            city = body.get("city", "")
            try:
                longitude = float(body.get("longitude", 0))
                latitude = float(body.get("latitude", 0))
            except (TypeError, ValueError):
                self._send_json({"error": "longitude i latitude musza byc liczbami"}, 400)
                return
            if not day or not city:
                self._send_json({"error": "date i city sa wymagane"}, 400)
                return
            result = build_and_submit(day, city, longitude, latitude)
            self._send_json(result)
            return

        self.send_response(404)
        self.end_headers()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> None:
    with ReusableTCPServer(("localhost", PORT), Handler) as server:
        print(f"L23 UI server: http://localhost:{PORT}/")
        server.serve_forever()


if __name__ == "__main__":
    main()
