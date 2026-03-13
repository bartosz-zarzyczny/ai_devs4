#!/usr/bin/env python3
from __future__ import annotations

import argparse
import functools
import http.server
import os
import socketserver
import webbrowser


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve Railway UI")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-open", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(__file__))  # L05
    os.chdir(base_dir)

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=base_dir)

    with socketserver.TCPServer(("", args.port), handler) as httpd:
        url = f"http://localhost:{args.port}/ui/"
        print(f"Serving {base_dir}")
        print(f"Open: {url}")
        if not args.no_open:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        httpd.serve_forever()


if __name__ == "__main__":
    raise SystemExit(main())
