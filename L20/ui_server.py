from __future__ import annotations

import http.server
import json
import socketserver
from pathlib import Path
from urllib.parse import urlparse

from task import BONUS_FILE, DISCOVERY_FILE, FOOD_FILE, L20_DIR, ORDERS_FILE, RESULT_FILE, discover_bonus, fetch_requirements, run_discovery, run_solver


PORT = 8020


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
            self._send_file(L20_DIR / "ui.html", "text/html; charset=utf-8")
            return
        if path == "/api/status":
            self._send_json(
                {
                    "requirements": _read_json(FOOD_FILE),
                    "discovery": _read_json(DISCOVERY_FILE),
                    "orders": _read_json(ORDERS_FILE),
                    "verification": _read_json(RESULT_FILE),
                    "bonus": _read_json(BONUS_FILE),
                }
            )
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/api/fetch":
                self._send_json({"requirements": fetch_requirements()})
                return
            if path == "/api/discovery":
                requirements = fetch_requirements()
                self._send_json(run_discovery(requirements))
                return
            if path == "/api/run":
                self._send_json(run_solver())
                return
            if path == "/api/bonus":
                self._send_json(discover_bonus())
                return
        except Exception as exc:
            self._send_json({"error": str(exc)}, 500)
            return
        self.send_response(404)
        self.end_headers()


def _read_json(path: Path) -> dict | list | None:
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
        print(f"L20 UI server running at http://localhost:{PORT}/ui.html")
        server.serve_forever()


if __name__ == "__main__":
    main()