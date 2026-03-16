import json
import urllib.request
import urllib.parse
import urllib.error
import sys

API_KEY = "5f9f1207-390f-4032-b98a-72075b11e655"
DATA_URL = f"https://hub.ag3nts.org/data/{API_KEY}/categorize.csv"
VERIFY_URL = "https://hub.ag3nts.org/verify"

def post_json(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'))
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=10) as f:
            return json.loads(f.read().decode('utf-8')), f.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode('utf-8')), e.code

# 1. Reset
print("Resetting...")
res, status = post_json(VERIFY_URL, {
    "apikey": API_KEY,
    "task": "categorize",
    "answer": {"prompt": "reset"}
})
print("Reset res:", res)

# 2. Download data
print("Downloading CSV...")
req = urllib.request.Request(DATA_URL)
with urllib.request.urlopen(req) as response:
    lines = response.read().decode('utf-8').splitlines()

# skip header unconditionally since we know format is code,description
lines = lines[1:]

data = []
for line in lines:
    if not line.strip(): continue
    parts = line.split(',', 1)
    if len(parts) == 2:
        pid = parts[0].strip('"').strip("'")
        pdesc = parts[1].strip('"').strip("'")
        data.append({"id": pid, "desc": pdesc})

print(f"Loaded {len(data)} items:")
for d in data:
    print(d)

order = ['J', 'D', 'I', 'B', 'A', 'C', 'G', 'E', 'H', 'F']
data = [data[ord(letter) - ord('A')] for letter in order]

# 3. Test a prompt
# Requirements:
# - output DNG or NEU
# - exceptional: parts related to reactor MUST be NEU
# Limit is 100 tokens including the desc. The prompt must be short.
# It's better to put variables at the end.
prompt_template = "Return exactly 1 word: 'NEU' or 'DNG'. 'NEU' for safe items, tools, and ALL 'reactor' items. 'DNG' for weapons/ammo/hazardous. No explanations. ID:{id} Desc:{desc}"
import os
if os.path.exists("prompt.txt"):
    with open("prompt.txt", "r", encoding="utf-8") as pf:
        content = pf.read().strip()
        if content:
            prompt_template = content

all_results = []
print("\nTesting prompt...")
for d in data:
    prompt = prompt_template.format(id=d["id"], desc=d["desc"])
    payload = {
        "apikey": API_KEY,
        "task": "categorize",
        "answer": {"prompt": prompt}
    }
    with open("debug.txt", "a", encoding="utf-8") as f:
        f.write(f"SENDING PROMPT: {prompt}\n")
    
    res, status = post_json(VERIFY_URL, payload)
    
    all_results.append({
        "id": d["id"],
        "status": status,
        "res": res
    })
    
    if "FLG" in str(res):
        print("WIN! FLAG:", res)
        with open("results.json", "w", encoding="utf-8") as rf:
            json.dump(all_results, rf, indent=2)
        continue
    
    if status not in [200, 202] or ("code" in res and res["code"] not in [0, 1, 2]):
        print("ERROR! Stopping")
        with open("results.json", "w", encoding="utf-8") as rf:
            json.dump(all_results, rf, indent=2)
        break

with open("results.json", "w", encoding="utf-8") as rf:
    json.dump(all_results, rf, indent=2)
