import http.server
import json
import os
import socket
import socketserver
import re
from urllib.parse import parse_qs, urlparse
from pathlib import Path

from failure_fetch import (
    build_token_limited_failure_log,
    download_failure_log,
    get_api_key,
    render_summary_text,
    summarize_compact_log,
    summarize_failure_log,
    run_verification_cycle,
)

PORT = int(os.environ.get("PORT", "8080"))
L08_DIR = Path(__file__).resolve().parent
os.chdir(L08_DIR)


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

        if parsed.path.startswith("/api/status"):
            head = int(params.get("head", [80])[0])
            tail = int(params.get("tail", [40])[0])
            self.write_json(self.status_payload(head_limit=head, tail_limit=tail))
            return

        if parsed.path.startswith("/api/download"):
            try:
                log_path = download_failure_log()
                payload = self.status_payload()
                payload["downloaded"] = str(log_path)
                payload["message"] = "failure.log został pobrany"
                self.write_json(payload)
            except Exception as error:
                self.write_json({"error": str(error)}, status=500)
            return

        if parsed.path.startswith("/api/compact"):
            try:
                compact_info = build_token_limited_failure_log()
                compact_path = compact_info["path"]
                payload = self.status_payload()
                payload["compact_file"] = str(compact_path)
                payload["compact_message"] = "failure_compact.log został utworzony"
                payload["compact_tokens"] = compact_info["token_count"]
                payload["compact_max_tokens"] = compact_info["max_tokens"]
                self.write_json(payload)
            except Exception as error:
                self.write_json({"error": str(error)}, status=500)
            return

        if parsed.path.startswith("/api/verify"):
            try:
                result = run_verification_cycle(get_api_key())
                payload = self.status_payload()
                payload["verification"] = result
                self.write_json(payload)
            except Exception as error:
                self.write_json({"error": str(error)}, status=500)
            return

        if parsed.path.startswith("/api/summary"):
            try:
                head = int(params.get("head", [80])[0])
                tail = int(params.get("tail", [40])[0])
                summary = summarize_failure_log(head_limit=head, tail_limit=tail)
                self.write_json(summary)
            except Exception as error:
                self.write_json({"error": str(error)}, status=500)
            return

        if parsed.path == "/":
            self.path = "/ui.html"
            return super().do_GET()

        return super().do_GET()

    def do_POST(self):
        self.write_json({"error": "not found"}, status=404)

    def status_payload(self, head_limit=80, tail_limit=40):
        raw_summary = summarize_failure_log(head_limit=head_limit, tail_limit=tail_limit)
        compact_summary = summarize_compact_log(head_limit=head_limit, tail_limit=tail_limit)
        verification_path = L08_DIR / "verification_result.json"
        verification = None
        verification_flag = None
        if verification_path.exists():
            try:
                verification = json.loads(verification_path.read_text(encoding="utf-8"))
                serialized = json.dumps(verification, ensure_ascii=False)
                match = re.search(r"\{FLG:[^}]+\}", serialized)
                if match:
                    verification_flag = match.group(0)
            except Exception:
                verification = None
        return {
            "api_key_present": bool(os.getenv("AI_DEVS_4_API_KEY")),
            "log_file": str(L08_DIR / "failure.log"),
            "compact_file": str(L08_DIR / "failure_compact.log"),
            "verification_file": str(verification_path),
            "verification": verification,
            "verification_flag": verification_flag,
            "compact_max_tokens": 1500,
            "raw": {
                **raw_summary,
                "summary_text": render_summary_text(raw_summary, label="failure.log"),
            },
            "compact": {
                **compact_summary,
                "summary_text": render_summary_text(compact_summary, label="failure_compact.log"),
            },
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
