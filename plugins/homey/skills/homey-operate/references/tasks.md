# Task notes and the watcher

Source: `scripts/homey_tasks.py`, `scripts/homey_watch.py`, `scripts/homey_steer.py`, `.claude/homey.json` key `tasks`.

## Note format
| Part | Fact |
|---|---|
| Properties | `type: task`, `owner`, `status`, `summary` (quoted); optional `kind` (code, bug, deploy, docs) and the links `commit`, `pr`, `issue`, `branch` (`homey link`); a question also gets `later: <date>` when put off |
| Sections | `## Brief`, `## Comments`, `## Result`; a question also has `## Context` and `## Options` before Comments |
| Comment line | `- <author>: <text>`. Any list line counts; a line with no known name before the colon counts as the user typing |
| Known names | Owners in `tasks.owners` plus `tasks.people` (mark, homey, watcher) |
| Bad note | No properties block, a missing section, or `type` not `task`: shown as `bad`, skipped by the watcher, logged |

## Statuses and who moves them
| Status | Set by | Meaning |
|---|---|---|
| `todo` | `task` command; the user dragging a card back or "Run again" in the pane | Waiting for a nudge. Moving it back to todo after another status resets its nudge count to 0 |
| `doing` | The owner at the start | Owner is working |
| `review` | The owner at the end | Finished; Homey checks it against the brief |
| `blocked` | The owner with a comment, or the watcher | Needs something. Watcher reasons: nudge limit, day limit, run failed, run ended with the status still todo or doing, open session dropped the message, stalled again after its restart |
| `done` | Homey after checking (a `code` task needs a `commit` or `pr` link first); the pane's `answer` for a question | Closed. The watcher and the pane ignore it |

## Watcher pass (every `tickSeconds`, 10)
| Step | What happens |
|---|---|
| 1 | Finish ended runs: record the end; if the note is still `todo` or `doing`, or the run errored, block it. A run older than `runTimeoutSeconds` (3600) gets SIGTERM |
| 2 | Read all task notes. Settle messages: a message an open session took counts as one nudge and its comments become seen; waiting messages whose task is done or gone are dropped |
| 2b | Check working tasks against their session transcript, which a run writes whatever the app shows: quiet for `stallMinutes` or denied `stallDenials` times gives a watcher comment and one notice to Homey; a run quiet for `stallStopMinutes` is stopped, then restarted `stallRestarts` times, then blocked |
| 3 | Ask `claude agents --json` which sessions are live and write `status.json` (time and live sessions). If that fails nothing is nudged this pass |
| 4 | Decide, per task whose owner is a known agent and whose status is todo, doing, blocked or review: act only on a new `todo` (or one reopened) or on unseen comments from anyone but the owner and the watcher |
| 5 | Skip if the owner already has a run, or `maxRuns` (2) runs are going. Block instead of nudging when the per-task or per-day limit is reached |
| 6 | Record the action in `state.json` before doing it, so a restart cannot repeat it; then act |
| 7 | For each agent task that moved to `review` or `blocked` since the last pass, leave Homey one notice |
| 8 | Forget tasks that no longer exist; save state |

An unknown owner or status gets one `skip` line in the log and no block.

## Wake routes
| Owner session | Route | Counted as a nudge |
|---|---|---|
| Not open in the app | `claude -p --resume <sessionId> --model <model> --permission-mode <tasks.permissionMode> --output-format json "<prompt>"`, started detached from the vault folder with env `HOMEY_TASK`, `HOMEY_SEEN`, `HOMEY_OWNER`, `HOMEY_CONFIG`. Output goes to `run-<owner>.json` | At once |
| Open in the app (listed by `claude agents --json`) | The watcher writes `inbox/<session>--<hash>.json` with the prompt and adds a watcher comment "message left for it". That session's own mod calls `homey take <session>` every 15 s and submits the prompt as a user message | When taken |
| Homey itself | Notices go to `inbox/` for `tasks.homeySession`. Its mod submits them without the user flag, only when Homey is idle | Not counted |

`holdMinutes` (now 0): with a value above 0 the watcher first leaves a "session is open in the app; will message it after N min" comment, and sends the message after N minutes. At 0 it messages at once. If the app drops the message the mod comments the reason and sets `blocked`.

