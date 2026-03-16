import json, time, random, requests

URL = "https://hub.ag3nts.org/verify"
API = "5f9f1207-390f-4032-b98a-72075b11e655"

def call(action_dict, max_retry=35, label=""):
    backoff = 2.0
    for i in range(1, max_retry+1):
        try:
            r = requests.post(URL, json={"apikey": API, "task": "railway", "answer": action_dict}, timeout=30)
            try:
                d = r.json()
            except:
                d = {"raw": r.text}
            txt = json.dumps(d)[:250]
            print(f"  [{label}] attempt={i} status={r.status_code} => {txt}")
            if "FLG" in str(d):
                print("!!! FLAG:", d)
                return d, r
            if r.status_code == 200 and d.get("code") != -925:
                return d, r
            ra = d.get("retry_after") if isinstance(d, dict) else None
            wait = min(int(ra)+1, 70) if ra else min(backoff, 10)
            time.sleep(wait + random.random())
            backoff = min(backoff * 1.5, 15)
        except Exception as e:
            print(f"  err: {e}")
            time.sleep(5)
    return None, None

ROUTE = "x-01"

print("\n=== VARIANT A: reconfigure -> getstatus (skip setstatus+save) ===")
d1, _ = call({"action": "reconfigure", "route": ROUTE}, label="reconf")
if d1:
    d2, _ = call({"action": "getstatus", "route": ROUTE}, label="getstatus-immediate")
    print("getstatus result:", d2)

time.sleep(5)

print("\n=== VARIANT B: reconfigure -> setstatus RTCLOSE -> save -> getstatus ===")
d1, _ = call({"action": "reconfigure", "route": ROUTE}, label="reconf")
if d1:
    d2, _ = call({"action": "setstatus", "route": ROUTE, "value": "RTCLOSE"}, label="setstatus-RTCLOSE")
    if d2:
        d3, _ = call({"action": "save", "route": ROUTE}, label="save")
        if d3:
            d4, _ = call({"action": "getstatus", "route": ROUTE}, label="getstatus-final")
            print("getstatus result:", d4)

time.sleep(5)

print("\n=== VARIANT C: getstatus before reconfigure ===")
d1, _ = call({"action": "getstatus", "route": ROUTE}, label="getstatus-first")
print("Result:", d1)

print("\nDone")
