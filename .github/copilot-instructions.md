# ai_devs4 Workspace Instructions

## Scope

- This repository contains solutions for AI_DEVS 4 lessons.
- Treat each lesson folder as a mostly self-contained mini-project.
- When a lesson has its own `README.md`, use it as the source of truth for that lesson.

## Repository Structure

- `README.md` at the repo root is the entry point and index for the lesson folders.
- Lesson folders usually contain scripts, prompts, local UI files, logs, and generated outputs.
- New lessons should include a browser-based UI (`ui_server.py` + `ui.html`) when the task benefits from step-by-step inspection or manual verification.
- Typical lesson files: `task.py` (main solver/submission), `ui_server.py` (local HTTP server based on stdlib `http.server`), `ui.html` (frontend), `verification_result.json` (hub response).
- Keep changes focused to the lesson or file the user asked about.

## Python Setup

- Use the existing virtual environment in `.venv` when possible.
- Install shared dependencies with `python -m pip install -r requirements.txt` from the repo root.
- Some lessons have extra dependencies in their own `requirements.txt` files, so check the lesson README before adding packages.

## Environment Variables

- The repo expects a root `.env` file.
- Common keys include `API_OPEN_ROUTER_KEY` and `AI_DEVS_4_API_KEY`.
- Never commit secrets or echo them into logs unless the lesson explicitly needs redacted debug output.

## Working Conventions

- Prefer running scripts from the repo root unless a lesson README says otherwise.
- Use lesson-specific commands and flags from that lesson’s README instead of inventing new entry points.
- Update the lesson README when adding or changing lesson behavior, and update the root README when the lesson index or cross-lesson summary changes.
- Update `requirements.txt` when new libraries are introduced for imports, and prefer reusing existing dependencies before adding more.
- Preserve existing generated artifacts unless the task explicitly requires regenerating them.
- Keep edits minimal and avoid unrelated formatting changes.
- Prefer ASCII for new code and configuration unless the file already uses Unicode.

## Validation

- After making code changes, run the smallest relevant validation step for the affected lesson.
- For Python scripts, prefer a targeted script run or a lesson-specific verification command over a full-repo sweep.
- If a lesson depends on network calls or hub endpoints, validate only what is practical in the current environment and report any limits clearly.

## Common Pitfalls

- Several lessons rely on external APIs, rate limits, or task-specific payload formats.
- Some scripts assume files are in lesson-local paths, so be careful with current working directory and relative paths.
- Generated outputs such as JSON, logs, and compacted files are often part of the solution flow, not source files.

## Reference Files

- Root overview: `README.md`
- Lesson instructions: each `L*/README.md`
- Shared dependencies: `requirements.txt`
