#!/usr/bin/env python3
"""
L13: Reactor — autonomous robot navigator.

Navigates a robot across a 7x5 grid, avoiding vertically bouncing reactor
blocks, from column 1 to column 7 on the bottom row.

Usage:
    python L13/task.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_KEY = os.environ.get("AI_DEVS_4_API_KEY", "")
HUB_URL = "https://hub.ag3nts.org/verify"
TASK = "reactor"

L13_DIR = Path(__file__).resolve().parent

# Board constants (1-indexed in task description, 0-indexed in code)
ROWS = 5
COLS = 7
ROBOT_ROW = 4   # bottom row, 0-indexed
GOAL_COL = 6    # rightmost column, 0-indexed
CMD_DELAY = 0.5  # seconds between API calls


# ---------------------------------------------------------------------------
# Hub communication
# ---------------------------------------------------------------------------

def send_command(command: str) -> tuple[dict, int]:
    """POST a single command to hub and return (response_dict, http_status)."""
    time.sleep(CMD_DELAY)
    payload = {
        "apikey": API_KEY,
        "task": TASK,
        "answer": {"command": command},
    }
    try:
        resp = requests.post(HUB_URL, json=payload, timeout=15)
    except requests.RequestException as exc:
        print(f"  [{command:6s}] NETWORK ERROR: {exc}")
        return {"error": str(exc)}, 0
    try:
        data = resp.json()
    except Exception:
        data = {"raw_text": resp.text}
    short = json.dumps(data, ensure_ascii=False)
    print(f"  [{command:6s}] HTTP {resp.status_code} | {short[:300]}")
    return data, resp.status_code


# ---------------------------------------------------------------------------
# Board parsing
# ---------------------------------------------------------------------------

_VALID_CHARS = set("PGBpgb. ")


def _parse_grid_lines(lines: list[str]) -> list[list[str]] | None:
    """Try to extract a 5x7 board from a list of stripped text lines."""
    candidates = []
    for line in lines:
        clean = line.replace(" ", "").replace(",", "").replace("|", "")
        if len(clean) == COLS and all(c in "PGBpgb." for c in clean):
            candidates.append([c.upper() for c in clean])
    if len(candidates) == ROWS:
        return candidates
    # allow extra  lines (headers/footers) — find 5 consecutive board rows
    for start in range(len(candidates) - ROWS + 1):
        return candidates[start : start + ROWS]
    return None


def parse_board(data: dict) -> list[list[str]] | None:
    """Extract the 5x7 board grid from an API response dict."""
    # Structured keys
    for key in ("board", "map", "grid", "state"):
        raw = data.get(key)
        if isinstance(raw, list) and len(raw) == ROWS:
            if all(isinstance(r, str) for r in raw):
                return [[c.upper() for c in row] for row in raw]
            if all(isinstance(r, list) for r in raw):
                return [[str(c).upper() for c in row] for row in raw]
    # Text fallback: search message / entire serialised response
    for source in (str(data.get("message", "")), json.dumps(data, ensure_ascii=False)):
        lines = [l.strip() for l in source.splitlines() if l.strip()]
        result = _parse_grid_lines(lines)
        if result:
            return result
    return None


# ---------------------------------------------------------------------------
# Block info extraction
# ---------------------------------------------------------------------------

def extract_blocks(data: dict, board: list[list[str]] | None) -> list[dict]:
    """
    Return block dicts: {col, top_row, direction} — all values 0-indexed.

    Strategy:
    - Derive col/top_row from board (always 0-indexed, reliable).
    - Fetch direction from API block data; auto-detect if API uses 1-indexed values.
    """
    # Step 1: board-derived positions (ground truth)
    board_blocks: list[dict] = []
    if board:
        for col in range(COLS):
            b_rows = [r for r in range(ROWS) if board[r][col] == "B"]
            if b_rows:
                board_blocks.append({"col": col, "top_row": min(b_rows), "direction": "unknown"})

    # Step 2: collect direction data from API
    api_raw: list[dict] = []
    for key in ("blocks", "reactorBlocks", "reactor_blocks", "obstacles"):
        raw = data.get(key)
        if not (isinstance(raw, list) and raw):
            continue
        for b in raw:
            if not isinstance(b, dict):
                continue
            col_v = b.get("col", b.get("column", b.get("x", b.get("c"))))
            dir_v = (b.get("direction") or b.get("dir") or b.get("moving") or "unknown").lower()
            if col_v is not None:
                api_raw.append({"col_raw": int(col_v), "direction": dir_v})
        if api_raw:
            break

    if not api_raw:
        return board_blocks

    # Step 3: decide offset — if API col values don't overlap with board cols at all,
    # they are probably 1-indexed; subtract 1 to align.
    board_cols = {bb["col"] for bb in board_blocks}
    api_cols_0 = {b["col_raw"] for b in api_raw}          # assuming 0-indexed
    api_cols_1 = {b["col_raw"] - 1 for b in api_raw}      # assuming 1-indexed
    overlap_0 = len(board_cols & api_cols_0)
    overlap_1 = len(board_cols & api_cols_1)
    offset = 1 if overlap_1 > overlap_0 else 0

    api_dir_by_col = {b["col_raw"] - offset: b["direction"] for b in api_raw}
    print(f"  [blocks] API offset={offset}  api_dir_by_col={api_dir_by_col}")

    # Step 4: assign directions to board-derived blocks
    for bb in board_blocks:
        if bb["col"] in api_dir_by_col:
            bb["direction"] = api_dir_by_col[bb["col"]]

    return board_blocks


# ---------------------------------------------------------------------------
# Safety predicates
# ---------------------------------------------------------------------------

def _block_currently_at_bottom(blk: dict) -> bool:
    """True when block occupies the robot row right now."""
    return blk["top_row"] + 1 >= ROBOT_ROW  # top_row >= 3


def _block_will_hit_bottom(blk: dict) -> bool:
    """True when block will occupy the robot row after ONE command is sent."""
    top = blk["top_row"]
    direction = blk.get("direction", "unknown").lower()

    if direction == "down":
        # Moves toward higher row index; reverses at ROBOT_ROW-1 (top_row=3)
        next_top = top + 1 if top < ROBOT_ROW - 1 else top - 1
    elif direction == "up":
        # Moves toward lower row index; reverses at row 0
        next_top = top - 1 if top > 0 else top + 1
    else:
        # Direction unknown — be conservative: dangerous if close to bottom
        return top >= ROBOT_ROW - 2  # top_row >= 2

    return next_top + 1 >= ROBOT_ROW  # next bottom cell at or below robot row


def col_safe_now(board: list[list[str]], col: int) -> bool:
    """True if column col has no block at the robot row right now."""
    if col < 0 or col >= COLS:
        return False
    return board[ROBOT_ROW][col] != "B"


def col_safe_next(blocks_by_col: dict, col: int) -> bool:
    """True if column col will not have a block at the robot row after one step."""
    if col < 0 or col >= COLS:
        return False
    for blk in blocks_by_col.get(col, []):
        if _block_will_hit_bottom(blk):
            return False
    return True


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------

def decide(board: list[list[str]], blocks: list[dict], robot_col: int) -> str:
    """
    Return the safest command.
    Priority: right (advance) > wait > left (retreat).
    """
    by_col: dict[int, list[dict]] = {}
    for blk in blocks:
        by_col.setdefault(blk["col"], []).append(blk)

    right_col = robot_col + 1
    left_col = robot_col - 1

    # Option 1: advance right
    if col_safe_now(board, right_col) and col_safe_next(by_col, right_col):
        return "right"

    # Option 2: wait in place
    if col_safe_now(board, robot_col) and col_safe_next(by_col, robot_col):
        return "wait"

    # Option 3: retreat left
    if col_safe_now(board, left_col) and col_safe_next(by_col, left_col):
        return "left"

    # Fallback
    return "wait"


# ---------------------------------------------------------------------------
# Robot position detection
# ---------------------------------------------------------------------------

def find_robot_col(board: list[list[str]]) -> int | None:
    """Return robot's column (0-indexed) on the bottom row. 'P' = robot."""
    for c, cell in enumerate(board[ROBOT_ROW]):
        if cell == "P":
            return c
    # Fallback: any non-standard character on bottom row
    for c, cell in enumerate(board[ROBOT_ROW]):
        if cell not in (".", "B", "G"):
            return c
    return None


