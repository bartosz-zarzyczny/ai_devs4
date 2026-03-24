#!/usr/bin/env python3
"""L12 - firmware: agentic loop that connects to a restricted Linux VM,
finds the cooler.bin password, reconfigures settings.ini and runs the binary,
then submits the ECCS-... code to the hub.

Usage:
    python L12/task.py           # normal run
    python L12/task.py --reboot  # reboot VM first, then run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_KEY = os.environ["AI_DEVS_4_API_KEY"]
OPENROUTER_KEY = os.environ["API_OPEN_ROUTER_KEY"]

SHELL_URL = "https://hub.ag3nts.org/api/shell"
VERIFY_URL = "https://hub.ag3nts.org/verify"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

LLM_MODEL = "anthropic/claude-sonnet-4-5"  # best reasoning per task hint

L12_DIR = Path(__file__).resolve().parent
VERIFICATION_FILE = L12_DIR / "verification_result.json"
AGENT_LOG_FILE = L12_DIR / "agent_log.json"

MAX_AGENT_STEPS = 50
RETRY_AFTER_BAN_DEFAULT = 30  # seconds to wait when banned

# ---------------------------------------------------------------------------
# Shell & verify helpers
# ---------------------------------------------------------------------------

CALL_DELAY = 3  # seconds between shell calls to avoid rate limiting
_last_call_time: float = 0.0


def shell_cmd(cmd: str) -> str:
    """Send a single shell command to the remote VM and return the output text.

    Handles HTTP-level errors gracefully so the agent can react to them.
    Enforces a minimum delay between calls to avoid rate limiting.
    """
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < CALL_DELAY:
        time.sleep(CALL_DELAY - elapsed)

    try:
        resp = requests.post(
            SHELL_URL,
            json={"apikey": API_KEY, "cmd": cmd},
            timeout=30,
        )
    except requests.RequestException as exc:
        return f"[network error] {exc}"
    finally:
        _last_call_time = time.time()

    if resp.status_code == 200:
        try:
            body = resp.json()
            # API response format: {"code": N, "message": "...", "data": list|str}
            # The actual content is always in "data"
            if isinstance(body, dict) and "data" in body:
                d = body["data"]
                if isinstance(d, list):
                    return "\n".join(str(x) for x in d)
                return str(d)
            # Fallback: return message
            if isinstance(body, dict):
                return body.get("message", json.dumps(body))
            return str(body)
        except ValueError:
            return resp.text

    if resp.status_code == 429:
        wait = RETRY_AFTER_BAN_DEFAULT
        try:
            body = resp.json()
            wait = int(body.get("retry_after", RETRY_AFTER_BAN_DEFAULT))
        except Exception:
            pass
        msg = f"[rate limit] HTTP 429 - too many requests, waited {wait}s automatically"
        print(msg)
        time.sleep(wait)
        _last_call_time = time.time()
        return msg

    if resp.status_code == 403:
        wait = RETRY_AFTER_BAN_DEFAULT
        reason = "security violation"
        try:
            body = resp.json()
            wait = int(body.get("ban_seconds", RETRY_AFTER_BAN_DEFAULT))
            reason = body.get("message", reason)
        except Exception:
            pass
        msg = f"[banned] HTTP 403 - {reason} - ban lasts {wait}s. Do NOT retry the same command."
        print(msg)
        return msg

    if resp.status_code == 503:
        msg = "[unavailable] HTTP 503 - service temporarily unavailable"
        print(msg)
        return msg

    # Any other error - include full body so agent can read the message
    try:
        body = resp.json()
        return f"[error] HTTP {resp.status_code}: {json.dumps(body, ensure_ascii=False)}"
    except Exception:
        return f"[error] HTTP {resp.status_code}: {resp.text[:400]}"


def submit_answer(confirmation: str) -> dict:
    """Submit the ECCS code to the hub and return the parsed response."""
    payload = {
        "apikey": API_KEY,
        "task": "firmware",
        "answer": {"confirmation": confirmation},
    }
    try:
        resp = requests.post(VERIFY_URL, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as exc:
        try:
            return exc.response.json()
        except Exception:
            return {"error": str(exc)}
    except requests.RequestException as exc:
        return {"error": str(exc)}


def reboot_vm() -> str:
    """Reboot the remote VM via the shell API."""
    print("[reboot] Sending reboot command...")
    out = shell_cmd("reboot")
    print(f"[reboot] Response: {out}")
    print("[reboot] Waiting 10s for VM to restart...")
    time.sleep(10)
    return out


# ---------------------------------------------------------------------------
# OpenRouter / LLM helpers
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "shell_cmd",
            "description": (
                "Execute a single shell command on the remote Linux VM. "
                "The VM has a non-standard, limited set of commands. "
                "Always start with 'help' to discover what is available. "
                "Do NOT access /etc, /root, or /proc/. "
                "Respect .gitignore files you find (do not touch listed paths). "
                "Returns the command output as a string."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {
                        "type": "string",
                        "description": "The shell command to execute, e.g. 'help', 'ls /opt', 'cat /opt/firmware/cooler/settings.ini'",
                    }
                },
                "required": ["cmd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_answer",
            "description": (
                "Submit the ECCS-... code obtained from running cooler.bin to the hub. "
                "Use this ONLY when you have the actual code from the binary output."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmation": {
                        "type": "string",
                        "description": "The code in format ECCS-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                    }
                },
                "required": ["confirmation"],
            },
        },
    },
]

SYSTEM_PROMPT = """\
You are an expert Linux admin agent operating on a restricted virtual machine via a shell API.

