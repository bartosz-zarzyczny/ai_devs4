#!/usr/bin/env python3
"""L16 UI server — OKOeditor operation monitoring."""

import http.server
import json
import os
import requests
import socketserver
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from dotenv import load_dotenv

try:
    from .hidden_probe import probe_candidates
except ImportError:
    from hidden_probe import probe_candidates

load_dotenv()

L16_DIR = Path(__file__).resolve().parent
os.chdir(L16_DIR)

PORT = int(os.environ.get("PORT", "8080"))
API_KEY = os.getenv("AI_DEVS_4_API_KEY")
HUB_URL = "https://hub.ag3nts.org/verify"

SKOLWIN_INCIDENT_ID = "380792b2c86d9c5be670b3bde48e187b"
KOMAROWO_INCIDENT_ID = "bcdfc393f811cc05d3a189c679f50659"


def send_api_request(answer_payload):
    """Send request to hub API and return response."""
    payload = {
        "apikey": API_KEY,
        "task": "okoeditor",
        "answer": answer_payload
    }
    try:
        response = requests.post(HUB_URL, json=payload, timeout=10)
        try:
            return response.json()
        except Exception as e:
            return {
                "error": f"Failed to parse JSON response: {str(e)}",
                "status_code": response.status_code,
                "text": response.text[:500]
            }
    except Exception as e:
        return {
            "error": f"Request failed: {str(e)}"
        }


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)

        try:
            if parsed.path == "/api/hidden-probe":
                content_length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
                payload = json.loads(raw_body)
                result = self._hidden_probe(payload)
                self.write_json(result)
                return

            self.write_json({"error": "Not found"}, status=404)
        except Exception as e:
            print(f"ERROR in do_POST: {e}", flush=True)
            import traceback
            traceback.print_exc()
            self.write_json({"error": str(e)}, status=500)

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        try:
            if parsed.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                html = (L16_DIR / "ui.html").read_text(encoding="utf-8")
                body = html.encode("utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if parsed.path == "/ui.html":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                html = (L16_DIR / "ui.html").read_text(encoding="utf-8")
                body = html.encode("utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if parsed.path == "/api/status":
                self.write_json(self._status())
                return

            if parsed.path == "/api/step1":
                result = self._step1()
                self.write_json(result)
                return

            if parsed.path == "/api/step2":
                result = self._step2()
                self.write_json(result)
                return

            if parsed.path == "/api/step3":
                result = self._step3()
                self.write_json(result)
                return

            if parsed.path == "/api/step4":
                result = self._finish()
                self.write_json(result)
                return

            # 404
            self.write_json({"error": "Not found"}, status=404)
        except Exception as e:
            print(f"ERROR in do_GET: {e}", flush=True)
            import traceback
            traceback.print_exc()
            self.write_json({"error": str(e)}, status=500)

    def write_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Log all requests for debugging
        print(f"[{self.client_address[0]}] {format % args}", flush=True)

    # ------------------------------------------------------------------

    def _status(self) -> dict:
        return {
            "task": "okoeditor",
            "status": "ready",
            "steps": [
                {"id": 1, "name": "Zmień klasyfikację Skolwina na zwierzęta", "api_action": "update_report"},
                {"id": 2, "name": "Oznacz zadanie Skolwina jako wykonane", "api_action": "update_task"},
                {"id": 3, "name": "Dodaj raport o ruchu ludzi w Komarowie", "api_action": "add_incident"},
                {"id": 4, "name": "Finalizacja zmian (action: done)", "api_action": "done"}
            ],
            "hidden_probe_defaults": ["Mickiewicz", "Miłosz", "Milosz", "Cichosza", "Cichosha"]
        }

    def _step1(self) -> dict:
        """Zmiana klasyfikacji raportu Skolwin na zwierzęta."""
        try:
            answer = {
                "action": "update",
                "page": "incydenty",
                "id": SKOLWIN_INCIDENT_ID,
                "title": "MOVE04 Obserwacja zwierząt nieopodal miasta Skolwin",
                "content": "Czujniki zarejestrowały szybko poruszające się zwierzęta w pobliżu Skolwina. Obiekty przemieszczały się nieregularnie wzdłuż rzeki. Analiza wykazała, że obserwowano bobry i inne zwierzęta wodne. Sygnały pochodziły z naturalnych źródeł aktywności zwierząt."
            }
            result = send_api_request(answer)
            return {
                "step": 1,
                "description": "Zmiana klasyfikacji raportu Skolwina",
                "request": answer,
                "response": result,
                "success": result.get("code") == 110
            }
        except Exception as e:
            return {
                "step": 1,
                "error": str(e),
                "success": False
            }

    def _step2(self) -> dict:
        """Oznaczenie zadania Skolwin jako wykonane."""
        try:
            answer = {
                "action": "update",
                "page": "zadania",
                "id": SKOLWIN_INCIDENT_ID,
                "content": "Widziano bobry i inne zwierzęta w okolicach Skolwina.",
                "done": "YES"
            }
            result = send_api_request(answer)
            return {
                "step": 2,
                "description": "Oznaczenie zadania Skolwina jako wykonane",
                "request": answer,
                "response": result,
                "success": result.get("code") == 110
            }
        except Exception as e:
            return {
                "step": 2,
                "error": str(e),
                "success": False
            }

    def _step3(self) -> dict:
        """Dodanie raportu o ruchu ludzi w Komarowie."""
        try:
            answer = {
                "action": "update",
                "page": "incydenty",
                "id": KOMAROWO_INCIDENT_ID,
                "title": "MOVE01 Trudne do klasyfikacji ruchy nieopodal miasta Komarowo",
                "content": "Wykryto ruch ludzi i pojazdy w okolicach miasta Komarowo."
            }
            result = send_api_request(answer)
            return {
                "step": 3,
                "description": "Dodanie raportu o ruchu ludzi w Komarowie",
                "request": answer,
                "response": result,
                "success": result.get("code") == 110
            }
        except Exception as e:
            return {
                "step": 3,
                "error": str(e),
                "success": False
            }

    def _finish(self) -> dict:
        """Finalizacja zmian."""
        try:
            answer = {"action": "done"}
            result = send_api_request(answer)
            return {
                "step": 4,
                "description": "Finalizacja zmian",
                "request": answer,
                "response": result,
                "success": result.get("code") == 111,
                "flag": result.get("flag")
            }
        except Exception as e:
            return {
                "step": 4,
                "error": str(e),
                "success": False
            }

    def _hidden_probe(self, payload: dict) -> dict:
        candidates = payload.get("candidates", [])
        result = probe_candidates(candidates)
        return {
            "success": True,
            "probe": result,
        }


if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"OKOeditor UI Server listening on http://localhost:{PORT}")
        httpd.serve_forever()
