#!/usr/bin/env python3
"""
L13 bonus probe: round-trip solver (right to col 5, back to col 0).
Hint: → → → → → ← ← ← ← ← BB
Flag is hidden in the response data (debug / preview).
"""

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

ROWS = 5
COLS = 7
ROBOT_ROW = 4
FLAG_RE = re.compile(r"\{FLG:[^}]+\}", re.IGNORECASE)


def send(command: str) -> tuple[dict, int]:
    time.sleep(0.5)
    payload = {"apikey": API_KEY, "task": TASK, "answer": {"command": command}}
    try:
        resp = requests.post(HUB_URL, json=payload, timeout=15)
    except requests.RequestException as exc:
        return {"error": str(exc)}, 0
    try:
        data = resp.json()
    except Exception:
        data = {"raw_text": resp.text}
    return data, resp.status_code


def parse_board(data: dict) -> list[list[str]] | None:
    board_raw = data.get("board")
    if isinstance(board_raw, list) and len(board_raw) == ROWS:
        return [[c.upper() for c in row] for row in board_raw]
    return None


def find_robot_col(board) -> int | None:
    for c, cell in enumerate(board[ROBOT_ROW]):
        if cell == "P":
            return c
    return None


def extract_blocks(data: dict, board) -> list[dict]:
    blocks = []
    raw_blocks = data.get("blocks", [])
    for blk in raw_blocks:
        api_col = blk.get("col", 0)
        # auto-detect offset
        col = api_col - 1 if api_col >= 1 else api_col
        if board and 0 <= col < COLS:
            if board[0][col] == "B" or board[1][col] == "B":
                pass  # match
            elif 0 <= api_col < COLS and (board[0][api_col] == "B" or board[1][api_col] == "B"):
                col = api_col
        blocks.append({
            "col": col,
            "top_row": blk.get("top_row", 1) - 1,
            "direction": blk.get("direction", "down"),
        })
    return blocks


def _block_will_hit_bottom(blk: dict) -> bool:
    top = blk["top_row"]
    d = blk["direction"]
    if d == "down":
        return top + 1 >= ROBOT_ROW - 1
    return False


def col_safe_now(board, col: int) -> bool:
    if col < 0 or col >= COLS:
        return False
    return board[ROBOT_ROW][col] != "B"


def col_safe_next(blocks_by_col: dict, col: int) -> bool:
    if col < 0 or col >= COLS:
        return False
    for blk in blocks_by_col.get(col, []):
        if _block_will_hit_bottom(blk):
            return False
    return True


def decide(board, blocks, robot_col, heading="right"):
    by_col = {}
    for blk in blocks:
        by_col.setdefault(blk["col"], []).append(blk)

    if heading == "right":
        adv_col, ret_col = robot_col + 1, robot_col - 1
        adv_cmd, ret_cmd = "right", "left"
    else:
        adv_col, ret_col = robot_col - 1, robot_col + 1
        adv_cmd, ret_cmd = "left", "right"

    if col_safe_now(board, adv_col) and col_safe_next(by_col, adv_col):
        return adv_cmd
    if col_safe_now(board, robot_col) and col_safe_next(by_col, robot_col):
        return "wait"
    if col_safe_now(board, ret_col) and col_safe_next(by_col, ret_col):
        return ret_cmd
    return "wait"


def check_flag(data: dict) -> str | None:
    flat = json.dumps(data, ensure_ascii=False)
    m = FLAG_RE.search(flat)
    return m.group(0) if m else None


def format_blocks_arrows(data: dict) -> str:
    """Format blocks with direction arrows like the UI: col(↑/↓)."""
    raw_blocks = data.get("blocks", [])
    parts = []
    for blk in raw_blocks:
        col = blk.get("col", "?")
        d = (blk.get("direction", "?")).lower()
        arrow = "\u2193" if d == "down" else "\u2191" if d == "up" else "?"
        top = blk.get("top_row", "?")
        parts.append(f"c{col}{arrow}r{top}")
    return " ".join(parts)


