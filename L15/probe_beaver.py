import os, requests, json, re
from dotenv import load_dotenv
load_dotenv()
KEY = os.getenv("AI_DEVS_4_API_KEY")
BASE = "https://hub.ag3nts.org"

r = requests.get(BASE + "/savethem_preview.html", timeout=15)
text = r.text

# Find API endpoints
apis = re.findall(r"['\"/]api/[^'\" \t\n>]+", text)
print("API endpoints:", sorted(set(apis)))
print()

# Find fetch calls
fetches = re.findall(r"fetch\([^)]+\)", text)
for f in fetches[:10]:
    print("fetch:", f)
print()

# Find beaverSpot source - where does it come from in the data?
idx = text.find("beaverSpot")
while idx != -1:
    snippet = text[max(0,idx-50):idx+200]
    if "data." in snippet or "response" in snippet or "json" in snippet.lower():
        print(f"--- beaverSpot at {idx} ---")
        print(snippet)
        print()
    idx = text.find("beaverSpot", idx+1)

# Find data structure parsing
for kw in ["beaver_spot", "beaverspot", "data.beaver", "data.map", "data.start"]:
    idx = text.lower().find(kw.lower())
    if idx != -1:
        print(f"--- {kw} at {idx} ---")
        print(text[max(0,idx-100):idx+400])
        print()
