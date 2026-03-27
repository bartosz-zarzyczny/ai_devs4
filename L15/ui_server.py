#!/usr/bin/env python3
"""
L15 UI Server: Local HTTP server for route visualization.

Serves ui.html and provides API endpoints for route data.
"""

import os
import json
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PORT = 8015
SCRIPT_DIR = Path(__file__).parent

# Shared state (protected by lock)
_state_lock = threading.Lock()
_last_route = None
_last_map = None


class UIHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for UI server."""

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/":
            self.path = "/ui.html"

        if self.path == "/ui.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            html_file = SCRIPT_DIR / "ui.html"
            if html_file.exists():
                self.wfile.write(html_file.read_bytes())
            else:
                self.wfile.write(b"<h1>ui.html not found</h1>")

        elif self.path == "/api/state":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            with _state_lock:
                state = {
                    "route": _last_route,
                    "map": _last_map,
                }
            self.wfile.write(json.dumps(state).encode())

        elif self.path.startswith("/api/"):
            # Other API endpoints
            self.send_response(404)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())

        else:
            # Try to serve static files from L15 directory
            try:
                file_path = SCRIPT_DIR / self.path.lstrip("/")
                if file_path.exists() and file_path.is_file():
                    self.send_response(200)
                    content_type = "text/plain"
                    if self.path.endswith(".json"):
                        content_type = "application/json"
                    elif self.path.endswith(".html"):
                        content_type = "text/html"
                    self.send_header("Content-type", content_type)
                    self.end_headers()
                    self.wfile.write(file_path.read_bytes())
                else:
                    self.send_response(404)
                    self.end_headers()
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(f"Error: {e}".encode())

    def do_POST(self):
        """Handle POST requests (e.g., to update state)."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        if self.path == "/api/update_state":
            try:
                data = json.loads(body)
                global _last_route, _last_map
                with _state_lock:
                    _last_route = data.get("route")
                    _last_map = data.get("map")
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode())
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def main():
    """Start UI server."""
    server = HTTPServer(("localhost", PORT), UIHandler)
    print(f"[UI] Savethem UI server listening on http://localhost:{PORT}")
    print(f"[UI] Open in browser: http://localhost:{PORT}/ui.html")
    print(f"[UI] API endpoint: http://localhost:{PORT}/api/state")
    print(f"[UI] Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[UI] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