def dump_full(step, cmd, data):
    print(f"\n--- Step {step}: {cmd} ---")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:800])
    # Show block directions
    if data.get("blocks"):
        print(f"  blocks: {format_blocks_arrows(data)}")
    # Check ALL keys for unusual data
    for key in data:
        if key not in ("board", "blocks", "player", "goal", "code", "message", "reached_goal"):
            print(f"  >>> EXTRA KEY: {key} = {data[key]}")
    flag = check_flag(data)
    if flag:
        print(f"  *** FLAG: {flag} ***")


def main():
    print("=== L13 Bonus: Round-trip Solver ===\n")

    TURNAROUND_COL = 5  # 0-indexed, = column 6 in 1-indexed (one before goal)
    START_COL = 0

    MAX_ATTEMPTS = 5
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n>>> Attempt {attempt}")
        data, status = send("start")
        dump_full(0, "start", data)
        all_responses = [data]

        heading = "right"
        turned = False
        returned = False

        for step in range(1, 200):
            flat = json.dumps(data, ensure_ascii=False)
            if FLAG_RE.search(flat):
                print(f"\n*** FLAG FOUND at step {step}! ***")
                (L13_DIR / "bonus_result.json").write_text(
                    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                # Save all
                (L13_DIR / "bonus_probe_responses.json").write_text(
                    json.dumps(all_responses, indent=2, ensure_ascii=False), encoding="utf-8")
                return

            if status == 409 or "crush" in flat.lower() or "zgnieciony" in flat.lower():
                print(f"  DEAD at step {step} — resetting")
                send("reset")
                break

            board = parse_board(data)
            if board is None:
                data, status = send("wait")
                dump_full(step, "wait", data)
                all_responses.append(data)
                continue

            robot_col = find_robot_col(board)
            if robot_col is None:
                data, status = send("wait")
                dump_full(step, "wait", data)
                all_responses.append(data)
                continue

            # Phase transitions
            if heading == "right" and robot_col >= TURNAROUND_COL and not turned:
                print(f"  >>> TURNAROUND at col {robot_col}")
                heading = "left"
                turned = True

            if heading == "left" and robot_col <= START_COL and turned:
                print(f"  >>> BACK AT START col {robot_col}")
                returned = True
                # Now try special commands or just dump state
                print("  Sending 'BB' command...")
                data, status = send("BB")
                dump_full(step, "BB", data)
                all_responses.append(data)
                # Also try 'start' again to see if something different happens
                break

            cmd = decide(board, extract_blocks(data, board), robot_col, heading)
            grid_str = ""
            if board:
                grid_str = " | " + " ".join("".join(r) for r in board)
            arrows = format_blocks_arrows(data)
            print(f"  step={step} col={robot_col} heading={heading} -> {cmd}  [{arrows}]{grid_str}")
            data, status = send(cmd)
            dump_full(step, cmd, data)
            all_responses.append(data)

        # Save responses from this attempt
        (L13_DIR / "bonus_probe_responses.json").write_text(
            json.dumps(all_responses, indent=2, ensure_ascii=False), encoding="utf-8")

        if returned:
            print("\n  Round trip complete! Checking if there's something with different task names...")
            # Try submitting with hints from the puzzle
            for extra_cmd in ["start", "reset", "finish"]:
                print(f"\n  Trying extra command: {extra_cmd}")
                data, status = send(extra_cmd)
                dump_full(999, extra_cmd, data)
                if FLAG_RE.search(json.dumps(data, ensure_ascii=False)):
                    print(f"  *** FLAG: {check_flag(data)} ***")
                    (L13_DIR / "bonus_result.json").write_text(
                        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                    return
            break

    print("\nNo bonus flag found yet. Check bonus_probe_responses.json")


if __name__ == "__main__":
    main()
