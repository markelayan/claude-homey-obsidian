# Files that matter

Paths are from the vault root. Plugin root = the installed plugin, `${CLAUDE_PLUGIN_ROOT}` (called `<plugin>`).

## Plugin
| Path | Job |
|---|---|
| `<plugin>/.claude-plugin/plugin.json` | Plugin `homey`, version 0.2.0 |
| `<plugin>/bin/homey` | The CLI: vault reads and task writes (`commands.md`). On PATH only in Claude's Bash tool while the plugin is enabled |
| `<plugin>/scripts/homey_tasks.py` | Task note read and write code shared by the CLI, watcher and steer hook |
| `<plugin>/scripts/homey_watch.py` | The watcher: `tick` (one pass) or `run` (loop) |
| `<plugin>/scripts/homey_watch_install.py` | `install`, `uninstall`, `status` for the launchd job |
| `<plugin>/scripts/homey_steer.py` | `PostToolUse` hook that passes new comments into a running task |
| `<plugin>/scripts/homey_hooks.py` | The other hooks: resume, prompt, checkpoint, logcheck, canvas, guard. Settings from `hooks` in `homey.json` |
| `<plugin>/hooks/hooks.json` | Registers the mod (`./register.js`) and the command hooks |
| `<plugin>/hooks/register.js` | The mod: band, pane, `/homey` command, message taking (`pane.md`) |
| `<plugin>/skills/` | All `homey-*` skills and the four Obsidian skills (`homey:` prefix; bare names still resolve) |

## Hooks registered in `hooks.json`
| Event | Matcher | Command | Timeout |
|---|---|---|---|
| SessionStart | startup, resume, clear, compact | `homey_hooks.py resume` | 10 |
| UserPromptSubmit | any | `homey_hooks.py prompt` | 10 |
| PreCompact | any | `homey_hooks.py checkpoint` | 10 |
| Stop | any | `homey_hooks.py logcheck` | 10 |
| PostToolUse | Write\|Edit | `homey_hooks.py canvas` | 10 |
| PostToolUse | any | `homey_steer.py` | 5 |
| PreToolUse | Bash\|Write\|Edit\|NotebookEdit\|Agent\|Task\|mcp__.* | `homey_hooks.py guard` | 10 |

## `.claude/homey.json`
| Key | Used by | Holds |
|---|---|---|
| `vault`, `dailyDir`, `inboxDir`, `staleDays` | CLI, hooks | Where notes live, stale age (14) |
| `domains`, `skipDirs`, `types`, `nextPattern`, `dailyGlob`, `statuses`, `limits` | CLI | What the CLI reads and its caps; `statuses` are project statuses |
| `band`, `panes` | Mod via `bin/homey data` | Band items and tabs |
| `hooks` | `homey_hooks.py` | `checks` (which run), `style`, `words`, `askFirst`, `tradeToolPattern`, `homeFile`, `homeWritePattern`, `editTools`, `noteSkills`, `cliSkill`, `outsideOk`, `projectDomains`, `summaryDomains`, `hooksSkipDirs`, `templatesDir`, `rulesFile`, `dailyTemplate`, `nextPrefix`, `obsidianVault`, `activeStatus`, `limits`. A missing key gives the error line `Homey hooks: homey.json missing: ...` |
| `tasks` | CLI, watcher, hooks, mod | `dir`, `statuses`, `owners`, `people`, `homeySession`, `nudgesPerDay`, `nudgesPerTask`, `holdMinutes`, `maxRuns`, `tickSeconds`, `runTimeoutSeconds`, `stallMinutes`, `stallStopMinutes`, `stallRestarts`, `stallDenials`, `claudeBin`, `stateDir`, `prompt` (template with `{path}`, `{reason}`, `{owner}`, `{homey}`), `appLink` |

## `.claude/homey-watch/` (git-ignored)
| File | Job |
|---|---|
| `state.json` | Per task nudge counts and last status; runs in progress; day and day count |
| `status.json` | Written each pass: time and live sessions. The pane reads it |
| `watch.log` | One line per nudge, end, block, message, notice, skip, failure |
| `launchd.log` | Output of the launchd job |
| `run-<owner>.json` | Output of that owner's last `claude -p` run |
| `seen/` | Seen-comment keys per task (`tasks.md`) |
| `inbox/`, `inbox/taken/` | Messages waiting for, and just taken by, an open session |
| `homey-look.json` | Task name to status as of Homey's last prompt. Written by the `prompt` hook in Homey's session only |

## Vault places
| Path | Job |
|---|---|
| `Tasks/` | One note per task and per question |
| `System/Bases/Tasks.base` | Obsidian board: views Board (kanban by status), Agents, Current |
| `System/Archive/` | Finished plans and one-off checks. Decisions stay in `Homey/` |
| `Homey/Agents.md` | Session ids by role |
| `Homey/Homey Rules.md` | The user's rules, read at every start |
| `Homey/Homey Tools.md` | CLI gotchas and tool notes |

## Watcher on and off
| Want | Command (from the vault) |
|---|---|
| See it | `homey watcher status` (`active pid N` or `not running`) |
| Turn on, or restart after changing `vault`, `dir` or `stateDir`; other `tasks` edits apply on the next pass | `... homey_watch_install.py install` |
| Turn off | `... homey_watch_install.py uninstall` |
| One pass by hand | `HOMEY_CONFIG=<config> python3 .../homey_watch.py tick` |

Each folder has its own launchd job, label `com.homey.watch.<folder>-<hash>`, file `~/Library/LaunchAgents/<label>.plist`, the only file outside the vault. It runs `homey_watch.py run` with `RunAtLoad` and `KeepAlive`, restart throttle 10 s, working folder the vault, and env `HOMEY_CONFIG`, `HOME`, `PATH`. `install` writes it with the python that ran the installer and replaces a running job.

## Tests
`PLUGIN/tests` exists and is not run: tests and CI are not used here, production use is the proof.

## Settings added for sharing

| Key | Job |
|---|---|
| `user.name`, `user.id` | Who the assistant works for; `id` owns questions and signs comments |
| `requires.obsidian` | Lowest Obsidian version `homey check` accepts. Obsidian is required: it holds the memory |
| `tasks.permissionMode` | Unset means `default`: workers may read and use task commands only. `bypassPermissions` is opt-in |
| `tasks.allowedTools` | Replaces that default list when the mode is not bypass |

## Setup

| Path | Job |
|---|---|
| `scripts/homey_setup.py` | Makes the vault; never overwrites |
| `setup/homey.default.json` | Default settings, no personal values |
| `setup/vault/` | Obsidian templates, Bases, index, starter notes |
| `setup/agents/` | Agent definitions copied into `.claude/agents/` |
| `hooks.startSkill` | Skill the main session is told to load at start |
