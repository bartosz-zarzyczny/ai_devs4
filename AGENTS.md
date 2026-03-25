# AGENTS.md — AI Coding Agent Instructions

This file describes conventions, structure, and workflows for AI coding agents
working in the `ai_devs4` repository.

## Project Purpose

The repository contains Python solutions for AI_DEVS 4 lessons.
Each lesson folder (`L01/`, `L02/`, ...) is a self-contained mini-project.
The root `README.md` is the index; each `L*/README.md` is the source of truth
for that lesson.

---

## Environment Setup

### Python

- Virtual environment: `.venv/` at the repo root.
- Activate before running any script:
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
- Install shared dependencies:
  ```powershell
  python -m pip install -r requirements.txt
  ```
- Shared packages: `requests`, `tiktoken`, `fastapi`, `pydantic`,
  `python-dotenv`, `Pillow`, `uvicorn`.
- Some lessons have their own `requirements.txt` — check the lesson README
  before installing.

### Environment Variables

Create a `.env` file at the repo root (never commit it):

```env
API_OPEN_ROUTER_KEY=your_openrouter_key
AI_DEVS_4_API_KEY=your_ai_devs_key
```

- `AI_DEVS_4_API_KEY` — used by hub endpoints (`POST https://hub.ag3nts.org/verify`)
  and most lesson scripts.
- `API_OPEN_ROUTER_KEY` — used by L01 and other LLM-calling scripts via
  OpenRouter.

---

## Repository Structure

```
ai_devs4/
  README.md                   # lesson index + cross-lesson summary
  AGENTS.md                   # this file
  requirements.txt            # shared Python dependencies
  .env                        # secrets (not committed)
  .venv/                      # virtual environment
  .github/
    copilot-instructions.md   # VS Code Copilot workspace instructions
    skills/                   # Copilot skill definitions
  L01/ … L12/                 # lesson folders
```

### Typical Lesson Layout

```
L<NN>/
  task.py                     # main solver / submission script
  ui_server.py                # local HTTP server (stdlib http.server)
  ui.html                     # browser frontend
  README.md                   # lesson docs and run instructions
  verification_result.json    # saved hub response
  prompts/                    # prompt texts (optional)
  logs/                       # runtime logs (optional)
  __pycache__/                # Python bytecode (ignore)
```

---

## Lesson Inventory

| Folder | Task name      | Short description                                                  |
|--------|----------------|--------------------------------------------------------------------|
| L01    | `people`       | Filter, tag, and submit a people list to `/verify`                |
| L02    | `findhim`      | Location + access-level analysis, candidate verification          |
| L03    | `server`       | Local FastAPI proxy server with debug endpoints                   |
| L04    | `sendit`       | Transport declaration, route testing, log responses               |
| L05    | `railway`      | Automated action-sequence executor with rate-limit handling       |
| L06    | `categorize`   | DNG/NEU classifier, prompt caching, browser UI                    |
| L07    | `electricity`  | Image analysis (3x3 grid), rotation plan, PNG meta-flag           |
| L08    | `failure`      | Log compression, browser UI, iterative verification               |
| L09    | `mailbox`      | Search `zmail` API, extract flag from attachment bonus            |
| L10    | `drone`        | Map vision analysis, drone flight mission, browser UI             |
| L11    | `evaluation`   | Anomaly detection in 10 000 sensor JSON files, AWK bonus flag     |
| L12    | `firmware`     | Agentic VM loop (`cooler.bin`), `flaggengenerator` bonus          |

---

## Running Scripts

- Always run scripts from the **repo root** unless the lesson README says
  otherwise:
  ```powershell
  python L10/task.py
  python L10/ui_server.py
  ```
- Use lesson-specific commands from `L*/README.md`. Do not invent new entry
  points.
- UI servers listen on `localhost` (default port 8000 or similar); open in a
  browser to inspect results step-by-step.

---

## Coding Conventions

- **Language:** Python 3. Prefer ASCII; use Unicode only when the file already
  does.
- **HTTP servers:** Use stdlib `http.server` for UI servers (`ui_server.py`).
  FastAPI is used only in L03 proxy.
- **Hub interaction:** `POST https://hub.ag3nts.org/verify` with JSON body
  `{"task": "<name>", "apikey": "<AI_DEVS_4_API_KEY>", "answer": <payload>}`.
- **Secrets:** Never log or print API keys. Mask sensitive fields in JSONL logs.
- **Generated artifacts:** JSON results, logs, and compacted files are part of
  the solution. Preserve them unless the task explicitly requires regeneration.
- **Relative paths:** Scripts often use lesson-local paths; mind the working
  directory when running commands.

---

## Making Changes

1. Read the lesson README and the root README before editing.
2. Keep changes scoped to the relevant lesson folder. Cross-lesson index or
   shared-setup changes go in the root README.
3. Update `L*/README.md` when lesson behavior, commands, files, or outputs
   change.
4. Update root `README.md` when the lesson list or shared setup changes.
5. Update root `requirements.txt` when adding new imports; prefer reusing
   existing dependencies.
6. Keep edits minimal — do not reformat unrelated code or add docstrings to
   untouched functions.

---

## Validation

- After code changes, run the **smallest relevant validation** step:
  ```powershell
  python L<NN>/task.py        # re-run the solver
  python L<NN>/ui_server.py   # launch UI and inspect manually
  ```
- If network calls are required and the environment is offline, report the
  limitation clearly instead of silently skipping.
- For pure logic changes, a quick `python -c "import L<NN>.task"` or a
  dry-run flag (where supported) is sufficient.

---

## Common Pitfalls

- Several lessons rely on external APIs with rate limits or task-specific
  payload formats; check the lesson README for known constraints.
- Scripts assume lesson-local relative paths — running them from a different
  working directory breaks file lookups.
- `verification_result.json` and other generated JSON files are solution
  artifacts, not source files; do not delete them unless re-solving.
- L03 uses FastAPI + uvicorn; all other UI servers use `http.server`.

---

## References

- Root index: [README.md](README.md)
- Workspace instructions: [.github/copilot-instructions.md](.github/copilot-instructions.md)
- Lesson workflow skill: [.github/skills/ai-devs4-workflow/SKILL.md](.github/skills/ai-devs4-workflow/SKILL.md)
- Shared dependencies: [requirements.txt](requirements.txt)
