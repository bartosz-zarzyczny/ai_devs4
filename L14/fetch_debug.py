#!/usr/bin/env python3
import requests, os, html as htmllib
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")
API_KEY = os.getenv("AI_DEVS_4_API_KEY")

r = requests.get("https://hub.ag3nts.org/debug?apikey=" + API_KEY, timeout=10)
text = r.text

# Find the main output area
marker = 'class="out"'
idx = text.find(marker)
if idx >= 0:
    chunk = text[idx + len(marker):]
    end = chunk.find("</pre>")
    content = htmllib.unescape(chunk[:end] if end >= 0 else chunk[:8000])
    print(content)
else:
    # Dump raw HTML after <body>
    body = text.find("<body")
    print(text[body:body + 6000] if body >= 0 else text[2000:8000])
