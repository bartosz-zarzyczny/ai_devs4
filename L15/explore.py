import os, requests, json
from dotenv import load_dotenv
load_dotenv()
KEY = os.getenv('AI_DEVS_4_API_KEY')
BASE = 'https://hub.ag3nts.org'

def toolsearch(query):
    r = requests.post(BASE+'/api/toolsearch', json={'apikey': KEY, 'query': query}, timeout=15)
    return r.json()

def tool(url, query):
    r = requests.post(BASE+url, json={'apikey': KEY, 'query': query}, timeout=15)
    return r.json()

# Find more tools
queries = [
    'movement rules terrain passable obstacles',
    'terrain type cost multiplier rocks trees',
    'game mechanics movement constraints',
    'mission briefing rules',
    'can vehicles pass obstacles',
    'terrain walkable impassable tiles',
    'rules movement direction',
]
found = {}
for q in queries:
    r = toolsearch(q)
    for t in r.get('tools', []):
        found[t['url']] = t
    names = [t['name'] for t in r.get('tools', [])]
    print(f"Query: {q[:50]} -> {names}")

print("\nAll unique tools found:")
print(json.dumps(list(found.values()), indent=2))

# Also try querying vehicles with specific terrain questions
print("\n\n=== Vehicle terrain interaction queries ===")
for v in ['rocket', 'horse', 'walk', 'car']:
    res = tool('/api/wehicles', v)
    print(f"\n{v}: note={res.get('note','')[:200]}")
    print(f"  consumption: {res.get('consumption')}")
