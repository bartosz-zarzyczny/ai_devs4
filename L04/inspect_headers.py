import requests, json, urllib.parse, base64

URL = 'https://hub.ag3nts.org/verify'
API = '5f9f1207-390f-4032-b98a-72075b11e655'

payload = json.load(open('payload_to_send.json','r',encoding='utf-8'))
payload['apikey'] = API

r = requests.post(URL, json=payload, timeout=30)
print('STATUS:', r.status_code)
print('BODY:', r.text)
print()
print('=== ALL RESPONSE HEADERS ===')
for k, v in r.headers.items():
    print(repr(k), ':', repr(v))
    # try to find FLG in header values
    if 'FLG' in v or 'flg' in v.lower():
        print("  ^^^ CONTAINS FLAG!")

print()
# also try URL-decoding any suspicious header values
for k, v in r.headers.items():
    if '%' in v or len(v) > 100:
        try:
            decoded = urllib.parse.unquote(v)
            print(f'URL-decoded {k}:', decoded[:500])
        except:
            pass

# Also try GET
print()
print('=== GET request ===')
r2 = requests.get(URL, timeout=30)
print('STATUS:', r2.status_code)
for k, v in r2.headers.items():
    print(repr(k), ':', repr(v[:300]))
print('BODY:', r2.text[:500])
