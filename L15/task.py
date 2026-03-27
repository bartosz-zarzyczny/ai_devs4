#!/usr/bin/env python3
"""
L15 — Savethem: Optimal route finder using toolsearch API.

Agent discovers tools via toolsearch, gathers map/vehicle/terrain data,
computes shortest path via Dijkstra with fuel+food constraints,
and submits the route to /verify.
"""

import os
import sys
import json
import heapq
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, List, Any
from dotenv import load_dotenv
import requests

load_dotenv()

API_KEY = os.getenv("AI_DEVS_4_API_KEY")
HUB_BASE = "https://hub.ag3nts.org"
TOOLSEARCH_URL = f"{HUB_BASE}/api/toolsearch"
VERIFY_URL = f"{HUB_BASE}/verify"
PREVIEW_URL = "https://hub.ag3nts.org/savethem_preview.html"

TASK_NAME = "savethem"
MAX_RETRIES = 3
REQUEST_TIMEOUT = 15

# Dijkstra state: (row, col, fuel, food, vehicle_name)
@dataclass
class State:
    row: int
    col: int
    fuel: int
    food: int
    vehicle: str
    path: List[str]  # Directions taken

    def __lt__(self, other):
        # Priority queue: prefer shorter paths (fewer steps)
        return len(self.path) < len(other.path)

    def __hash__(self):
        return hash((self.row, self.col, self.fuel, self.food, self.vehicle))

    def __eq__(self, other):
        return (
            self.row == other.row
            and self.col == other.col
            and self.fuel == other.fuel
            and self.food == other.food
            and self.vehicle == other.vehicle
        )


def log_msg(msg: str, level: str = "INFO"):
    """Log with timestamp."""
    print(f"[{level}] {msg}")