## Limits
| Key | Now | Effect |
|---|---|---|
| `nudgesPerTask` | 5 | Then the task becomes `blocked` with a watcher comment; drag to `todo` to go again |
| `nudgesPerDay` | 50 | Same, for all tasks that day |
| `maxRuns` | 2 | Runs at the same time; an owner never has two |
| `tickSeconds` | 10 | Time between passes |
| `runTimeoutSeconds` | 3600 | A run over this gets SIGTERM |
| `stallMinutes` | 10 | Quiet this long: comment, notice to Homey, Stuck in the pane. A long tool call looks quiet too |
| `stallStopMinutes` | 30 | Quiet this long: the run's process group is stopped, killed 60 s later if still there |
| `stallRestarts` | 1 | Restarts per task after a stop, on the same session; then `blocked`. Run again does not refill it |
| `stallDenials` | 3 | Hook denials in one run before Homey gets a notice |

## Finished-task notices
Sent for a task whose owner is an agent (not in `tasks.people`) when its status changes to `review` or `blocked` after the watcher had already seen it. The text names the task, owner and path and tells Homey to check the result against the brief, close it, and ask the user only what is their. The file waits until Homey's mod takes it; it is deleted when taken.

## Board line on Homey's prompt
The `prompt` hook, in Homey's session only (`tasks.homeySession`), compares every task's status with `homey-look.json`. If any moved it adds one line to that prompt: `Tasks: <counts of open statuses>. Since last look: <name -> status; ...>` (up to 8), plus "Check each review task and close it; ask the user only what is their to decide" when any is in review. Worker sessions (prompt starts with `HOMEY-WORKER`) get no such line and no style note.

## Seen comments
One append-only file per task, `.claude/homey-watch/seen/<first 16 hex of sha1(path)>.txt`. A comment key is the first 16 hex of sha1 of `<count of identical lines so far>|<line>`, so the same text twice gets two keys. The watcher marks every current comment seen when it nudges or when a message is taken. Comments by the owner or the watcher never wake anyone.

## Steer hook
`scripts/homey_steer.py`, a `PostToolUse` hook on every tool, timeout 5. It exits silently unless env `HOMEY_TASK` is set, which only a watcher-started run has. Otherwise it reads the note, records unseen comments as seen, and for those not written by the owner or the watcher adds context: `New comment on your task, follow it: ...`. Any failure exits 0: it never fails a tool call. A session open in the app has no `HOMEY_TASK`, so it gets new comments only through the message route.

Unknown: how Claude Code orders this hook against other `PostToolUse` hooks.

## Role limits (`roles` in homey.json)
| Key | Meaning |
|---|---|
| `edit` | `none`, `vault` (outside `.claude`), `vault-all`, or `project` (the folder holding `.claude`, except `.claude`; skips the scope guard there) |
| `bash` | `any`, or a list of programs; a list allows commands joined with `&&` or `\|`; redirects, `;` and command substitution are denied |
| `bashSub` | Allowed subcommands per program (`git`, `gh`). Global options (`-C x`, `-c k=v`, `--no-pager`, `-R x`) are parsed first; `git -c` is denied. `git branch` takes no arguments or `--list`; `git remote` only `-v`, `show`, `get-url`; `gh` only `list`, `view`, `diff`, `status`, `checks`; `gh api` only plain reads. `find` may not run commands or write files; `rg` not `--pre`; `obsidian` not `eval` or `dev:` |
| `taskScope`, `noFileWrites` | `taskScope`: Edit tools only on files matching the current task's `files` (the `HOMEY_TASK` note, else the one `doing` task the role owns). `noFileWrites`: `sed -i`, `perl -i`, `tee` and redirects to a file are denied in real commands |
| `editDeny` | Path prefixes (relative to the vault or project) the role may not edit by hand, e.g. `Tasks/` |
| `denyBash` | Regexes checked on the whole command under any `bash` value; `$WRITE_GIT_GH` expands to the shared `writeGitGh` list |
| `agents`, `mcp` | Sub-agent types the role may start; tool name prefixes it may use besides `mcp__ccd_turn__` |
| `rules` | One sentence given at start |
`tasks.mainRole` names the role of the main session (default settings: `lead`; this vault leaves it unset, so Homey stays `main`). Config `noTest` lists test and CI command prefixes; check `noTestRuns` denies them as real commands for limited roles and the main role (a project replaces the list). Checks: `roleGuard`, `pluginLock`, `paneQuestions` (the main role cannot ask in chat), `commitLink` (roles with `commitLink: true`, coder and lead: each real commit or PR-create command, found by segment and token, needs the `Task: <task note name>` line in its own `-m` or `--body` value; `-F`, `--body-file` and a commit with no `-m` are denied; `bash -c '...'` with a quoted command is not caught, the close check and the verifier are the backstop).
