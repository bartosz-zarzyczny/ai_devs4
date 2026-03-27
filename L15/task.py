"""
L15 — savethem solver
Discovers tools via toolsearch, fetches map and vehicle data,
computes optimal rocket+dismount route, and submits to /verify.
"""
import os
import requests
import json
import heapq
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("AI_DEVS_4_API_KEY")
BASE = "https://hub.ag3nts.org"


def toolsearch(query):
    r = requests.post(BASE + "/api/toolsearch", json={"apikey": KEY, "query": query}, timeout=15)
    return r.json()


def call_tool(url, query):
    r = requests.post(BASE + url, json={"apikey": KEY, "query": query}, timeout=15)
    return r.json()


def fetch_map():
    res = call_tool("/api/maps", "Skolwin")
    assert res.get("code") == 241, f"Map fetch failed: {res}"
    return res["map"]


def fetch_vehicles():
    vehicles = {}
    for name in ["rocket", "horse", "walk", "car"]:
        res = call_tool("/api/wehicles", name)
        assert res.get("code") == 230, f"Vehicle fetch failed for {name}: {res}"
        c = res["consumption"]
        # water_blocked: rocket and car cannot enter water tiles
        water_blocked = name in ("rocket", "car")
        vehicles[name] = {
            "fuel": c["fuel"],
            "food": c["food"],
            "water_blocked": water_blocked,
        }
    return vehicles


def find_route(grid, vehicles, start, goal, init_fuel=10.0, init_food=10.0):
    """
    Dijkstra over (row, col, fuel*100, food*100, vehicle) states.
    Supports mid-route dismount (switch to walk).
    Returns (route_list, final_fuel, final_food).
    """
    PREC = 100
    DIRS = [(-1, 0, "up"), (1, 0, "down"), (0, -1, "left"), (0, 1, "right")]
    rows, cols = len(grid), len(grid[0])

    init_fuel_i = round(init_fuel * PREC)
    init_food_i = round(init_food * PREC)

    # State: (steps, row, col, fuel_i, food_i, vehicle, path)
    # We enumerate over starting vehicles
    best = None

    for start_veh in vehicles:
        heap = [(0, start[0], start[1], init_fuel_i, init_food_i, start_veh, [start_veh])]
        visited = {}

        while heap:
            steps, r, c, fuel_i, food_i, veh, path = heapq.heappop(heap)

            state = (r, c, fuel_i, food_i, veh)
            if state in visited:
                continue
            visited[state] = True

            if (r, c) == goal:
                if best is None or steps < best[0]:
                    best = (steps, path, init_fuel - fuel_i / PREC, init_food - food_i / PREC)
                break

            v = vehicles[veh]
            f_i = round(v["fuel"] * PREC)
            fd_i = round(v["food"] * PREC)

            # Move in 4 directions
            for dr, dc, dir_name in DIRS:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < rows and 0 <= nc < cols):
                    continue
                cell = grid[nr][nc]
                if cell == "R":
                    continue  # rocks are impassable for all vehicles/modes
                if cell == "W" and v["water_blocked"]:
                    continue
                nf = fuel_i - f_i
                nfd = food_i - fd_i
                if nf < 0 or nfd < 0:
                    continue
                heapq.heappush(heap, (steps + 1, nr, nc, nf, nfd, veh, path + [dir_name]))

            # Allow dismount (switch to walk) — treated as zero-cost action
            if veh != "walk":
                walk_state = (r, c, fuel_i, food_i, "walk")
                if walk_state not in visited:
                    heapq.heappush(heap, (steps, r, c, fuel_i, food_i, "walk", path + ["dismount"]))

    return best


def submit(route):
    r = requests.post(
        BASE + "/verify",
        json={"apikey": KEY, "task": "savethem", "answer": route},
        timeout=15,
    )
    return r.json()


def main():
    print("=== L15 savethem solver ===\n")

    # --- Phase 1: discover tools ---
    print("Discovering tools via toolsearch...")
    res = toolsearch("map of terrain")
    print(f"  maps tool: {res.get('tools', [])}")
    res2 = toolsearch("available vehicles fuel consumption")
    print(f"  vehicles tool: {res2.get('tools', [])}\n")

    # --- Phase 2: fetch data ---
    print("Fetching map...")
    grid = fetch_map()
    for i, row in enumerate(grid):
        print(f"  Row {i}: {''.join(row)}")

    start = None
    goal = None
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            if cell == "S":
                start = (r, c)
            elif cell == "G":
                goal = (r, c)
    print(f"\n  Start: {start}, Goal: {goal}")

    print("\nFetching vehicles...")
    vehicles = fetch_vehicles()
    for name, v in vehicles.items():
        print(f"  {name}: fuel={v['fuel']}/step, food={v['food']}/step, water_blocked={v['water_blocked']}")

    # --- Phase 3: find route ---
    print("\nRunning Dijkstra...")
    result = find_route(grid, vehicles, start, goal)
    if result is None:
        print("ERROR: No valid route found within resource limits!")
        return

    steps, route, fuel_used, food_used = result
    print(f"\nOptimal route ({steps} moves):")
    print(f"  {route}")
    print(f"  Fuel used: {fuel_used:.1f}/10, Food used: {food_used:.1f}/10")

    # --- Phase 4: submit ---
    print("\nSubmitting to /verify...")
    response = submit(route)
    print(f"Response: {json.dumps(response, indent=2)}")

    with open("L15/verification_result.json", "w") as f:
        json.dump(response, f, indent=2)
    print("Saved to L15/verification_result.json")


if __name__ == "__main__":
    main()
