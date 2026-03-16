import json, time, random, requests

URL = "https://hub.ag3nts.org/verify"
API = "5f9f1207-390f-4032-b98a-72075b11e655"

def call(action_dict, max_retry=40):
    backoff = 2.0
    for i in range(1, max_retry+1):
        try:
            r = requests.post(URL, json={"apikey": API, "task": "railway", "answer": action_dict}, timeout=30)
            print(f"  attempt={i} status={r.status_code}", end=" ")
            try:
                d = r.json()
                print(json.dumps(d)[:300])
            except:
                print(r.text[:300])
                d = {}
            if r.status_code == 200 and d.get("code") != -925:
                return d, r
            # respect JSON retry_after
            ra = d.get("retry_after") if isinstance(d, dict) else None
            if ra:
                wait = min(int(ra)+1, 70)
            else:
                wait = min(backoff, 10)
            print(f"  -> waiting {wait}s")
            time.sleep(wait + random.random())
            backoff = min(backoff * 1.5, 15)
        except Exception as e:
            print(f"  err: {e}")
            time.sleep(5)
    return None, None

print("=== Calling help to see full response ===")
h, _ = call({"action": "help"})
if h:
    with open("help_full.json", "w", encoding="utf-8") as f:
        json.dump(h, f, indent=2, ensure_ascii=False)
    print("\n\nFull help saved to help_full.json")
