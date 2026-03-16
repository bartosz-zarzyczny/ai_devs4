import requests, json, urllib.parse

URL = 'https://hub.ag3nts.org/verify'
API = '5f9f1207-390f-4032-b98a-72075b11e655'

payload = json.load(open('payload_to_send.json','r',encoding='utf-8'))
payload['apikey'] = API

r = requests.post(URL, json=payload, timeout=30)

with open('headers_dump.txt', 'w', encoding='utf-8') as f:
    f.write(f"STATUS: {r.status_code}\n")
    f.write(f"BODY: {r.text}\n\n")
    f.write("=== HEADERS ===\n")
    for k, v in r.headers.items():
        f.write(f"{k}: {v}\n")
        if 'FLG' in v or 'flag' in v.lower():
            f.write(f"  *** FLAG DETECTED ***\n")

print("Saved to headers_dump.txt")
print(open('headers_dump.txt', encoding='utf-8').read())
