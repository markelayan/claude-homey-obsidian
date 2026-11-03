---
name: homey-code
description: Make exactly the edits a Code task note names, commit with a Task line, link the commit and set review. Use when a task note assigns you code work.
---

## Who runs it
Agent `coder`, from a task note.

## Steps
1. `homey status <task> doing`. Read the Brief: Requirement, Files, Exact change, What to run or see.
2. Edit only the files in the task's `files` field (the hook denies others) and the lines the task names. Use the Edit tools: `sed -i`, `perl -i`, `tee` and redirects to a file are denied. If another file is needed, comment and set blocked. Make no design or scope decision.
3. Do the "run or see" step and note what you saw. Never run test suites (the hook denies test commands).
4. Commit with `-m`; the message holds a line `Task: <task note name>` (the note name from `Tasks/`). No `-F`, no `--no-verify`, no force push. For a pull request, the create command takes `--body` with the same line.
5. `homey link <task> commit <hash>` (or `pr <url>`).
6. `homey result <task> "<what changed, what you saw>"`, then `homey status <task> review`.

## If it is unclear or fails
`homey comment <task> coder "<why>"` and `homey status <task> blocked`. Do not guess, widen the scope or retry past the task's words.

## Do not
- Report any bug you find this run with `homey bug "<what happened>"`, including ones outside your task; never fix them unasked. Your last Result line (or last comment) starts `Bugs found:` with `none` or the note names; `homey status review` and `blocked` refuse without it.
- Edit under `.claude`, or outside the project.
- Add fixes the task did not ask for; comment them instead.

## Known glitches
- The commit hook sees only the command text: put the Task line in the `-m` text itself.
- Not yet run on a real task.
