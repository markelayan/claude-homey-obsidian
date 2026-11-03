---
name: homey-bug
description: Report, write up, check and close a bug through its task note and the Bugs tab. Use when a bug is reported (.bug or homey bug) or a bug task arrives.
---

## Who runs it
`capturer` writes the note up; a fresh `verifier` checks it; the lead (or the main session) records and decides.

## Report
Anyone: `.bug <text>` in the chat, or `homey bug "<what happened>" [--from <who>]`. It makes a task note for `capturer` (kind bug, `bug: reported`, the text word for word under Brief) and a row in `Homey/Bugs.md` under Open. The Bugs tab shows Open.

## capturer: write it up
1. `homey status <task> doing`. Read the note and any files it names.
2. Under the original text in Brief (keep it, never delete it) add bold labels: **Seen**, **Where**, **When**, **Expected**, **Evidence**, **Reporter**. Fill each only from the report and the files it names; write `unknown` where nothing says. Add nothing that is not there.
3. `homey result <task> "<one line: what was written up, what is unknown>"`, then `homey status <task> review`.

## Lead or main session: on the review notice
1. Start a new `verifier` with `homey-check` on the note. It answers reproduced or not, with file and line or command. It is read-only: where a run is needed it says `could not run` and what would settle it.
2. Record the answer in the Result, run `homey bug-state <task> <reported|verified|not reproduced|fixed>`, and close the capturer's task.
3. Act only on `verified`. `not reproduced` goes back to the reporter once. A verified bug's fix is a separate Code task (`homey-lead`) that names the bug note; set `fixed` when that task closes.

## Do not
- Report any bug you find this run with `homey bug "<what happened>"`, including ones outside your task; never fix them unasked. Your last Result line (or last comment) starts `Bugs found:` with `none` or the note names; `homey status review` and `blocked` refuse without it.
- Add facts the report does not hold.
- Fix a bug from its report alone: verify first.

## Known glitches
- Not yet run on a real bug; the first real report will show what to add.