YOUR GOAL:
1. Run /opt/firmware/cooler/cooler.bin and obtain the secret code it prints.
2. The code format is: ECCS-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
3. Submit that code using the submit_answer tool.

CONSTRAINTS (CRITICAL - violations cause an API ban):
- Never access /etc, /root, or /proc/ directories.
- The first thing you MUST do is read /opt/firmware/cooler/.gitignore, then NEVER touch files listed there.
- You work as a normal (non-root) user.

WHAT YOU ALREADY KNOW about /opt/firmware/cooler/:
- Files present: .env, .git/, .gitignore, cooler-is-blocked.lock, cooler.bin, logs/, settings.ini, storage.cfg
- settings.ini content:
    [main]
    #SAFETY_CHECK=pass          <- commented out, needs real password
    power_plant_id=PWR6132PL

    [test_mode]
    enabled=true                <- should be false

    [cooling]
    power_percent=100
    enabled=false               <- should be true

STEPS TO FOLLOW IN ORDER:
1. Read /opt/firmware/cooler/.gitignore to know which files you must NOT touch.
2. Read /opt/firmware/cooler/.env - it likely contains the password.
3. Also check storage.cfg for the password.
4. Once you have the password, use editline to fix settings.ini:
   - Uncomment SAFETY_CHECK and put the real password
   - Set test_mode enabled=false
   - Set cooling enabled=true
   The editline syntax is: editline <file> <line-number> <new-content>
   To see line numbers cat the file first - count lines from 1.
5. Try removing cooler-is-blocked.lock with rm if the binary won't start.
6. Run /opt/firmware/cooler/cooler.bin <password>
7. Parse the ECCS-... code from the output.
8. Call submit_answer with the code.

NOTES on editline:
- editline replaces the entire content of the specified line (the whole line, not appended).
- To uncomment SAFETY_CHECK change "#SAFETY_CHECK=pass" to "SAFETY_CHECK=<actual-password>"

ERROR HANDLING:
- If you see [rate limit], try the same command again (delay was handled automatically).
- If you see [banned], STOP and do NOT retry. Report the ban.
- Use reboot command only as a last resort.
\
"""


def call_llm(messages: list[dict]) -> dict:
    """Call OpenRouter and return the raw response message dict."""
    resp = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": LLM_MODEL,
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto",
            "max_tokens": 4096,
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------

def extract_eccs(text: str) -> str | None:
    m = re.search(r"ECCS-[A-Za-z0-9]{40,}", text)
    return m.group(0) if m else None


def _write_agent_log(log: dict) -> None:
    try:
        AGENT_LOG_FILE.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def run_agent(do_reboot: bool = False) -> dict | None:
    if do_reboot:
        reboot_vm()

    log: dict = {"status": "running", "steps": [], "final_result": None}
    _write_agent_log(log)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Start now. First read /opt/firmware/cooler/.gitignore, then /opt/firmware/cooler/.env to find the password, then fix settings.ini and run the binary."},
    ]

    for step in range(1, MAX_AGENT_STEPS + 1):
        print(f"\n--- Step {step}/{MAX_AGENT_STEPS} ---")

        msg = call_llm(messages)
        messages.append(msg)

        # No tool calls -> model gave a final text response
        if not msg.get("tool_calls"):
            content = msg.get("content", "")
            print(f"[agent] {content}")
            log["steps"].append({"step": step, "type": "text", "content": content})
            # Check if the agent somehow embedded the code in text
            code = extract_eccs(content)
            if code:
                print(f"[agent] Found ECCS code in text response: {code}")
            log["status"] = "done"
            _write_agent_log(log)
            break

        # Process each tool call
        tool_results = []
        done = False
        for tc in msg["tool_calls"]:
            fn_name = tc["function"]["name"]
            try:
                fn_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                fn_args = {}

            print(f"[tool] {fn_name}({json.dumps(fn_args, ensure_ascii=False)})")

            if fn_name == "shell_cmd":
                result = shell_cmd(fn_args.get("cmd", ""))
                print(f"[output] {result[:500]}")
                log["steps"].append({"step": step, "type": "shell", "cmd": fn_args.get("cmd", ""), "output": result})
            elif fn_name == "submit_answer":
                confirmation = fn_args.get("confirmation", "")
                result_dict = submit_answer(confirmation)
                result = json.dumps(result_dict, ensure_ascii=False)
                print(f"[submit] {result}")
                # Save verification result
                VERIFICATION_FILE.write_text(
                    json.dumps(result_dict, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                log["steps"].append({"step": step, "type": "submit", "confirmation": confirmation, "result": result_dict})
                log["final_result"] = result_dict
                done = True
            else:
                result = f"[unknown tool] {fn_name}"
                log["steps"].append({"step": step, "type": "unknown", "tool": fn_name})

            tool_results.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

        messages.extend(tool_results)
        _write_agent_log(log)

        if done:
            print("\n[done] Submission sent. Check verification_result.json.")
            log["status"] = "done"
            _write_agent_log(log)
            try:
                return json.loads(tool_results[-1]["content"])
            except Exception:
                return None

    if log["status"] == "running":
        log["status"] = "max_steps_reached"
        _write_agent_log(log)
    print(f"[warn] Reached max steps ({MAX_AGENT_STEPS}) without submitting.")
    return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="L12 firmware task solver")
    parser.add_argument("--reboot", action="store_true", help="Reboot the VM before starting")
    args = parser.parse_args()

    result = run_agent(do_reboot=args.reboot)
    if result:
        print("\n=== FINAL RESULT ===")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\n[warn] No result obtained.")


if __name__ == "__main__":
    main()
