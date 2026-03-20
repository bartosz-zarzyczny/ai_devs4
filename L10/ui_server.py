from __future__ import annotations

import http.server
import json
import os
import socketserver
from pathlib import Path

from drone_solver import (
    build_bonus_instructions,
    build_instructions,
    maybe_extract_flag,
    run_solution,
)

PORT = int(os.environ.get("PORT", "8080"))

os.chdir(os.path.dirname(os.path.abspath(__file__)))

L10_DIR = Path(__file__).resolve().parent


class DroneHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/instructions":
            self.write_json({"instructions": build_instructions()})
            return

        if self.path == "/api/bonus":
            self.write_json(
                {
                    "title": "Radom bonus",
                    "summary": "Fuksja widziala balon w Radomiu.",
                    "bonusFlag": "{FLG:RADOMAIRPORT}",
                    "flag": "{FLG:RADOMAIRPORT}",
                    "instructions": build_bonus_instructions(),
                    "expectedResult": "photo response from Radom balloon route",
                }
            )
            return

        if self.path == "/api/run":
            try:
                response = run_solution()
                flag = maybe_extract_flag(response)
                self.write_json({"response": response, "flag": flag})
            except Exception as exc:
                self.write_json({"error": str(exc)}, status=500)
            return

        if self.path == "/api/result":
            result_path = L10_DIR / "verification_result.json"
            if result_path.exists():
                self.write_json(json.loads(result_path.read_text(encoding="utf-8")))
            else:
                self.write_json({"error": "No result yet"}, status=404)
            return

        super().do_GET()

    def write_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(format % args)


def main():
    with socketserver.TCPServer(("", PORT), DroneHandler) as httpd:
        print(f"UI server running at http://localhost:{PORT}/ui.html")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
