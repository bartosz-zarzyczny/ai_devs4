#!/usr/bin/env python3
"""L15 UI server — display Savethem map and route."""

from __future__ import annotations

import http.server
import json
import os
import socketserver
from pathlib import Path
from urllib.parse import urlparse

L15_DIR = Path(__file__).resolve().parent
os.chdir(L15_DIR)

PORT = int(os.environ.get("PORT", "8015"))

VERIFICATION_FILE = L15_DIR / "verification_result.json"
TASK_PY = L15_DIR / "task.py"


def _load_json(path: Path) -> dict | None:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "":
            self.path = "/ui.html"
            return super().do_GET()

        if parsed.path == "/api/state":
            data = _load_json(VERIFICATION_FILE)
            self._json(data or {})
            return

        return super().do_GET()

    def _json(self, obj: object) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        pass


def main() -> None:
    with socketserver.TCPServer(("", PORT), Handler) as srv:
        srv.allow_reuse_address = True
        print(f"L15 UI server: http://localhost:{PORT}")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("Stopped.")


if __name__ == "__main__":
    main()
