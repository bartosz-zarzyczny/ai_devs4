from __future__ import annotations

import base64
import http.server
import json
import mimetypes
import os
import socketserver
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

PORT = int(os.environ.get("PORT", "8082"))

L21_DIR = Path(__file__).resolve().parent
DANE_DIR = L21_DIR / "dane"
JSONL_PATH = L21_DIR / "session_raw.jsonl"
RESULT_PATH = L21_DIR / "verification_result.json"

os.chdir(L21_DIR)

# ---------------------------------------------------------------------------
# Pipeline runner (background thread)
# ---------------------------------------------------------------------------

_run_lock = threading.Lock()
_run_state: dict = {"running": False, "lines": [], "done": True, "exit_code": None, "mode": None}


def _run_pipeline(mode: str) -> None:
    """Execute task.py in a subprocess and stream lines into _run_state."""
    global _run_state
    task_script = L21_DIR / "task.py"
    cmd = [sys.executable, str(task_script)]
    if mode == "replay":
        cmd.append("--replay")
    elif mode == "listen":
        cmd.append("--listen")
    # else: full run (no extra flag)

    with _run_lock:
        _run_state = {"running": True, "lines": [], "done": False, "exit_code": None, "mode": mode}

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(L21_DIR),
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for line in proc.stdout:
            with _run_lock:
                _run_state["lines"].append(line.rstrip("\n"))
        proc.wait()
        with _run_lock:
            _run_state["running"] = False
            _run_state["done"] = True
            _run_state["exit_code"] = proc.returncode
    except Exception as exc:
        with _run_lock:
            _run_state["lines"].append(f"[ERROR] {exc}")
            _run_state["running"] = False
            _run_state["done"] = True
            _run_state["exit_code"] = -1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

META_TYPE = {
    "image/png": "image",
    "image/jpeg": "image",
    "image/gif": "image",
    "image/webp": "image",
    "audio/mpeg": "audio",
    "audio/wav": "audio",
    "audio/ogg": "audio",
    "application/json": "json",
    "text/xml": "text",
    "text/csv": "text",
    "text/plain": "text",
    "text/html": "text",
}


def load_signals() -> list[dict]:
    if not JSONL_PATH.exists():
        return []
    signals = []
    with open(JSONL_PATH, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            meta = raw.get("meta", "")
            kind = META_TYPE.get(meta, "unknown")
            if "attachment" not in raw:
                if "transcription" in raw:
                    kind = "text"
                elif raw.get("code") != 100:
                    kind = "noise"
                else:
                    kind = "noise"

            sig = {
                "index": i,
                "code": raw.get("code"),
                "message": raw.get("message", ""),
                "meta": meta,
                "kind": kind,
                "filesize": raw.get("filesize"),
            }

            if "transcription" in raw:
                sig["transcription"] = raw["transcription"]
            elif "attachment" in raw:
                # figure out filename that _save_signal_to_dane() would have created
                sig["has_attachment"] = True

            signals.append(sig)
    return signals


def find_dane_file(index: int) -> Path | None:
    """Return the decoded file path for signal <index> in dane/."""
    prefix = f"signal_{index:03d}"
    for f in DANE_DIR.glob(f"{prefix}.*"):
        if f.suffix not in (".b64", ".txt") and f.stem == prefix:
            return f
    # text attachments stored with different naming
    return None


def load_text_file(index: int) -> str | None:
    txt_path = DANE_DIR / f"signal_{index:03d}_transcription.txt"
    if txt_path.exists():
        return txt_path.read_text(encoding="utf-8")
    # xml/csv
    for ext in (".xml", ".csv"):
        p = DANE_DIR / f"signal_{index:03d}{ext}"
        if p.exists():
            return p.read_text(encoding="utf-8")
    # attachment_ files
    for f in DANE_DIR.glob(f"attachment_{index - 1}.*"):
        return f.read_text(encoding="utf-8")
    return None


def route_summary(signals: list[dict]) -> dict:
    by_kind: dict[str, int] = {}
    for s in signals:
        by_kind[s["kind"]] = by_kind.get(s["kind"], 0) + 1
    return by_kind


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


class RadioHandler(http.server.SimpleHTTPRequestHandler):
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
        if parsed.path == "/api/run":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            mode = body.get("mode", "replay")  # replay | full | listen
            with _run_lock:
                already = _run_state.get("running", False)
            if already:
                self.write_json({"error": "pipeline already running"}, 409)
                return
            t = threading.Thread(target=_run_pipeline, args=(mode,), daemon=True)
            t.start()
            self.write_json({"status": "started", "mode": mode})
            return
        self.write_json({"error": "not found"}, 404)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/":
            self.path = "/ui.html"
            return super().do_GET()

        # ---- API routes ------------------------------------------------

        if path == "/api/signals":
            signals = load_signals()
            by_kind = route_summary(signals)
            self.write_json({"signals": signals, "byKind": by_kind, "total": len(signals)})
            return

        if path == "/api/signal/text":
            idx = int(params.get("idx", [0])[0])
            text = load_text_file(idx)
            if text is not None:
                self.write_json({"index": idx, "text": text})
            else:
                self.write_json({"error": "not found"}, 404)
            return

        if path == "/api/signal/attachment":
            idx = int(params.get("idx", [0])[0])
            f = find_dane_file(idx)
            if f and f.exists():
                data = f.read_bytes()
                mime, _ = mimetypes.guess_type(str(f))
                mime = mime or "application/octet-stream"
                body = base64.b64encode(data).decode()
                self.write_json({"index": idx, "mime": mime, "data": body, "filename": f.name})
            else:
                self.write_json({"error": "not found"}, 404)
            return

        if path == "/api/run/status":
            with _run_lock:
                snap = dict(_run_state)
                snap["lineCount"] = len(snap["lines"])
                del snap["lines"]  # keep payload small
            self.write_json(snap)
            return

        if path == "/api/run/log":
            offset = int(params.get("offset", [0])[0])
            with _run_lock:
                lines = _run_state["lines"][offset:]
                running = _run_state["running"]
                done = _run_state["done"]
                exit_code = _run_state["exit_code"]
                total = len(_run_state["lines"])
            self.write_json({"lines": lines, "running": running, "done": done, "exitCode": exit_code, "total": total})
            return

        if path == "/api/result":
            if RESULT_PATH.exists():
                self.write_json(json.loads(RESULT_PATH.read_text(encoding="utf-8")))
            else:
                self.write_json({"error": "no result yet"}, 404)
            return

        if path.startswith("/dane/"):
            # Serve files from dane/ directly (images, audio)
            rel = unquote(path[len("/dane/"):])
            fpath = DANE_DIR / rel
            if fpath.exists() and fpath.is_file():
                mime, _ = mimetypes.guess_type(str(fpath))
                mime = mime or "application/octet-stream"
                data = fpath.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404)
                self.end_headers()
            return

        return super().do_GET()

    def write_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(fmt % args)


def main():
    with socketserver.TCPServer(("", PORT), RadioHandler) as httpd:
        print(f"UI server running at http://localhost:{PORT}/ui.html")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
