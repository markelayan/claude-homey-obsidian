---
name: homey-ops
description: Report host state from the fixed checks run by homey hosts, with the read time. Read-only. Use when a task asks for the state of a host or service.
---

## Who runs it
Agent `ops`, from a task note. Reports host state, and runs a Deploy task only through `homey deploy`.

## Steps
1. `homey status <task> doing`.
2. Run `homey hosts`. It runs the fixed checks from `homey.json` (`hosts`) and rewrites `Homey/System state.md`.
3. Report what it printed word for word, with the read time, in `homey result <task> "..."`. Then `homey status <task> review`.
4. Say what a down result means only if the task's notes say so. Never guess a cause.

## Deploy task
1. `homey status <task> doing`. Read the Brief: Services, Steps, Expected, Rollback, and the go note it names, if any.
2. Run `homey deploy <task>` (add `--go <go note>` when the task names one: a step that matches a danger or order-path pattern needs it). It reads the hosts before and after, runs each step once and records them in the Result.
3. Report the Result word for word, and compare After with Expected only as the task says. Then `homey status <task> review`; if it failed the task is already blocked.

Never run a step any other way, and never run Rollback: on failure the command prints the Rollback lines and Homey or the lead decides.

## Service start task
Only where your agent file lists the deploy tools. The lead designs it; you run it exactly. The Brief names the stack and endpoint IDs, the service, the file holding the full stack, the lines that change, and what to read afterwards.
1. `homey status <task> doing`. If the service is in `orderPath` of `homey.json` (order path), or the Brief lacks any of the above: `homey status <task> blocked` with a comment saying so.
2. Run `homey hosts`. Read the stored stack with the deploy tool's read call. Compare it with the file: if anything differs beyond the named lines, block and say which lines.
3. Run the deploy tool's update call once, with the file's content word for word. Do not retry.
4. Read what the Brief names, then the deploy tool's status call and `homey hosts`. Report both word for word with the read time in `homey result`, then `homey status <task> review`. On any failure block; never roll back or fix.

## Rules
- Report any bug you find this run with `homey bug "<what happened>"`, including ones outside your task; never fix them unasked. Your last Result line (or last comment) starts `Bugs found:` with `none` or the note names; `homey status review` and `blocked` refuse without it.
- State only what `homey hosts` shows, with its read time. `homey hosts --age` gives the minutes since the last read.
- Adding or changing a check means asking Homey or the lead to change the config.
- Never start, stop or change a service outside a Service start task.

## Known glitches
- A check that cannot connect shows `down: refused`; that does not say whether the service or the network is the cause.
- Not yet run on a real case.
