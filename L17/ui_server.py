from __future__ import annotations

import http.server
import json
import socketserver
from pathlib import Path
from urllib.parse import urlparse

from bonus_probe import BONUS_RESULT_FILE, run_bonus_probe
from task import L17_DIR, SCHEDULE_FILE, VERIFICATION_FILE, solve


PORT = 8017


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # noqa: N802
        pass

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, mime: str) -> None:
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
            self._send_file(L17_DIR / "ui.html", "text/html; charset=utf-8")
            return
        if path == "/api/status":
            payload = {
                "schedule": _read_json(SCHEDULE_FILE),
                "verification": _read_json(VERIFICATION_FILE),
                "bonus": _read_json(BONUS_RESULT_FILE),
            }
            self._send_json(payload)
            return
        if path == "/api/bonus-flag":
            bonus = _read_json(BONUS_RESULT_FILE)
            if isinstance(bonus, dict):
                self._send_json({"flag": bonus.get("flag")})
            else:
                self._send_json({"flag": None})
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/run":
            try:
                result = solve()
                self._send_json(result)
            except Exception as exc:
                self._send_json({"error": str(exc)}, 500)
            return
        if path == "/api/bonus":
            try:
                result = run_bonus_probe()
                self._send_json(result)
            except Exception as exc:
                self._send_json({"error": str(exc)}, 500)
            return
        self.send_response(404)
        self.end_headers()


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> None:
    with ReusableTCPServer(("localhost", PORT), Handler) as server:
        print(f"L17 UI server running at http://localhost:{PORT}/ui.html")
        server.serve_forever()


if __name__ == "__main__":
    main()