# ---------------------------------------------------------------------------
# Completion detection
# ---------------------------------------------------------------------------

_FLAG_RE = re.compile(r"\{FLG:[^}]+\}", re.IGNORECASE)


def is_finished(data: dict) -> bool:
    serialized = json.dumps(data, ensure_ascii=False)
    if _FLAG_RE.search(serialized):
        return True
    msg = str(data.get("message", "")).lower()
    code = data.get("code", -1)
    if code == 0 and any(w in msg for w in ("congratulat", "success", "win", "done", "flagg")):
        return True
    return False


def is_dead(data: dict, http_status: int) -> bool:
    """True when the robot has been crushed / game-over state."""
    if http_status == 409:
        return True
    msg = str(data.get("message", "")).lower()
    code = data.get("code", -1)
    dead_words = ("crush", "dead", "fail", "collision", "game over", "restart", "reset", "zgnieciony")
    if code not in (0, 100) and any(w in msg for w in dead_words):
        return True
    return False


# ---------------------------------------------------------------------------
# Main solve loop
# ---------------------------------------------------------------------------

def solve() -> None:
    if not API_KEY:
        print("ERROR: AI_DEVS_4_API_KEY not set in .env")
        sys.exit(1)

    print("=== L13 Reactor Solver ===")

    MAX_ATTEMPTS = 10
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n>>> Attempt {attempt}/{MAX_ATTEMPTS}")
        data, status = send_command("start")

        for step in range(1, 300):
            print(f"\n--- Step {step} ---")

            if is_finished(data):
                _save_and_exit(data)
                return

            if is_dead(data, status):
                print("  ROBOT DEAD -- resetting...")
                send_command("reset")
                break  # restart attempt loop

            board = parse_board(data)
            blocks = extract_blocks(data, board)

            if board:
                for row in board:
                    print("  " + "".join(row))
            else:
                print(f"  (board not parsed) raw: {str(data)[:300]}")

            if board is None:
                data, status = send_command("wait")
                continue

            robot_col = find_robot_col(board)
            if robot_col is None:
                print("  WARNING: robot not found on board; sending wait")
                data, status = send_command("wait")
                continue

            if robot_col >= GOAL_COL:
                print("  Robot reached goal column — finishing!")
                _save_and_exit(data)
                return

            command = decide(board, blocks, robot_col)
            print(f"  robot_col={robot_col + 1}/7  blocks={[(b['col'] + 1, b['top_row'], b['direction']) for b in blocks]}  -> {command}")
            data, status = send_command(command)

    print("ERROR: max attempts exceeded without reaching goal")
    sys.exit(1)


def _save_and_exit(data: dict) -> None:
    print("\n=== TASK COMPLETE ===")
    flag_match = _FLAG_RE.search(json.dumps(data, ensure_ascii=False))
    if flag_match:
        print(f"Flag: {flag_match.group(0)}")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    out = L13_DIR / "verification_result.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Result saved to {out}")


if __name__ == "__main__":
    solve()
