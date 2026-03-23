#!/usr/bin/env python3
"""L11 UI server — browse sensor anomalies interactively."""

from __future__ import annotations

import http.server
import json
import os
import socketserver
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

L11_DIR = Path(__file__).resolve().parent
os.chdir(L11_DIR)

PORT = int(os.environ.get("PORT", "8080"))

ANOMALIES_FILE = L11_DIR / "anomalies.json"
VERIFICATION_FILE = L11_DIR / "verification_result.json"
SENSORS_ZIP = L11_DIR / "sensors.zip"


def _read_sensor_from_zip(fid: str) -> dict | None:
    """Read a single sensor JSON by file ID from sensors.zip."""
    if not SENSORS_ZIP.exists():
        return None
    target = f"{fid}.json"
    with zipfile.ZipFile(SENSORS_ZIP) as zf:
        for name in zf.namelist():
            if Path(name).name == target:
                return json.loads(zf.read(name).decode("utf-8"))
    return None


def _count_sensors() -> int:
    if not SENSORS_ZIP.exists():
        return 0
    with zipfile.ZipFile(SENSORS_ZIP) as zf:
        return sum(1 for n in zf.namelist() if n.endswith(".json"))


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
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

        if parsed.path == "/api/status":
            self.write_json(self._status())
            return

        if parsed.path == "/api/anomalies":
            self.write_json(self._anomalies(params))
            return

        if parsed.path == "/api/sensor":
            fid = params.get("id", [""])[0]
            self.write_json(self._sensor_detail(fid))
            return

        if parsed.path == "/api/verification":
            self.write_json(self._verification())
            return

        if parsed.path == "/api/bonus":
            self.write_json(self._bonus())
            return

        return super().do_GET()

    def write_json(self, data, status: int = 200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # quiet logger
        pass

    # ------------------------------------------------------------------
    def _status(self) -> dict:
        return {
            "anomalies_ready": ANOMALIES_FILE.exists(),
            "verification_ready": VERIFICATION_FILE.exists(),
            "sensors_zip": str(SENSORS_ZIP),
            "sensor_count": _count_sensors(),
        }

    def _anomalies(self, params: dict) -> dict:
        if not ANOMALIES_FILE.exists():
            return {"error": "anomalies.json not found — run task.py first"}
        data = json.loads(ANOMALIES_FILE.read_text(encoding="utf-8"))
        page = int(params.get("page", ["1"])[0])
        per_page = int(params.get("per_page", ["50"])[0])
        kind = params.get("kind", ["all"])[0]  # all | programmatic | note

        prog = data.get("programmatic_anomalies", {})
        note = data.get("note_anomalies", {})

        if kind == "programmatic":
            ids = sorted(prog.keys())
        elif kind == "note":
            ids = sorted(note.keys())
        else:
            ids = data.get("all_anomaly_ids", [])

        total = len(ids)
        start = (page - 1) * per_page
        page_ids = ids[start : start + per_page]

        items = []
        for fid in page_ids:
            items.append({
                "id": fid,
                "programmatic_reasons": prog.get(fid, []),
                "note_problem": note.get(fid),
            })

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "items": items,
            "summary": {
                "programmatic": len(prog),
                "note": len(note),
                "total": data.get("count", total),
                "total_files": data.get("total_files", 0),
            },
        }

    def _sensor_detail(self, fid: str) -> dict:
        if not fid:
            return {"error": "id param required"}
        raw = _read_sensor_from_zip(fid)
        if raw is None:
            return {"error": f"sensor file {fid}.json not found in sensors.zip"}
        anomalies_data: dict = {}
        if ANOMALIES_FILE.exists():
            ad = json.loads(ANOMALIES_FILE.read_text(encoding="utf-8"))
            anomalies_data = {
                "programmatic_reasons": ad.get("programmatic_anomalies", {}).get(fid, []),
                "note_problem": ad.get("note_anomalies", {}).get(fid),
            }
        return {"id": fid, "data": raw, "anomalies": anomalies_data}

    def _verification(self) -> dict:
        if not VERIFICATION_FILE.exists():
            return {"error": "verification_result.json not found — run task.py first"}
        return json.loads(VERIFICATION_FILE.read_text(encoding="utf-8"))

    def _bonus(self) -> dict:
        bonus_file = L11_DIR / "bonus_result.json"
        if not bonus_file.exists():
            return {"error": "bonus_result.json not found — run bonus_solver.py first"}
        return json.loads(bonus_file.read_text(encoding="utf-8"))


def main():
    print(f"L11 UI server starting on http://localhost:{PORT}")
    print(f"  Sensors ZIP : {SENSORS_ZIP}")
    print(f"  Anomalies   : {ANOMALIES_FILE}")
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
