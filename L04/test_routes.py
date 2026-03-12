#!/usr/bin/env python3
"""Batch-test route codes using send_payload.py.

Usage examples:
  python test_routes.py --apikey YOUR_KEY
  python test_routes.py --apikey YOUR_KEY --routes X-01 X-02 R-13 --wdp 0
  python test_routes.py --apikey YOUR_KEY --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Iterable


DEFAULT_ROUTES = [
    "X-01",
    "X-02",
    "X-03",
    "X-04",
    "X-05",
    "X-06",
    "X-07",
    "X-08",
    "X-09",
    "X-10",
    "X-11",
    "X-12",
    "X-13",
    "X-14",
    "X-15",
    "R-13",
    "R-16",
    "M-12",
    "M-03",
    "L-01",
]


def parse_response(output: str) -> tuple[str, str]:
    """Extract API code/message from send_payload.py logs."""
    code_match = re.search(r'"code"\s*:\s*([^,\n]+)', output)
    msg_match = re.search(r'"message"\s*:\s*"([^"]+)"', output)
    code = code_match.group(1).strip() if code_match else "N/A"
    msg = msg_match.group(1).strip() if msg_match else "No message parsed"
    return code, msg


def run_one(
    python_exe: str,
    script_path: str,
    apikey: str,
    route: str,
    wdp: str,
    dry_run: bool,
) -> tuple[int, str, str, str]:
    cmd = [
        python_exe,
        script_path,
        "--apikey",
        apikey,
        "--route",
        route,
        "--wdp",
        wdp,
    ]
    if dry_run:
        cmd.append("--dry-run")

    completed = subprocess.run(cmd, capture_output=True, text=True)
    merged = (completed.stdout or "") + "\n" + (completed.stderr or "")
    code, message = parse_response(merged)
    return completed.returncode, route, code, message


def format_table(rows: Iterable[tuple[int, str, str, str]]) -> str:
    rows = list(rows)
    headers = ["exit", "route", "api_code", "message"]
    widths = [
        max(len(headers[0]), *(len(str(r[0])) for r in rows)) if rows else len(headers[0]),
        max(len(headers[1]), *(len(r[1]) for r in rows)) if rows else len(headers[1]),
        max(len(headers[2]), *(len(r[2]) for r in rows)) if rows else len(headers[2]),
        max(len(headers[3]), *(len(r[3]) for r in rows)) if rows else len(headers[3]),
    ]

    def line(vals):
        return " | ".join(str(v).ljust(w) for v, w in zip(vals, widths))

    sep = "-+-".join("-" * w for w in widths)
    out = [line(headers), sep]
    for row in rows:
        out.append(line(row))
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apikey", required=True, help="API key passed to send_payload.py")
    parser.add_argument("--wdp", default="0", help="WDP override value")
    parser.add_argument("--routes", nargs="+", default=DEFAULT_ROUTES, help="Route codes to test")
    parser.add_argument("--dry-run", action="store_true", help="Do not perform network request")
    args = parser.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(here, "send_payload.py")
    python_exe = sys.executable

    if not os.path.exists(script_path):
        print(f"Missing script: {script_path}")
        return 2

    results = []
    for route in args.routes:
        print(f"Testing route: {route}")
        results.append(
            run_one(
                python_exe=python_exe,
                script_path=script_path,
                apikey=args.apikey,
                route=route,
                wdp=args.wdp,
                dry_run=args.dry_run,
            )
        )

    table = format_table(results)
    print("\nSummary:\n")
    print(table)

    # Save machine-readable output as well
    out_path = os.path.join(here, "route_test_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            [
                {"exit": e, "route": r, "api_code": c, "message": m}
                for (e, r, c, m) in results
            ],
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\nSaved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