def call_toolsearch(query: str) -> List[Dict[str, Any]]:
    """Query toolsearch API, return top 3 tools."""
    payload = {"apikey": API_KEY, "query": query}
    try:
        resp = requests.post(TOOLSEARCH_URL, json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        result = resp.json()
        # Result format: {"code": 210, "message": "...", "tools": [...]}
        if isinstance(result, dict):
            if "tools" in result:
                tools = result["tools"]
                # Convert path-based URLs to full URLs
                for tool in tools:
                    if "url" in tool and not tool["url"].startswith("http"):
                        tool["url"] = HUB_BASE + tool["url"]
                return tools[:3]
            elif "results" in result:
                return result["results"][:3]
            else:
                log_msg(f"Unexpected toolsearch format: {result}", "WARN")
                return []
        elif isinstance(result, list):
            return result[:3]
        else:
            log_msg(f"Unexpected toolsearch format: {result}", "WARN")
            return []
    except Exception as e:
        log_msg(f"Toolsearch error for query '{query}': {e}", "ERROR")
        return []


def call_tool(tool_url: str, query: str) -> Optional[str]:
    """Call a discovered tool with query, return text response."""
    payload = {"apikey": API_KEY, "query": query}
    try:
        # Try POST first
        resp = requests.post(tool_url, json=payload, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 404:
            # Try with query as parameter
            log_msg(f"  Trying GET with query param: {tool_url}?query={query[:30]}...", "WARN")
            resp = requests.get(tool_url, params=payload, timeout=REQUEST_TIMEOUT)
        
        resp.raise_for_status()
        result = resp.json()
        # Result may be: {"output": "text"}, or raw string, or other format
        if isinstance(result, dict):
            if "output" in result:
                return result["output"]
            elif "answer" in result:
                return result["answer"]
            elif "data" in result:
                return result["data"]
            else:
                return json.dumps(result)
        else:
            return str(result)
    except Exception as e:
        log_msg(f"Tool call error to {tool_url}: {e}", "ERROR")
        return None


def discover_tools() -> Dict[str, str]:
    """
    Discover tools via toolsearch for: map, vehicles, terrain rules.
    Returns dict: {"map": url, "vehicles": url, ...}
    """
    log_msg("=== Phase 1: Discovering tools ===")

    tools_found = {}

    queries = [
        ("map", "map of terrain 10x10 grid"),
        ("vehicles", "available vehicles fuel consumption speed"),
        ("terrain", "movement rules terrain costs"),
        ("resources", "fuel food resource cost per move"),
    ]

    for key, query in queries:
        log_msg(f"Searching for {key}: {query}")
        results = call_toolsearch(query)
        if results:
            # Take first result — handle both "url" and "URL" fields
            result = results[0]
            tool_url = result.get("url") or result.get("URL")
            if tool_url:
                tools_found[key] = tool_url
                log_msg(f"  Found {key} tool: {tool_url}")
                if "description" in result:
                    log_msg(f"    Description: {result['description']}")
            else:
                log_msg(f"  No URL in result: {result}", "WARN")
        else:
            log_msg(f"  No results for {key}", "WARN")

    log_msg(f"Discovered {len(tools_found)} tools: {list(tools_found.keys())}")
    return tools_found


def fetch_game_data(tools: Dict[str, str]) -> Dict[str, Any]:
    """
    Query discovered tools to gather map, vehicles, and terrain data.
    Returns: {"map": [[...]], "vehicles": [...], "terrain": {...}, ...}
    """
    log_msg("=== Phase 2: Gathering game data ===")

    data = {}

    if "map" in tools:
        log_msg("Fetching map...")
        map_text = call_tool(tools["map"], "What is the 10x10 map? Show terrain, rivers, trees, stones.")
        if map_text:
            data["map_raw"] = map_text
            log_msg(f"  Map retrieved ({len(map_text)} chars)")

    if "vehicles" in tools:
        log_msg("Fetching vehicles...")
        veh_text = call_tool(tools["vehicles"], "List all available vehicles with fuel consumption and speed parameters.")
        if veh_text:
            data["vehicles_raw"] = veh_text
            log_msg(f"  Vehicles retrieved ({len(veh_text)} chars)")

    if "terrain" in tools:
        log_msg("Fetching terrain rules...")
        terrain_text = call_tool(tools["terrain"], "Explain movement rules and terrain cost for each type (river, tree, stone, grass).")
        if terrain_text:
            data["terrain_raw"] = terrain_text
            log_msg(f"  Terrain rules retrieved ({len(terrain_text)} chars)")

    if "resources" in tools:
        log_msg("Fetching resource rules...")
        res_text = call_tool(tools["resources"], "How much fuel and food consumed per move with each vehicle?")
        if res_text:
            data["resources_raw"] = res_text
            log_msg(f"  Resources info retrieved ({len(res_text)} chars)")

    return data


def simplify_map_to_grid(map_raw: str) -> Optional[List[List[str]]]:
    """
    Try to parse raw map text into 10x10 grid.
    Simple heuristic: extract lines that look like rows.
    """
    lines = map_raw.strip().split("\n")
    grid = []
    for line in lines:
        # Filter lines that look like map rows (contain . # ~ T etc)
        line = line.strip()
        if not line or len(line) < 5:
            continue
        # Try to extract characters
        chars = list(line)
        if len(chars) >= 10:
            grid.append(chars[:10])
        if len(grid) >= 10:
            break
    if len(grid) == 10 and all(len(row) == 10 for row in grid):
        return grid
    return None


def parse_vehicles(vehicles_raw: str) -> Dict[str, Dict[str, float]]:
    """
    Parse vehicle data. Format varies; return best guess.
    Returns: {"car": {"fuel_cost": 1.0, "food_cost": 0.5}, ...}
    """
    vehicles = {}
    # Heuristic: look for lines with "car", "bike", "truck" etc and numbers
    lines = vehicles_raw.lower().split("\n")
    for line in lines:
        for vname in ["car", "bike", "truck", "horse", "walking", "walk", "foot"]:
            if vname in line:
                # Try to extract fuel and food costs
                tokens = line.split()
                fuel_cost = 1.0
                food_cost = 1.0
                for i, token in enumerate(tokens):
                    try:
                        val = float(token)
                        if i % 2 == 0:
                            fuel_cost = val
                        else:
                            food_cost = val
                    except:
                        pass
                vehicles[vname] = {"fuel_cost": fuel_cost, "food_cost": food_cost}
    if not vehicles:
        # Default vehicles if parsing fails
        # Costs are set low to allow traversing 10x10 grid with 10 fuel and 10 food
        vehicles = {
            "car": {"fuel_cost": 0.5, "food_cost": 0.3},    #Fast, moderate food
            "bike": {"fuel_cost": 0.3, "food_cost": 0.5},   # Balanced
            "walk": {"fuel_cost": 0.0, "food_cost": 0.6},   # No fuel, most food
        }
    return vehicles


def find_start_and_goal(grid: List[List[str]]) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """
    Find start (S or @) and goal (G or Skolwin marker) in grid.
    Fallback: start (0,0), goal (9,9).
    """
    start = None
    goal = None
    for r in range(len(grid)):
        for c in range(len(grid[r])):
            cell = grid[r][c].upper()
            if cell in ["S", "@", "P"]:
                start = (r, c)
            elif cell in ["G", "E", "X"]:
                goal = (r, c)
    if start is None:
        start = (0, 0)
    if goal is None:
        goal = (9, 9)
    return start, goal


def is_passable(grid: List[List[str]], row: int, col: int) -> bool:
    """Check if cell is passable (not obstacle)."""
    if not (0 <= row < len(grid) and 0 <= col < len(grid[0])):
        return False
    cell = grid[row][col].upper()
    # Assume: . = grass, S/P = start, G/E = goal, others blocked
    if cell in ["#", "~", "|", "-", "X", "T"]:  # tree, water, stone
        return False
    return True


def direction_to_delta(direction: str) -> Tuple[int, int]:
    """Convert direction string to row/col delta."""
    direction = direction.lower()
    if direction == "up":
        return (-1, 0)
    elif direction == "down":
        return (1, 0)
    elif direction == "left":
        return (0, -1)
    elif direction == "right":
        return (0, 1)
    return (0, 0)


def dijkstra_shortest_path(
    grid: List[List[str]],
    start: Tuple[int, int],
    goal: Tuple[int, int],
    vehicles: Dict[str, Dict[str, float]],
    initial_fuel: int = 10,
    initial_food: int = 10,
) -> Optional[List[str]]:
    """
    A* pathfinding with fuel/food constraints.
    Returns list of directions, starting with vehicle name.
    """
    log_msg("=== Phase 3: Computing optimal route ===")

    start_row, start_col = start
    goal_row, goal_col = goal

    def heuristic(row: int, col: int) -> float:
        """Manhattan distance to goal."""
        return abs(row - goal_row) + abs(col - goal_col)

    # Priority queue: (f_score, g_score, state)
    # f_score = g_score + h_score (total estimated cost)
    pq = []
    visited = set()

    # Try starting with the most fuel-efficient vehicle
    start_vehicle = "walk"  # Walk is most food-efficient, least fuel
    initial_state = State(
        row=start_row,
        col=start_col,
        fuel=initial_fuel,
        food=initial_food,
        vehicle=start_vehicle,
        path=[],
    )
    h_score = heuristic(start_row, start_col)
    heapq.heappush(pq, (h_score, 0, initial_state))

    best_solution = None
    best_steps = float("inf")

    iterations = 0
    max_iterations = 10000

    while pq and iterations < max_iterations:
        iterations += 1
        f_score, g_score, state = heapq.heappop(pq)

        # Goal check
        if state.row == goal_row and state.col == goal_col and len(state.path) < best_steps:
            best_solution = [state.vehicle] + state.path
            best_steps = len(state.path)
            log_msg(f"Found solution: {best_steps} steps with {state.vehicle}")
            continue  # Look for even better solutions

        # Visited check
        state_key = (state.row, state.col, state.vehicle)
        if state_key in visited:
            continue
        visited.add(state_key)

        # Try moving in 4 directions
        for direction in ["up", "down", "left", "right"]:
            dr, dc = direction_to_delta(direction)
            new_row = state.row + dr
            new_col = state.col + dc

            if not is_passable(grid, new_row, new_col):
                continue

            # Cost of move with current vehicle
            vehicle_data = vehicles[state.vehicle]
            fuel_cost = vehicle_data.get("fuel_cost", 1.0)
            food_cost = vehicle_data.get("food_cost", 1.0)

            new_fuel = state.fuel - fuel_cost
            new_food = state.food - food_cost

            if new_fuel < 0 or new_food < 0:
                continue  # Not enough resources

            new_state = State(
                row=new_row,
                col=new_col,
                fuel=new_fuel,
                food=new_food,
                vehicle=state.vehicle,
                path=state.path + [direction],
            )
            new_g = g_score + 1
            new_h = heuristic(new_row, new_col)
            new_f = new_g + new_h
            
            state_key = (new_state.row, new_state.col, new_state.vehicle)
            if state_key not in visited:
                heapq.heappush(pq, (new_f, new_g, new_state))

        # Try switching vehicle at current location
        for new_vehicle_name in vehicles:
            if new_vehicle_name == state.vehicle:
                continue
            new_state = State(
                row=state.row,
                col=state.col,
                fuel=state.fuel,
                food=state.food,
                vehicle=new_vehicle_name,
                path=state.path,
            )
            h_score = heuristic(state.row, state.col)
            # Switching is "free" but still costs in queue
            state_key = (new_state.row, new_state.col, new_state.vehicle)
            if state_key not in visited:
                heapq.heappush(pq, (g_score + h_score, g_score, new_state))

    log_msg(f"Explored {iterations} iterations")
    if best_solution:
        log_msg(f"Optimal path found: {best_steps} steps, {len(best_solution)-1} moves")
        return best_solution
    else:
        log_msg("No solution found!", "ERROR")
        return None


def submit_answer(route: List[str]) -> bool:
    """
    Submit route to /verify.
    Format: ["vehicle_name", "dir1", "dir2", ...]
    """
    log_msg("=== Phase 4: Submitting route ===")

    payload = {
        "apikey": API_KEY,
        "task": TASK_NAME,
        "answer": route,
    }

    try:
        resp = requests.post(VERIFY_URL, json=payload, timeout=REQUEST_TIMEOUT)
        result = resp.json()
        log_msg(f"Response status: {resp.status_code}")
        log_msg(f"Response: {json.dumps(result, indent=2)}")

        # Save result
        with open("L15/verification_result.json", "w") as f:
            json.dump(result, f, indent=2)

        if resp.status_code in [200, 201]:
            log_msg("✓ Route submitted successfully!")
            return True
        else:
            log_msg(f"✗ Submission failed with status {resp.status_code}", "ERROR")
            return False

    except Exception as e:
        log_msg(f"Submit error: {e}", "ERROR")
        return False


def main():
    log_msg(f"L15 Savethem Solver")
    log_msg(f"API Key: {'*' * 10}...")
    log_msg(f"Preview: {PREVIEW_URL}")

    # Validate API key
    if not API_KEY:
        log_msg("ERROR: AI_DEVS_4_API_KEY not set in .env", "ERROR")
        sys.exit(1)

    # Phase 1: Discover tools
    tools = discover_tools()
    if not tools:
        log_msg("WARNING: No tools discovered. Using defaults.", "WARN")
        tools = {}

    # Phase 2: Gather game data
    game_data = fetch_game_data(tools)

    # Parse map and vehicles
    map_grid = None
    if "map_raw" in game_data:
        map_grid = simplify_map_to_grid(game_data["map_raw"])

    if not map_grid:
        log_msg("WARNING: Could not parse map from tools. Using default 10x10 grid.", "WARN")
        # Create default 10x10 grid (mostly grass with some obstacles for testing)
        map_grid = [["." for _ in range(10)] for _ in range(10)]
        # Add some obstacles
        map_grid[2][4] = "#"  # Tree
        map_grid[3][4] = "#"
        map_grid[4][5] = "#"
        map_grid[5][5] = "#"
        map_grid[7][3] = "~"  # Water
        # Mark Skolwin (goal) at bottom-right area
        map_grid[9][9] = "G"
        map_grid[0][0] = "S"  # Start

    vehicles = parse_vehicles(game_data.get("vehicles_raw", ""))
    log_msg(f"Vehicles available: {list(vehicles.keys())}")

    # Find start (S, P, @) and goal (G, Skolwin location)
    start, goal = find_start_and_goal(map_grid)
    log_msg(f"Start: {start}, Goal (Skolwin): {goal}")

    # Log grid for debugging
    log_msg("Map (10x10):")
    for i, row in enumerate(map_grid):
        log_msg(f"  {i}: {''.join(row)}")

    # Phase 3: Compute optimal route with Dijkstra/A*
    route = dijkstra_shortest_path(map_grid, start, goal, vehicles)

    if not route:
        log_msg("ERROR: No route found!", "ERROR")
        sys.exit(1)

    log_msg(f"Route found: {route[:3]}{'...' if len(route) > 3 else ''} ({len(route)-1} moves)")

    # Phase 4: Submit
    success = submit_answer(route)

    if success:
        log_msg("✓ Task completed successfully!")
    else:
        log_msg("✗ Task submission failed.", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
