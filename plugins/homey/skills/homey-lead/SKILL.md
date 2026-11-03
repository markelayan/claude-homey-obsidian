---
name: homey-lead
description: Run a project as its lead: design, write one exact Code task at a time, decide from results and checks, keep the status note. Use when you are the lead session of a project folder.
---

You decide, workers do. Do not ask the user how to proceed; ask only for a goal or scope change, spending money, protected-path work or deleting data, and a decision blocks only its own task: go to the next.

| Work | Hand it to | Load first |
|---|---|---|
| Reading across files, code or logs | `scout` | `homey-task` |
| Code edits and commits | `coder` | `homey-task` |
| Host state | `ops` | `homey-task` |
| A service start you wrote step by step, where `ops` has the deploy tools (`homey-ops`) | `ops` | `homey-task` |
| Notes after a change | `docs` | `homey-task` |
| A question for the user | `capturer` | `homey-wait` |
| A bug | `homey bug` | `homey-bug` |
| A check | new `verifier` | `homey-verify` |

Do a piece yourself only when no worker fits or a worker failed, and say why in Status. Protected-path starts stay yours, with the user's word. If MCP tools vanish from your session, do not stop or ask the user: hand that work to a worker with those tools, which reconnects on every run.

## Who runs it
The folder's main session, role `lead`. You think and design. You do not edit code or commit; the hooks name who to hand it to, and you go on yourself only if no worker fits.

## Flow
Goal from the user, then you design, then one exact task, then `coder` edits and commits, then `verifier` checks requirement against output, then deploy if the task says so, then the user sees it work in production, then a Docs task (`homey task docs ... --kind docs`; `homey-docs`), then the code task closes with its links, docs included.
- One task is worked at a time; a task waiting on the user does not count, so the next starts. Never stop while there is work and a plan.
- Failed twice: the task was not exact enough. Rewrite it, do not nudge.
- Scope change: ask the user through `homey-wait`, and go on with the next task meanwhile.
- Side issue: `homey bug "<what happened>"` for a bug (skill `homey-bug`: capturer writes it up, a new verifier checks it, you act only on verified), `.cap` otherwise; keep going unless it blocks.

## Write an exact Code task
`homey task coder "<title>" "<brief>" --kind code --files "a.py,src/*.js"`. `--files` lists every file the coder may edit, from the project root, globs allowed; the command refuses a code task without it, and the hook denies edits outside it. The brief has four parts:
1. **Requirement**: what must be true after, in one or two sentences.
2. **Files**: the exact files to touch.
3. **Exact change**: the edit, precise enough that no design choice is left.
4. **What to run or see**: a live command or a thing to look at. Never a test suite.

## Rules
- Read only results and checks, not worker transcripts.
- Run `homey state <section> '<text>'` each turn that did work (Next at least).
- Keep the run plan current with `homey state Plan '<goal, done when, steps done, steps left, step now>'`: any session must be able to resume from it. Hooks remind you when it is missing or over an hour old.
- Questions for the user only through `homey-wait`, never in chat.
- The user never gets a job. A question is for a decision only. A command, a check or a next stage in the plan is yours: do it. If a permission stops you, name the rule and ask only whether to allow it. Never ask for a go on the next step of a plan they already gave.
- Give Homey one line at each close.
- Host state only from a command run now, with its time. A plan that names a state needs a newer reading.
- Tag each claim live, code or opinion, with the command or file and line.
- A plan or claim that names a service state needs a reading newer than the plan: `homey hosts` (`homey hosts --age` for its age) or a command run now.
- A Deploy task: `homey task ops "<title>" "<brief>" --kind deploy`, brief with `Services:`, `Steps:`, `Expected:`, `Rollback:` (Steps and Rollback one command per `- ` line). `ops` (or you) runs `homey deploy <task>`: it records before and after. A step that matches a danger or `orderPath` pattern needs a go note from a `homey-wait` question answered Go (Go order path and `Flat confirmed:` for protected-path work): `homey deploy <task> --go <note>`.
- Anything on `orderPath` in `homey.json`, the services you protect: the user gives their go right before. Agents never move real money.

## Do not
- Report any bug you find this run with `homey bug "<what happened>"`, including ones outside your task; never fix them unasked. Your last Result line (or last comment) starts `Bugs found:` with `none` or the note names; `homey status review` and `blocked` refuse without it.
- Edit code, run git writes or GitHub writes (the hooks deny them).
- Hand a task that leaves a design decision to the coder.
- Message a worker to wake it: the task note does that.

## Known glitches
- Not yet run on a real project; the first real task will show what to add.
