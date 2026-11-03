---
name: homey-docs
description: Update the notes a code task changed, check them against the code, add one changelog line, and link the code task. Use when a docs task note arrives.
---

## Who runs it
Agent `docs`, from a task note of kind `docs`. The lead writes it after the user has seen the change work in production.

## The brief holds
The code task, its commit, and which vault notes to update, if any.

## Steps
1. `homey status <task> doing`. Read the code task, its Result and the diff (`git show <commit>`).
2. Check each line you write against the code, not against other notes.
3. Update only the notes the brief names.
4. Add one plain sentence for the reader with `homey changelog "<what changed for the reader>" --task <code task>` (the commit comes from the code task's link).
5. `homey link <code task> docs <your task name>`.
6. `homey result <task> "<notes updated, changelog line>"`, then `homey status <task> review`.

## If a named note disagrees with the code in a way the task did not touch
Do not fix it. Report it with `homey bug "<what disagrees, where>"`, and say so in your Result.

## Do not
- Report any bug you find this run with `homey bug "<what happened>"`, including ones outside your task; never fix them unasked. Your last Result line (or last comment) starts `Bugs found:` with `none` or the note names; `homey status review` and `blocked` refuse without it.
- Design, or edit code.
- Edit a note the brief does not name.
- Copy a claim from another note instead of checking the code.

## Known glitches
- Not yet run on a real case; the first real docs task will show what to add.
