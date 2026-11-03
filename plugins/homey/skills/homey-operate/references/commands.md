# bin/homey commands

Source: `bin/homey`, `scripts/homey_tasks.py`. Run as `homey <command>`.

## How it runs
| Item | Fact |
|---|---|
| Config | `$HOMEY_CONFIG`, else `.claude/homey.json` found upward from the current directory. Root = the folder above `.claude`. Vault = root + `vault` |
| Writes | Only `task`, `ask`, `state`, `link`, `bug`, `bug-state`, `changelog`, `hosts`, `deploy`, `later`, `answer`, `comment`, `status`, `result`. Each swaps the whole note through a hidden temp file, so Obsidian and the watcher never read half a note |
| Errors | One line `homey: <reason>` on stderr, exit 1, note unchanged. Exception: `data` prints `{"error": ...}` and exits 0 |
| No or unknown command | Prints the usage text, exit 2 |
| Task reference | A note name, name with `.md`, vault-relative path or absolute path. It must resolve inside the `tasks.dir` folder: otherwise `not a task note: ...` or `no task note: ...` |

## Read commands
| Command | Prints | Errors |
|---|---|---|
| `find <term>` | `path \| summary`, at most `findLines` (15) lines, then `... N more; narrow the term`; `no match`. Matches note name first, then summary. Only folders in `domains`, not `skipDirs` or dot folders | usage when the term is empty |
| `get <note>[#heading]` | No heading: `path \| summary`. With heading: that section, cut at `getLines` (200) lines or `getChars` (8000) chars with a `[truncated: ...]` line. A note is found by exact name or path first, then by part of the name | `no note in domains`, `cannot read` (unreadable or over `noteBytes`), `no heading '...'` plus up to 12 headings |
| `now` | `Next: ... \| Inbox n \| Stale n \| Tasks n`. Tasks = unchecked `- [ ]` lines across the domain notes | config errors |
| `data` | JSON for the mod: config, today, next, inbox, stale, tasks, tasksBoard, projects, decisions, tables | never fails |
| `tasks` | JSON list of every note in the task folder: path, name, owner, status, summary, comments, result, brief, options, later. A note that is not a task, or is unreadable, is `{path, name, bad}` | `homey.json missing: tasks` |
| `take <session>` | JSON list of messages waiting for that session id. Each is claimed by moving its file to `inbox/taken/`, so it is taken once. The mod calls this | none for an unknown session: `[]` |

## Write commands
| Command | Writes | Errors |
|---|---|---|
| `task <owner> "<title>" "<brief>" [--kind code\|bug\|deploy\|docs] [--files "a,b"]` | New `Tasks/<YYYY-MM-DD HHMM> <title>.md` with `type: task`, `owner`, `status: todo`, `summary` (the title), then `## Brief`, `## Comments`, `## Result`. In the file name `\ / : * ? " < > \| # ^ [ ]` become spaces (runs of spaces fold to one; tested: `A/B: "x"?  title` gives `A B x title`) and it is cut at 80 characters; a clash adds ` 2`, ` 3`. Prints the vault-relative path | usage (needs exactly 3 arguments besides --kind); `--kind takes one of: ...` (a `--kind deploy` brief must hold Services:, Steps:, Expected:, Rollback:, with `- ` command lines under Steps and Rollback; writes property `files`, a code task or owner `coder` must give `--files`; writes property `kind`; owner `coder` with no `--kind` means `code`); `unknown owner: x; owners: ...` |
| `ask "<question>" "<why>" "<context>" ["<label>\|<reply>"...]` | A task with owner `mark` (the watcher ignores it): summary = question, Brief = why, plus `## Context` and `## Options` (`- label \| reply` per option) before Comments. Prints the path | usage (fewer than 3 arguments); `a question needs its context` (empty context); `the context is missing, or has no text after: <labels>` (context needs Needed:, How it came up:, Done:, Not done:, Each answer:, Pick:, Evidence:); `a question needs at least one option`; `options look like "<label>\|<reply>"` (split on the first `\|`, both sides non-empty) |
| `state [<section> '<text>']` | No arguments: prints `hooks.statusFile` (Homey/Status.md). Else replaces that section (Goal, Open task, Done this session, Decided, Waiting on user, Repo, Hosts, Next), refills Repo from git (branch, uncommitted, unpushed, or `no git`) and sets `updated`. Creates the note on first use. The Stop hook (`statusCheck`) asks the main session to run it after a work turn | unknown section; note over `limits.statusChars` |
| `deploy <task> [--go <note>]` | Runs a `kind: deploy` task once through `sh`: Before (hosts), the `- ` steps one at a time (120 s each, stop at the first failure, command, exit code and first 10 lines saved), After. No go note is needed unless a step matches the danger patterns or `orderPath`: then `--go` names a Tasks/ note owned by the user, done, Result starting `Go` (exactly `Go order path`, with `Flat confirmed:` in its Context). Sets `deploy:` first, so a second run is refused. On failure prints the Rollback lines, never runs them, status `blocked` | danger step with no go note; already deployed |
| `hosts [--age]` | Runs every check in `homey.json` `hosts` ({host, check, cmd}; no command comes from arguments) with a 6-second limit. Result is the first output line cut to 160 characters, or `down: refused`, `down: timed out`, `down: exit N`; a curl `000` is down. Rewrites `systemStateFile` (`Homey/System state.md`: Host, Check, Result, Read at; `read` in the frontmatter), sets the status note's Hosts line (read time, up and down counts) and prints the table. `--age` prints minutes since the last read | no hosts; no reading yet |
| `changelog "<line>" --task <task> [--commit <hash>]` | One row (Change, Task, Commit) at the top of today's `## YYYY-MM-DD` section of `changelogFile` (`Homey/Changelog.md`, created on first use; sections newest first). Commit defaults to the task's `commit` link. Prints the path | usage; no such task; no `changelogFile` |
| `status <task> review\|blocked` bug line | Warns, and still moves it, unless the Result has a line starting `Bugs found:` or the last comment's text does (`none`, or the note names from `bug`). Tasks owned by the user are exempt. `state 'Bugs found' '<text>'` fills that section and stamps `bugs_checked`; `state Next` stamps `next_checked` | missing `Bugs found:` line |
| `bug "<what happened>" [--from <who>]` | A normal task note for `capturer`: kind `bug`, `bug: reported`, `reporter` (`--from`, else the running role, else the user), title `Bug: <first words>`, Brief = the text word for word. Adds a row to `bugsFile` (`Homey/Bugs.md`, created on first use) under `## Open`. Any role may run it. Prints the path | usage; no `bugsFile` |
| `bug-state <task> <reported\|verified\|not reproduced\|fixed>` | Sets `bug:` in the note and updates its row; `fixed` and `not reproduced` move the row to `## Closed`, the others keep or return it to `## Open` | unknown state; not a bug note |
| `link <task> <commit\|pr\|issue\|branch\|docs> <value>` | Sets that property in the task's frontmatter; a later value replaces it. A `commit` value must exist in the project repo (`git cat-file`) unless it is a URL. Shown as columns in `Tasks.base` | usage |
| `later <task>` | Sets property `later: <today>`: the question stays open under For later | usage |
| `answer <task> "<text>"` | Appends `- mark: <text>` to Comments, writes the text to Result, sets status `done`. Works only on a task owned by the user (a question); other notes are refused | usage; `already answered` when status is already `done` |
| `comment <task> <author> "<text>"` | Appends `- <author>: <text>` (whitespace folded to one line) under Comments. The author is not checked | usage (needs exactly 3 arguments) |
| `status <task> <status>` | Replaces the `status:` property. `review` is refused with an empty Result, or for a `code` task with neither `commit` nor `pr`; `done` is refused for a `code` task with no `docs` link (a docs task reports first), and for a task of kind `code` with neither `commit` nor `pr` | usage; `unknown status: x; statuses: todo, doing, blocked, review, done`; `no status property` |
| `result <task> "<text>"` | Replaces the whole `## Result` section with the text | usage; `no ## Result section` |

