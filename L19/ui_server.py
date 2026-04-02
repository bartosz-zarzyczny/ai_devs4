#!/usr/bin/env python3
"""L19 UI server - filesystem task + bonus easter egg.

Endpoints:
  GET  /              -> ui.html
  POST /api/run_main  -> build main FS + submit done -> main flag
  POST /api/run_bonus -> build main FS + /flag/ easter egg -> bonus flag
  GET  /api/status    -> natan_data.json / verification_result.json presence
  GET  /api/data      -> natan_data.json contents
  GET  /api/result    -> verification_result.json contents
  GET  /api/listfiles?path=<p> -> listFiles action on virtual FS
"""

from __future__ import annotations

import http.server
import json
import os
import socketserver
import sys
import time
import zipfile
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

L19_DIR = Path(__file__).resolve().parent
os.chdir(L19_DIR)
sys.path.insert(0, str(L19_DIR))

PORT = int(os.environ.get("PORT", "8019"))

DATA_FILE = L19_DIR / "natan_data.json"
RESULT_FILE = L19_DIR / "verification_result.json"

import requests
from dotenv import load_dotenv

load_dotenv(L19_DIR.parent / ".env")

VERIFY_URL = "https://hub.ag3nts.org/verify"
TASK_NAME = "filesystem"


def get_api_key() -> str:
    key = os.environ.get("AI_DEVS_4_API_KEY", "").strip().strip('"').strip("'")
    if not key:
        raise RuntimeError("AI_DEVS_4_API_KEY not set")
    return key


def post_fs(answer) -> dict:
    resp = requests.post(
        VERIFY_URL,
        json={"apikey": get_api_key(), "task": TASK_NAME, "answer": answer},
        timeout=45,
    )
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text[:500]}


# ---- main FS builder ----

def _load_main_payload() -> list:
    from task import (
        build_filesystem_payload,
        parse_announcements,
        parse_transactions,
        extract_persons,
        NATAN_ZIP_URL,
    )
    r = requests.get(NATAN_ZIP_URL, timeout=60)
    r.raise_for_status()
    zf = zipfile.ZipFile(BytesIO(r.content))
    raw = {
        n: zf.read(n).decode("utf-8", "replace")
        for n in zf.namelist()
        if not n.endswith("/")
    }
    cities = parse_announcements(raw.get("og\u0142oszenia.txt", ""))
    tr = parse_transactions(raw.get("transakcje.txt", ""))
    pers = extract_persons(raw.get("rozmowy.txt", ""))
    if "lopata" in tr:
        tr["lopaty"] = tr["lopata"]
    if "mlotek" in tr and "mlotki" not in tr:
        tr["mlotki"] = tr["mlotek"]
    if "wolowina" not in tr:
        tr["wolowina"] = ["Opalino"]

    # save checkpoint
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"cities": cities, "persons": pers, "goods": tr}, f, ensure_ascii=False, indent=2)

    return build_filesystem_payload(cities, pers, tr)


def run_main() -> dict:
    """Build main filesystem, call done, return log."""
    log = []
    actions = _load_main_payload()
    log.append({"step": "build_fs", "actions": len(actions)})

    batch = post_fs(actions)
    log.append({"step": "batch", "code": batch.get("code"), "actions_executed": batch.get("actions_executed")})

    done = post_fs({"action": "done"})
    log.append({"step": "done", "response": done})

    result = {"log": log, "flag": done.get("message", ""), "done": done}
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def run_bonus() -> dict:
    """Build main FS + /flag/ easter egg, then call done + read /debug."""
    log = []
    actions = _load_main_payload()
    log.append({"step": "build_fs", "actions": len(actions)})

    batch = post_fs(actions)
    log.append({"step": "batch", "code": batch.get("code"), "actions_executed": batch.get("actions_executed")})

    # create /flag directory
    r = post_fs({"action": "createDirectory", "path": "/flag"})
    log.append({"step": "mkdir_flag", "response": r})

    # ls -la order: a, f, g, l -> sizes must spell FLAG via chr()
    # a=70(F), f=76(L), g=65(A), l=71(G)
    mapping = [("a", 70), ("f", 76), ("g", 65), ("l", 71)]
    for name, size in mapping:
        resp = post_fs({"action": "createFile", "path": f"/flag/{name}", "content": " " * size})
        log.append({"step": f"create_/flag/{name}", "size": size, "chr": chr(size), "code": resp.get("code")})
        time.sleep(1.1)

    # list /flag - should show server-injected easter egg files
    listing = post_fs({"action": "listFiles", "path": "/flag"})
    log.append({"step": "listFiles_/flag", "entries": listing.get("entries", [])})

    # check /debug for easter egg message
    debug_listing = post_fs({"action": "listFiles", "path": "/debug"})
    log.append({"step": "listFiles_/debug", "response": debug_listing})

    done = post_fs({"action": "done"})
    log.append({"step": "done", "response": done})

    # read /debug after done
    debug_after = post_fs({"action": "listFiles", "path": "/debug"})
    log.append({"step": "listFiles_/debug_after_done", "response": debug_after})

    bonus_flag = ""
    for entry in listing.get("entries", []):
        name = entry.get("name", "")
        if name not in ("a", "f", "g", "l"):
            bonus_flag = f"easter egg triggered (check /debug): see log"
            break

    result = {
        "log": log,
        "flag_main": done.get("message", ""),
        "flag_listing": listing,
        "debug_listing": debug_listing,
        "debug_after_done": debug_after,
        "hint": "ls -la /flag sorted alpha: a f g l  -> sizes 70 76 65 71 -> chr = F L A G",
    }
    return result


# ---- HTTP handler ----

class Handler(http.server.SimpleHTTPRequestHandler):
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

        if parsed.path in ("/", "/ui.html"):
            self.path = "/ui.html"
            return super().do_GET()

        if parsed.path == "/api/status":
            self.write_json({
                "data_ready": DATA_FILE.exists(),
                "result_ready": RESULT_FILE.exists(),
            })
            return

        if parsed.path == "/api/data":
            if not DATA_FILE.exists():
                self.write_json({"error": "natan_data.json not found - run main first"}, 404)
                return
            self.write_json(json.loads(DATA_FILE.read_text(encoding="utf-8")))
            return

        if parsed.path == "/api/result":
            if not RESULT_FILE.exists():
                self.write_json({"error": "verification_result.json not found"}, 404)
                return
            self.write_json(json.loads(RESULT_FILE.read_text(encoding="utf-8")))
            return

        if parsed.path == "/api/listfiles":
            path = params.get("path", ["/"])[0]
            try:
                data = post_fs({"action": "listFiles", "path": path})
                self.write_json(data)
            except Exception as exc:
                self.write_json({"error": str(exc)}, 500)
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/run_main":
            try:
                result = run_main()
                self.write_json(result)
            except Exception as exc:
                self.write_json({"error": str(exc)}, 500)
            return

        if parsed.path == "/api/run_bonus":
            try:
                result = run_bonus()
                self.write_json(result)
            except Exception as exc:
                self.write_json({"error": str(exc)}, 500)
            return

        self.send_response(404)
        self.end_headers()

    def write_json(self, data, status: int = 200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # quiet


def main():
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.allow_reuse_address = True
        print(f"L19 UI server: http://localhost:{PORT}/ui.html")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
