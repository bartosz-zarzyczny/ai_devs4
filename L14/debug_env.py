#!/usr/bin/env python3
"""Debug .env loading"""
import os
from pathlib import Path
from dotenv import load_dotenv

env_file = Path('d:/Repo/AI_Devs4/ai_devs4/.env')
print(f'Loading from: {env_file}')
print(f'Exists: {env_file.exists()}')

load_dotenv(env_file)

url = os.getenv('NGROK_URL')
print(f'NGROK_URL type: {type(url)}')
print(f'NGROK_URL value: {repr(url)}')
print(f'NGROK_URL starts with https://xxxx: {url.startswith("https://xxxx") if url else "URL is None"}')

# Also check file contents
with open(env_file) as f:
    lines = f.readlines()
    for i, line in enumerate(lines, 1):
        if 'NGROK_URL' in line:
            print(f'Line {i}: {repr(line)}')