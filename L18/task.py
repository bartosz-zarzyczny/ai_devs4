#!/usr/bin/env python3
"""L18 - domatowo solver

Algorithm summary from README:
1. help/getMap to discover map and costs
2. find B3 locations (highest blocks)
3. create transporter + scouts
4. move transporter to road nearest B3 cluster
5. dismount scouts and move one scout to B3 tile
6. inspect B3 tile and check logs
7. callHelicopter once human found
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

WHERE_LETTERS = "ABCDEFGHIJK"  # columns A..K
VERIFY_URL = "https://hub.ag3nts.org/verify"
TASK_NAME = "domatowo"

L18_DIR = Path(__file__).resolve().parent
RESULT_FILE = L18_DIR / "verification_result.json"
LOG_FILE = L18_DIR / "operation_log.jsonl"

def get_api_key() -> str:
    api_key = os.environ.get("AI_DEVS_4_API_KEY", "").strip().strip('"').strip("'")
    if not api_key:
        raise RuntimeError("AI_DEVS_4_API_KEY not set in environment")
    return api_key


def post_answer(answer: Dict[str, Any], *, timeout: int = 45) -> Dict[str, Any]:
    payload = {"apikey": get_api_key(), "task": TASK_NAME, "answer": answer}
    resp = requests.post(VERIFY_URL, json=payload, timeout=timeout)
    try:
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"Non-JSON response from verify: {exc}\n{resp.text[:1000]}")
    # Log actions
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"request": payload, "response": data}, ensure_ascii=False) + "\n")
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} {data}")
    return data


def coord_to_index(coord: str) -> Tuple[int, int]:
    c = coord[0].upper()
    r = int(coord[1:])
    x = WHERE_LETTERS.index(c)
    y = r - 1
    return x, y


def index_to_coord(x: int, y: int) -> str:
    return f"{WHERE_LETTERS[x]}{y+1}"


def get_row_col_pos(x: int, y: int) -> Tuple[int, int]:
    # same as tuple
    return x, y


def get_map_data() -> Dict[str, Any]:
    return post_answer({"action": "getMap"})


def get_objects() -> List[Dict[str, Any]]:
    resp = post_answer({"action": "getObjects"})
    return resp.get("objects", []) if isinstance(resp.get("objects"), list) else []


def get_logs() -> List[Dict[str, Any]]:
    resp = post_answer({"action": "getLogs"})
    return resp.get("logs", []) if isinstance(resp.get("logs"), list) else []


def reset_map() -> Dict[str, Any]:
    return post_answer({"action": "reset"})


def inspect_scout(scout_id: str) -> Dict[str, Any]:
    return post_answer({"action": "inspect", "object": scout_id})


def move_unit(obj_id: str, where: str) -> Dict[str, Any]:
    return post_answer({"action": "move", "object": obj_id, "where": where})


def dismount(transporter_id: str, passengers: int) -> Dict[str, Any]:
    return post_answer({"action": "dismount", "object": transporter_id, "passengers": passengers})


def call_helicopter(dest: str) -> Dict[str, Any]:
    return post_answer({"action": "callHelicopter", "destination": dest})


def create_transporter(passengers: int = 2) -> Dict[str, Any]:
    return post_answer({"action": "create", "type": "transporter", "passengers": passengers})


def create_scout() -> Dict[str, Any]:
    return post_answer({"action": "create", "type": "scout"})


def analyze_high_buildings(map_data: Dict[str, Any]) -> Dict[str, List[str]]:
    """Find all high-priority buildings by category."""
    grid = map_data.get("map", {}).get("grid", [])
    assert isinstance(grid, list), "Unexpected map grid"
    
    # Priority categories (highest first)
    categories = {
        "block3": [],    # 3-story blocks (highest priority)
        "school": [],    # Multi-story school buildings  
        "church": [],    # Multi-story church buildings
        "block2": [],    # 2-story blocks (medium priority)
    }
    
    for y, row in enumerate(grid):
        for x, tile in enumerate(row):
            if tile in categories:
                categories[tile].append(index_to_coord(x, y))
    
    return categories


def find_positions_by_symbol(map_data: Dict[str, Any], symbol: str) -> List[str]:
    grid = map_data.get("map", {}).get("grid", [])
    positions = []
    for y, row in enumerate(grid):
        for x, tile in enumerate(row):
            if tile == symbol:
                positions.append(index_to_coord(x, y))
    return positions


def neighbors(pos: Tuple[int, int]) -> List[Tuple[int, int]]:
    x, y = pos
    results = []
    for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
        nx, ny = x + dx, y + dy
        if 0 <= nx < 11 and 0 <= ny < 11:
            results.append((nx, ny))
    return results


def bfs(start: Tuple[int, int], goals: set[Tuple[int, int]], is_passable) -> Optional[List[str]]:
    queue = deque([(start, [])])
    visited = {start}
    while queue:
        pos, path = queue.popleft()
        if pos in goals:
            return [index_to_coord(x, y) for x, y in path]
        for n in neighbors(pos):
            if n in visited:
                continue
            if not is_passable(n):
                continue
            visited.add(n)
            queue.append((n, path + [n]))
    return None


def find_path(start: str, target: str, passable_func) -> Optional[List[str]]:
    start_idx = coord_to_index(start)
    target_idx = coord_to_index(target)
    path_coords = bfs(start_idx, {target_idx}, passable_func)
    if path_coords is None:
        return None
    return path_coords


def mower(grid: List[List[str]], iso: str) -> List[str]:
    # not used
    return []


def run_plan() -> None:
    print("====== L18 - domatowo / solver run ======")

    # Step 1: help
    help_result = post_answer({"action": "help"})
    print("help response code:", help_result.get("code"), "message:", help_result.get("message"))

    # Step 2: getMap
    map_response = get_map_data()
    print("map response:", map_response.get("message"))

    # Reset board to clean initial state before executing the plan
    print("Resetting board state")
    reset_resp = reset_map()
    print("reset response", reset_resp)

    # Re-fetch map after reset (position may change)
    map_response = get_map_data()
    print("map response after reset:", map_response.get("message"))

    # Analyze all high buildings according to plan
    building_categories = analyze_high_buildings(map_response)
    print("High building analysis:")
    for category, positions in building_categories.items():
        print(f"  {category}: {len(positions)} positions - {positions}")
    
    # Create prioritized target list (block3 first, then school/church, then block2)
    priority_targets = []
    for category in ["block3", "school", "church", "block2"]:
        priority_targets.extend(building_categories.get(category, []))
    
    if not priority_targets:
        raise RuntimeError("No high buildings found on map, cannot continue")

    transporter_scouts_onboard = 2

    # Step 3: optionally re-use existing transporter if present
    objs = get_objects()
    transporter_objs = [o for o in objs if o.get("typ") == "transporter"]
    scout_objs = [o for o in objs if o.get("typ") == "scout"]

    if transporter_objs:
        transporter = transporter_objs[-1]
        transporter_id = transporter["id"]
        transporter_pos = transporter.get("position")
        print("Re-using existing transporter", transporter_id, "at", transporter_pos)
    else:
        print("Creating transporter with 2 passengers...")
        t_response = create_transporter(passengers=2)
        print("transporter response", t_response)

        transporter_id = t_response.get("object") or t_response.get("id")
        transporter_pos = t_response.get("spawn") or t_response.get("position")

        if not transporter_id:
            # fallback to getObjects in case API returns different format
            objs = get_objects()
            transporter_objs = [o for o in objs if o.get("typ") == "transporter"]
            if not transporter_objs:
                raise RuntimeError("Failed to create transporter")
            transporter = transporter_objs[-1]
            transporter_id = transporter["id"]
            transporter_pos = transporter.get("position")

    if not transporter_id:
        # fallback to getObjects in case API returns different format
        objs = get_objects()
        transporter_objs = [o for o in objs if o.get("typ") == "transporter"]
        if not transporter_objs:
            raise RuntimeError("Failed to create transporter")
        transporter = transporter_objs[-1]
        transporter_id = transporter["id"]
        transporter_pos = transporter.get("position")

    print("Transporter id", transporter_id, "position", transporter_pos)

    # Refresh the object list and harvest scout ids from transporter crew.
    time.sleep(0.5)
    objs = get_objects()
    scout_objs = [o for o in objs if o.get("typ") == "scout"]
    print("Known scouts", [s.get("id") for s in scout_objs])

    # If transport has crew listed in response, include them
    if not scout_objs and t_response.get("crew"):
        scout_objs = [
            {"id": c.get("id"), "position": transporter_pos, "typ": "scout"}
            for c in t_response.get("crew", [])
            if c.get("role") == "scout"
        ]
        print("Using crew scouts from transporter response:", [s["id"] for s in scout_objs])

    # We use the first scout from transporter if available or independent.
    scout_id = scout_objs[0]["id"] if scout_objs else None

    # Simple strategy: iterate over B3 positions in order.
    # For each B3 target, move transporter to an adjacent road tile (or current pos if already on road),
    # dismount scouts, move one scout to target and inspect.

    # Compute road set
    roads = set(find_positions_by_symbol(map_response, "road"))

    def road_passable(coord):
        try:
            x, y = coord_to_index(coord)
        except Exception:
            return False
        tile = map_response["map"]["grid"][y][x]
        return tile == "road"

    def all_passable(coord):
        # scout can cross anything
        return True

    # Calculate priority scores according to README heuristic: score = priority / cost
    def calculate_priority_score(target_pos: str) -> float:
        # Priority weights (higher = more important to search)
        if any(target_pos in building_categories.get(cat, []) for cat in ["block3"]):
            base_priority = 100
        elif any(target_pos in building_categories.get(cat, []) for cat in ["school", "church"]):
            base_priority = 80  
        elif any(target_pos in building_categories.get(cat, []) for cat in ["block2"]):
            base_priority = 50
        else:
            base_priority = 10
            
        # Add some distance-based cost approximation
        tx, ty = coord_to_index(target_pos)
        # Rough cost estimate from current transporter position
        approx_cost = abs(tx - 3) + abs(ty - 6) + 10  # rough estimate
        
        return base_priority / max(approx_cost, 1)
    
    # Sort targets by priority score
    priority_targets.sort(key=calculate_priority_score, reverse=True)
    print(f"Prioritized targets: {priority_targets[:10]}...")  # show first 10
    
    # For each target in priority order
    for target in priority_targets:
        print('\n--- Trying priority target', target)
        tx, ty = coord_to_index(target)
        adj_roads = []
        for nx, ny in neighbors((tx, ty)):
            if map_response["map"]["grid"][ny][nx] == "road":
                adj_roads.append(index_to_coord(nx, ny))
        if not adj_roads:
            print("No adjacent road for target", target, "skipping")
            continue

        # Determine current transporter pos
        transporter_pos = get_objects()
        transporter_state = [o for o in transporter_pos if o.get("id") == transporter_id]
        if transporter_state:
            transporter_pos = transporter_state[0].get("position")
        else:
            transporter_pos = transporter.get("position")

        # choose nearest adjacent road
        best_path = None
        best_target = None
        for adj in adj_roads:
            path = find_path(transporter_pos, adj, lambda idx: map_response["map"]["grid"][idx[1]][idx[0]] == "road")
            if path is None:
                continue
            if best_path is None or len(path) < len(best_path):
                best_path = path
                best_target = adj

        if best_path is None:
            print("No road path found to any adjacent road around", target)
            continue

        # Move transporter along path
        for step in best_path:
            print("Move transporter", transporter_id, "->", step)
            resp = move_unit(transporter_id, step)
            print("  move response code", resp.get("code"), resp.get("message"))
            time.sleep(0.2)

        if 'transporter_scouts_onboard' not in locals():
            transporter_scouts_onboard = 2

        if transporter_scouts_onboard > 1:
            print("Dismount 1 scout from transporter")
            dismount(transporter_id, passengers=1)
            transporter_scouts_onboard -= 1
            time.sleep(0.2)
        else:
            print("Skipping dismount to keep transporter drivable (1 scout remains)")

        # refresh scout info
        objs = get_objects()
        scout_objs = [o for o in objs if o.get("typ") == "scout"]
        if not scout_objs:
            print("No scouts found after dismount, abort")
            continue

        # pick a scout near transporter first
        scout_obj = None
        for s in scout_objs:
            if s.get("position") in roads or s.get("position") == best_target:
                scout_obj = s
                break
        if scout_obj is None:
            scout_obj = scout_objs[0]

        scout_id = scout_obj["id"]
        scout_pos = scout_obj.get("position")
        print("Selected scout", scout_id, "at", scout_pos, "to inspect", target)

        # Move scout to target tile
        if scout_pos is None:
            print("Scout position unknown, skipping target", target)
            continue
        path = find_path(scout_pos, target, lambda idx: True)
        if path is None:
            print("Could not find scout path to", target, "skipping")
            continue

        for step in path:
            print("Move scout", scout_id, "->", step)
            resp = move_unit(scout_id, step)
            print("  scout move resp", resp.get("code"), resp.get("message"))
            time.sleep(0.2)

        print("Inspecting with scout", scout_id)
        inspect_resp = inspect_scout(scout_id)
        print(" inspect resp", inspect_resp)

        logs = get_logs()
        print(" getLogs", logs)

        def log_suggests_human(msg: str) -> bool:
            text = (msg or "").lower()
            # Explicit negative patterns (expanded)
            negative_patterns = [
                "brak", "puste", "pusty", "nieobecny", "nieobecna", 
                "nie ma", "bez", "nie odnaleziono", "nie został odnaleziony",
                "cel nie", "brak obecności", "pomieszczenie bez", "nikt",
                "pusto", "nie znaleziono", "bez kontaktu"
            ]
            if any(neg in text for neg in negative_patterns):
                return False
                
            # Trace/clue patterns (not actual human presence) 
            trace_patterns = ["ślad", "slad", "prowadz", "wskazuj", "sugeruj"]
            if any(trace in text for trace in trace_patterns):
                return False
                
            # Positive confirmation patterns (actual human found)
            positive_patterns = [
                "partyzant", "czlowiek", "human", "znalezion", "odnalezion", 
                "potwierdzam", "jest tutaj", "widać", "ranny", "żywy", 
                "człowiek obecny", "cel obecny", "osoba", "mamy poszukiwanego",
                "poszukiwany", "mężczyzna", "kobieta", "rannego", "ukrywa się",
                "ukrył się", "cel znaleziony", "odnaleźć", "osoba obecna"
            ]
            return any(pos in text for pos in positive_patterns)

        # Check if any log confirms human presence (not just traces)
        human_found = any(log_suggests_human(entry.get("msg", "")) for entry in logs)
        
        # Check if logs suggest traces leading to nearby areas
        traces_found = any("ślad" in entry.get("msg", "").lower() or "prowadz" in entry.get("msg", "").lower() 
                          for entry in logs)

        if human_found:
            print("Human found at", target, "calling helicopter")
            result = call_helicopter(target)
            print("callHelicopter result", result)
            RESULT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            return
        elif traces_found:
            print(f"Traces detected at {target}, noting for future reference")

        print("No human at", target, "continuing")

    print("No human found in prioritized high building candidates")


if __name__ == "__main__":
    try:
        run_plan()
    except Exception as e:
        print("ERROR:", e)
        sys.exit(1)
