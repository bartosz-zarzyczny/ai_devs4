---
name: ai-devs4-workflow
description: "Maintain AI_Devs4 lesson work in this repo. Use for lesson bootstrap, adding or updating browser UIs, updating lesson and root READMEs, keeping requirements.txt in sync with new imports, and validating the smallest relevant step."
argument-hint: "lesson or repo maintenance task"
user-invocable: true
disable-model-invocation: false
---

# AI_Devs4 Lesson Workflow

Use this skill when working on lesson folders in the `ai_devs4` repository.

## When to Use

- Adding a new lesson or extending an existing one.
- Deciding whether a task needs a browser-based UI.
- Updating lesson or root README documentation.
- Introducing new Python libraries (dependency tracking).
- Validating a code change with the smallest practical step.

## Typical Lesson Layout

```
L<NN>/
  task.py                  # main solver / submission script
  ui_server.py             # local HTTP server (stdlib http.server)
  ui.html                  # browser frontend
  README.md                # lesson docs and run instructions
  verification_result.json # saved hub response
  prompts/                 # prompt texts (optional)
  logs/                    # runtime logs (optional)
```

## Procedure

1. Read the lesson README and the root README before editing.
2. Identify the lesson boundary:
   - lesson-specific code stays in the lesson folder
   - cross-lesson summary or index changes belong in the root README
3. If the task benefits from step-by-step inspection, add a browser UI (`ui_server.py` + `ui.html`) following the pattern from L06-L09.
4. Update the lesson README whenever behavior, commands, files, or outputs change.
5. Update the root README when the lesson list, short summary, or shared setup changes.
6. Update root `requirements.txt` when new imported libraries are introduced; prefer reusing existing dependencies.
7. Keep changes minimal, preserve generated artifacts, and validate with the smallest relevant command or script.

## Quality Checks

- The lesson can be run or inspected from the instructions you left behind.
- The documentation matches the current behavior and output files.
- New dependencies are declared before or alongside new imports.
- The UI, if added, is accessible from the browser and supports manual verification or step-by-step inspection.

## Notes

- Treat each lesson as a mostly self-contained mini-project.
- UI servers use stdlib `http.server`, not FastAPI (FastAPI is only used in L03 proxy).
- Hub interactions go through `POST https://hub.ag3nts.org/verify`; API key comes from `.env` (`AI_DEVS_4_API_KEY`).
- Prefer ASCII for new code and configuration unless the file already uses Unicode.
- Keep secrets out of documentation and logs.

## References

- [Workspace instructions](../../copilot-instructions.md)
- [Root README](../../../README.md)