## Config errors (all commands)
| Message | Cause |
|---|---|
| `no .claude/homey.json found` | Run from outside the vault with no `$HOMEY_CONFIG` |
| `homey.json is not valid JSON` / `must be an object` | Bad file |
| `homey.json missing: a, b` | A required top-level key is absent: vault, dailyDir, inboxDir, domains, skipDirs, types, nextPattern, dailyGlob, staleDays, statuses, limits, band, panes |
| `limits missing or not positive ints: ...` | findLines, getLines, getChars, rowChars, decisions, dataRows, noteBytes |
| `domains/panes must be lists, types an object`; `nextPattern is not a valid regex` | Bad shapes |
| `homey.json missing: tasks` | Task commands without a `tasks` object |

Unknown: whether `take` for a session with no `inbox/` folder at all errors; the code uses a glob, so it should return `[]`, not run here.

## Main role
| Command | Does | Errors |
|---|---|---|
| `handoff` | A one-call cheap model writes `Homey/Session handoff.md` from the main session's transcript; sets `tasks.homeySession` to empty, so the first non-worker prompt in this folder takes it | No main session, no transcript, call failed: the role stays |
| `agent-add <role> --headless <model>` | Runs `claude -p` once from the project root (`--model`, `--agent <role>` when `.claude/agents/<role>.md` exists, the configured `permissionMode`, json output) with the HOMEY-WORKER start prompt; reads `session_id`; writes the owner (no `appSession`) and a `Homey/Agents.md` row. The pane shows the owner free and the watcher wakes it by `--resume` | role already recorded; no session started |
| `claim-main` | Makes the one busy interactive session here main | Not exactly one busy session |

## Advisor
| Command | Does | Errors |
|---|---|---|
| `advise <task> ["<question>"] [--plan <note>]...` | A task note for `advisor` with a fixed packet, property `advises`; its `result` also fills `## Advice` in `<task>`, and a comment wakes an asking agent. Logs in `advice.log` | Advisor off, agent not allowed, no question for an agent's task, already answered, daily limit |
| `escalate <note> [--plan <note>]... [--again]` | One senior call; writes `## Senior advice` with its cost, prints it, logs it | No senior set, no junior advice, gaps not filled, already asked, closed note, daily limit, call failed |
| `advisor <model> [role...]`, `advisor senior <model>`, `advisor senior off`, `advisor off` | Sets or removes `advisor` and its `senior` in the settings | |

`approvalGuard` (hooks): no Claude session runs `homey answer`; the pane does (`hooks/register.js` calls it through the mod host). `.ok` lifts it. `steerOnly` (config) lists checks (roleGuard, taskScope, commitLink, noTestRuns, paneQuestions, pluginLock) that remind instead of deny: the call goes ahead and the agent gets the reason as context. `status review`, `blocked`, `done` and `task coder` warn on a missing Bugs found line, Result, link, docs link or `--files`, and still do it.
