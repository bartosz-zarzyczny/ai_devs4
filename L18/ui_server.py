#!/usr/bin/env python3
"""L18 - domatowo UI server

Local HTTP server for step-by-step operation inspection as per README plan.
Shows map, unit positions, action points, inspection logs.
"""

import json
import os
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

L18_DIR = Path(__file__).resolve().parent
LOG_FILE = L18_DIR / "operation_log.jsonl"
RESULT_FILE = L18_DIR / "verification_result.json"

WHERE_LETTERS = "ABCDEFGHIJK"  # columns A..K
VERIFY_URL = "https://hub.ag3nts.org/verify"
TASK_NAME = "domatowo"


def get_api_key() -> str:
    api_key = os.environ.get("AI_DEVS_4_API_KEY", "").strip().strip('"').strip("'")
    if not api_key:
        raise RuntimeError("AI_DEVS_4_API_KEY not set in environment")
    return api_key


def post_answer(answer: dict, *, timeout: int = 45) -> dict:
    payload = {"apikey": get_api_key(), "task": TASK_NAME, "answer": answer}
    resp = requests.post(VERIFY_URL, json=payload, timeout=timeout)
    try:
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"Non-JSON response from verify: {exc}\n{resp.text[:1000]}")
    
    # Log actions
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"request": payload, "response": data}, ensure_ascii=False) + "\n")
    
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} {data}")
    return data


def coord_to_index(coord: str) -> tuple[int, int]:
    c = coord[0].upper()
    r = int(coord[1:])
    x = WHERE_LETTERS.index(c)
    y = r - 1
    return x, y


def index_to_coord(x: int, y: int) -> str:
    return f"{WHERE_LETTERS[x]}{y+1}"


class DomatowoUIHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        
        if parsed_url.path == "/":
            self.serve_ui_html()
        elif parsed_url.path == "/api/status":
            self.serve_status()
        elif parsed_url.path == "/api/map":
            self.serve_map()
        elif parsed_url.path == "/api/objects":
            self.serve_objects()
        elif parsed_url.path == "/api/logs":
            self.serve_logs() 
        elif parsed_url.path == "/api/expenses":
            self.serve_expenses()
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        parsed_url = urlparse(self.path)
        
        if parsed_url.path == "/api/action":
            self.handle_action()
        else:
            self.send_error(404, "Not Found")
    
    def serve_ui_html(self):
        try:
            ui_file = L18_DIR / "ui.html"
            if ui_file.exists():
                with open(ui_file, "r", encoding="utf-8") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))
            else:
                self.send_error(404, "ui.html not found")
        except Exception as e:
            self.send_error(500, f"Error serving UI: {e}")
    
    def serve_json_response(self, data):
        try:
            response_json = json.dumps(data, ensure_ascii=False, indent=2)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(response_json.encode("utf-8"))
        except Exception as e:
            self.send_error(500, f"JSON error: {e}")
    
    def serve_status(self):
        try:
            # Get basic status from API
            map_resp = post_answer({"action": "help"})
            self.serve_json_response({
                "status": "connected",
                "message": map_resp.get("message", "OK"),
                "timestamp": time.time()
            })
        except Exception as e:
            self.serve_json_response({
                "status": "error", 
                "message": str(e),
                "timestamp": time.time()
            })
    
    def serve_map(self):
        try:
            map_resp = post_answer({"action": "getMap"})
            self.serve_json_response(map_resp)
        except Exception as e:
            self.serve_json_response({"error": str(e)})
    
    def serve_objects(self):
        try:
            objects_resp = post_answer({"action": "getObjects"})
            self.serve_json_response(objects_resp)
        except Exception as e:
            self.serve_json_response({"error": str(e)})
    
    def serve_logs(self):
        try:
            logs_resp = post_answer({"action": "getLogs"})
            self.serve_json_response(logs_resp)
        except Exception as e:
            self.serve_json_response({"error": str(e)})
    
    def serve_expenses(self):
        try:
            exp_resp = post_answer({"action": "expenses"})
            self.serve_json_response(exp_resp)
        except Exception as e:
            self.serve_json_response({"error": str(e)})
    
    def handle_action(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length)
                action_data = json.loads(post_data.decode('utf-8'))
                
                # Execute action via API
                result = post_answer(action_data)
                self.serve_json_response(result)
            else:
                self.send_error(400, "No action data")
        except Exception as e:
            self.serve_json_response({"error": str(e)})


def main():
    os.chdir(L18_DIR)
    server_address = ('localhost', 8000)
    httpd = HTTPServer(server_address, DomatowoUIHandler)
    
    print(f"L18 Domatowo UI Server running at http://localhost:8000/")
    print("Press Ctrl+C to stop")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


if __name__ == "__main__":
    main()