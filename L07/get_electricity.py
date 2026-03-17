#!/usr/bin/env python3
from pathlib import Path
import re, requests, sys, argparse


def read_env_key(env_path: Path, var: str):
    txt = env_path.read_text(encoding='utf-8')
    m = re.search(rf'^{re.escape(var)}\s*=\s*["\']?(.*?)["\']?\s*$', txt, re.M)
    if m:
        return m.group(1)
    return None


def main():
    p = Path(__file__).resolve().parent
    repo_root = p.parent
    env_path = repo_root / '.env'
    if not env_path.exists():
        print('ERROR: .env not found at', env_path)
        sys.exit(1)

    apikey = read_env_key(env_path, 'AI_DEVS_4_API_KEY')
    if not apikey:
        print('ERROR: AI_DEVS_4_API_KEY not found in .env')
        sys.exit(1)

    parser = argparse.ArgumentParser(description='Pobierz electricity.png z hub.ag3nts.org')
    parser.add_argument('--reset', action='store_true', help='Dodaj ?reset=1 do URL aby zresetować planszę')
    args = parser.parse_args()

    url = f'https://hub.ag3nts.org/data/{apikey}/electricity.png'
    if args.reset:
        url += '?reset=1'

    out = p / 'electricity.png'
    print('Pobieram:', url)
    try:
        r = requests.get(url, timeout=30)
    except Exception as e:
        print('REQUEST ERROR:', e)
        sys.exit(2)

    if r.status_code != 200:
        print('ERROR downloading image, status:', r.status_code)
        print(r.text[:500])
        sys.exit(3)

    out.write_bytes(r.content)
    print('Zapisano obraz do:', out)


if __name__ == '__main__':
    main()
