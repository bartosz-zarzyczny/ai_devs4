#!/usr/bin/env python3
"""
L14 UI Server — Debug interface

Serves a local HTTP server on port 8001 for debugging CSV data and testing tool endpoints.
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import os
import requests
import csv
from io import StringIO
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import threading

PORT = 8001
UI_DIR = Path(__file__).parent
CSV_URL_BASE = "https://hub.ag3nts.org/dane/s03e04_csv/"

# Cache CSV data
csv_cache = {}


def fetch_csv_list():
    """Fetch list of CSV files from the hub."""
    try:
        resp = requests.get(CSV_URL_BASE, timeout=10)
        resp.raise_for_status()
        import re
        pattern = r'href=[\'"]([\w\-\.]+\.csv)[\'"]'
        files = re.findall(pattern, resp.text)
        return files if files else []
    except Exception as e:
        print(f"Error fetching CSV list: {e}")
        return []


def load_csv_data():
    """Load all CSV files into cache."""
    global csv_cache
    
    csv_cache = {"items": {}}
    
    csv_files = fetch_csv_list()
    for csv_file in csv_files:
        try:
            url = CSV_URL_BASE + csv_file
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            
            csv_reader = csv.DictReader(StringIO(resp.text))
            for row in csv_reader:
                item = row.get('item') or row.get('nazwa') or row.get('product')
                city = row.get('city') or row.get('miasto') or row.get('location')
                
                if item and city:
                    item_lower = item.lower().strip()
                    if item_lower not in csv_cache["items"]:
                        csv_cache["items"][item_lower] = []
                    if city not in csv_cache["items"][item_lower]:
                        csv_cache["items"][item_lower].append(city)
        except Exception as e:
            print(f"Error loading {csv_file}: {e}")
    
    print(f"[*] Loaded {len(csv_cache['items'])} items from CSV")


class DebugHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for the debug UI."""
    
    def do_GET(self):
        """Handle GET requests."""
        path = urlparse(self.path).path
        
        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            html_file = UI_DIR / "ui.html"
            if html_file.exists():
                self.wfile.write(html_file.read_bytes())
            else:
                self.wfile.write(b"<h1>UI not found</h1>")
        
        elif path == "/api/items":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "count": len(csv_cache.get("items", {})),
                "items": list(csv_cache.get("items", {}).keys())[:50]  # First 50
            }).encode())
        
        elif path.startswith("/api/item/"):
            item_name = path.split("/")[-1]
            items_db = csv_cache.get("items", {})
            cities = items_db.get(item_name.lower(), [])
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "item": item_name,
                "cities": cities
            }).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        """Handle POST requests (for tool testing)."""
        path = urlparse(self.path).path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body)
        except:
            data = {}
        
        if path == "/api/test_search_item":
            # Test search_item endpoint
            query = data.get("query", "")
            items_db = csv_cache.get("items", {})
            
            # Fuzzy match
            cities = items_db.get(query.lower(), [])
            if not cities:
                for key in items_db:
                    if key in query.lower() or query.lower() in key:
                        cities = items_db[key]
                        break
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "query": query,
                "cities": cities
            }).encode())
        
        elif path == "/api/test_find_all":
            # Test find_all endpoint
            items_raw = data.get("items", [])
            items_db = csv_cache.get("items", {})
            
            all_city_sets = []
            for item in items_raw:
                cities = items_db.get(item.lower(), [])
                if not cities:
                    for key in items_db:
                        if item.lower() in key or key in item.lower():
                            cities = items_db[key]
                            break
                if cities:
                    all_city_sets.append(set(cities))
            
            if all_city_sets:
                common_cities = set.intersection(*all_city_sets)
            else:
                common_cities = set()
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "items": items_raw,
                "common_cities": list(common_cities)
            }).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress log spam."""
        if "GET /api/" not in format and "POST /api/" not in format:
            super().log_message(format, *args)


def start_server():
    """Start the debug UI server."""
    print(f"[*] Loading CSV data...")
    load_csv_data()
    
    print(f"[*] Starting UI server on http://localhost:{PORT}")
    server = HTTPServer(("127.0.0.1", PORT), DebugHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server stopped")
        server.shutdown()


if __name__ == "__main__":
    start_server()
