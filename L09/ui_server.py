from __future__ import annotations

import http.server
import json
import os
import socket
import socketserver
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mailbox_client import (
    solve_bonus_flag,
    zmail_get_inbox,
    zmail_get_messages,
    zmail_get_thread,
    zmail_help,
    zmail_reset,
    zmail_search,
    verify_mailbox_answer,
)
from task import solve_main_flag


PORT = int(os.environ.get("PORT", "8080"))
L09_DIR = Path(__file__).resolve().parent
os.chdir(L09_DIR)


class MyHandler(http.server.SimpleHTTPRequestHandler):
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
        params = parse_qs(parsed.query)

        if parsed.path == "/":
            self.path = "/ui.html"
            return super().do_GET()

        if parsed.path.startswith("/api/status"):
            self.write_json(self.status_payload())
            return

        if parsed.path.startswith("/api/help"):
            try:
                payload = zmail_help()
                self.write_json({"status": self.status_payload(), "help": payload})
            except Exception as error:
                self.write_json({"error": str(error)}, status=500)
            return

        if parsed.path.startswith("/api/inbox"):
            try:
                page = int(params.get("page", [1])[0])
                per_page = int(params.get("perPage", [5])[0])
                self.write_json(zmail_get_inbox(page=page, per_page=per_page))
            except Exception as error:
                self.write_json({"error": str(error)}, status=500)
            return

        if parsed.path.startswith("/api/thread"):
            try:
                thread_id = int(params.get("threadID", [0])[0])
                self.write_json(zmail_get_thread(thread_id))
            except Exception as error:
                self.write_json({"error": str(error)}, status=500)
            return

        if parsed.path.startswith("/api/messages"):
            try:
                raw_ids = params.get("ids", [""])[0]
                ids = json.loads(raw_ids) if raw_ids.startswith("[") else raw_ids
                self.write_json(zmail_get_messages(ids))
            except Exception as error:
                self.write_json({"error": str(error)}, status=500)
            return

        if parsed.path.startswith("/api/search"):
            try:
                query = params.get("query", [""])[0]
                page = int(params.get("page", [1])[0])
                per_page = int(params.get("perPage", [5])[0])
                self.write_json(zmail_search(query=query, page=page, per_page=per_page))
            except Exception as error:
                self.write_json({"error": str(error)}, status=500)
            return

        if parsed.path.startswith("/api/reset"):
            try:
                self.write_json(zmail_reset())
            except Exception as error:
                self.write_json({"error": str(error)}, status=500)
            return

        if parsed.path.startswith("/api/verify"):
            try:
                result = solve_main_flag()
                result_path = L09_DIR / "verification_result.json"
                payload = self.status_payload()
                payload["verification"] = result
                payload["verification_file"] = str(result_path)
                self.write_json(payload)
            except Exception as error:
                self.write_json({"error": str(error)}, status=500)
            return

        if parsed.path.startswith("/api/main-flag"):
            try:
                result = solve_main_flag()
                result_path = L09_DIR / "verification_result.json"
                payload = self.status_payload()
                payload["verification"] = result
                payload["verification_file"] = str(result_path)
                payload["main_flag"] = result.get("message")
                self.write_json(payload)
            except Exception as error:
                self.write_json({"error": str(error)}, status=500)
            return

        if parsed.path.startswith("/api/bonus"):
            try:
                result = solve_bonus_flag()
                result_path = L09_DIR / "bonus_flag_result.json"
                result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                payload = self.status_payload()
                payload["bonus_flag_result"] = result
                payload["bonus_flag_file"] = str(result_path)
                self.write_json(payload)
            except Exception as error:
                self.write_json({"error": str(error)}, status=500)
            return

        return super().do_GET()

    def do_POST(self):
        self.write_json({"error": "not found"}, status=404)

    def status_payload(self):
        verification_path = L09_DIR / "verification_result.json"
        bonus_path = L09_DIR / "bonus_flag_result.json"
        verification = None
        bonus_result = None
        if verification_path.exists():
            try:
                verification = json.loads(verification_path.read_text(encoding="utf-8"))
            except Exception:
                verification = None
        if bonus_path.exists():
            try:
                bonus_result = json.loads(bonus_path.read_text(encoding="utf-8"))
            except Exception:
                bonus_result = None
        return {
            "api_key_present": bool(os.getenv("AI_DEVS_4_API_KEY")) or (L09_DIR.parent / ".env").exists(),
            "zmail_url": "https://hub.ag3nts.org/api/zmail",
            "task": "mailbox",
            "ui_file": str(L09_DIR / "ui.html"),
            "client_file": str(L09_DIR / "mailbox_client.py"),
            "verification_file": str(verification_path),
            "verification": verification,
            "main_flag": verification.get("message") if isinstance(verification, dict) else None,
            "bonus_flag_file": str(bonus_path),
            "bonus_flag_result": bonus_result,
        }

    def write_json(self, payload, status=200):
        self.send_response(status)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        try:
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return


class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def choose_port(start_port: int, attempts: int = 20) -> int:
    for port in range(start_port, start_port + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"Nie znaleziono wolnego portu w zakresie {start_port}-{start_port + attempts - 1}")


if __name__ == "__main__":
    selected_port = choose_port(PORT)
    with ReusableTCPServer(("", selected_port), MyHandler) as httpd:
        print(f"UI Server is running on http://localhost:{selected_port}")
        import webbrowser

        webbrowser.open(f"http://localhost:{selected_port}/ui.html")
        httpd.serve_forever()
