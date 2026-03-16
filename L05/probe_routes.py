import json, time, random, requests

URL = "https://hub.ag3nts.org/verify"
API = "5f9f1207-390f-4032-b98a-72075b11e655"

def call(action_dict, max_retry=40, label=""):
    backoff = 2.0
    for i in range(1, max_retry+1):
        try:
            r = requests.post(URL, json={"apikey": API, "task": "railway", "answer": action_dict}, timeout=30)
            try:
                d = r.json()
            except:
                d = {"raw": r.text}
            print(f"  [{label}] attempt={i} status={r.status_code} body={json.dumps(d)[:200]}")
            if "FLG" in str(d):
                print("!!! FLAG FOUND:", d)
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

# Try special routes hinting at CZARNOBYL
# c-4 = Chernobyl reactor 4
candidates = ["c-4", "c-4", "x-4", "y-4", "z-4"]

for route in candidates:
    print(f"\n=== Testing route: {route} ===")
    # reconfigure
    d1, _ = call({"action": "reconfigure", "route": route}, label=f"reconfigure {route}")
    if d1 is None:
        continue
    # setstatus RTOPEN
    d2, _ = call({"action": "setstatus", "route": route, "value": "RTOPEN"}, label=f"setstatus {route}")
    if d2 is None:
        continue
    # save
    d3, _ = call({"action": "save", "route": route}, label=f"save {route}")
    if d3 is None:
        continue
    # getstatus
    d4, _ = call({"action": "getstatus", "route": route}, label=f"getstatus {route}")
    print(f"Final getstatus: {d4}")
    if d4 and "FLG" in str(d4):
        print("!!! BONUS FLAG:", d4)
        break
    time.sleep(3)

print("\nDone")
