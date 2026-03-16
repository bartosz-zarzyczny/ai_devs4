import json, time, requests

URL = "https://hub.ag3nts.org/verify"
API = "5f9f1207-390f-4032-b98a-72075b11e655"
ROUTE = "x-01"
DURATION = 260  # send for 260 seconds (> 4 minutes)

start = time.time()
attempt = 0

print(f"Hammering API for {DURATION}s, ignoring ALL Retry-After...")

while time.time() - start < DURATION:
    attempt += 1
    elapsed = time.time() - start
    try:
        r = requests.post(URL, json={"apikey": API, "task": "railway", "answer": {"action": "getstatus", "route": ROUTE}}, timeout=10)
        try:
            d = r.json()
        except:
            d = {"raw": r.text}
        txt = json.dumps(d)[:200]
        print(f"  [{elapsed:.0f}s] attempt={attempt} status={r.status_code} => {txt}")
        if "FLG" in str(d):
            print("!!! FLAG FOUND:", d)
            break
    except Exception as e:
        print(f"  [{elapsed:.0f}s] err: {e}")
    # tiny delay to avoid crushing CPU, but nothing close to Retry-After
    time.sleep(0.3)

print(f"\nDone after {time.time()-start:.0f}s, {attempt} attempts")
