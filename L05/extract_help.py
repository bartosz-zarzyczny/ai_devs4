import json, sys

with open('logs/railway_requests.log', 'r', encoding='utf-8') as f:
    for line in f:
        try:
            entry = json.loads(line.strip())
            if entry.get('direction') == 'in':
                body = entry.get('body', {})
                if isinstance(body, dict) and 'help' in body:
                    sys.stdout.write(json.dumps(body, indent=2, ensure_ascii=False))
                    sys.stdout.flush()
                    break
        except:
            pass
