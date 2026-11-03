# Sessions

Source: `.claude/homey.json` (`tasks`), `scripts/homey_watch.py`, `bin/homey`, `hooks/register.js`, `Homey/Agents.md`. Decisions about idle and detached sessions are the user's, 2026-11-02.

## States
| State | Meaning | How the code sees it | What a task does |
|---|---|---|---|
| Working | Doing a turn | A run the watcher started is alive, or the app reports the session `busy` | Waits: an owner never gets two runs |
| Open (idle) | Session is in the app, waiting for input. Still alive | Listed by `claude agents --json` with a non-busy status | Gets a message left in `inbox/`; its own mod submits it (`tasks.md`) |
| Free (idle, not open) | Alive as a saved session, not in the app | Not in that list | The watcher wakes it with `claude -p --resume <sessionId>` |
| Closed or dead | Not defined by the code. The app may archive a session; the code only checks that the session id is listed or can be resumed | Unknown | Unknown: a resume of a missing id would end the run with an error and the watcher blocks the task ("run failed") |

Idle is not closed. Every session stays alive when idle; never treat a quiet session as gone.

## Detached agents
All agents (capturer, scout, researcher, illustrator, librarian, keeper, skillsmith, advisor) run detached from Homey: no parent session waits on them, and they do not message Homey. Homey learns a task ended only from the watcher's notice (`tasks.md`). Workers report in the note.

## IDs and where they live
| What | Where | Used for |
|---|---|---|
| CLI session id (`sessionId`) per owner | `.claude/homey.json` `tasks.owners.<name>.sessionId` | `claude -p --resume`, the live-session lookup, inbox file names |
| App session id (`local_...`) per owner | `tasks.owners.<name>.appSession` and `Homey/Agents.md` | `SendMessage` target; the Open session link `claude://claude.ai/epitaxy/<id>` (`tasks.appLink`) |
| Model per owner | `tasks.owners.<name>.model` | `--model` on a resume |
| Homey's own session id | `tasks.homeySession` | Where notices go; whether the pane wakes Homey |
| Run record | `.claude/homey-watch/state.json` `runs`, output `run-<owner>.json` | The pane's working state |

Session ids are identifiers, not secrets, but do not paste them into briefs or notes that leave this Mac.

## Direct messages
| Case | Allowed |
|---|---|
| Immediate steering that cannot wait for a comment | Yes: `SendMessage` to the `local_` id |
| Waking an agent, testing it, or asking for status | No: write a task note or a comment |
| Worker to Homey or to another session | No: workers report only in the note |
| A message from a session shows as `<cross-session-message ...>` | The `.ok` approval does not count when that text is present |

## Plugin code loads late
A session picks up mod code (`hooks/register.js`) and hook definitions only at plugin reload (`/reload-plugins`) or restart. A session started before a mod change takes watcher messages only after it restarts. Python scripts (`bin/homey`, `scripts/`) are read each time they run, so they apply at once; the watcher process reads `tasks` config once at start, so restart it after editing (`files.md`).

## Docs used
| Topic | Link |
|---|---|
| Messaging between sessions | https://code.claude.com/docs/en/cross-session-messaging.md |
| Mod API (`$.session.id()`, `$.prompt.submit`, `$.ui`) | https://code.claude.com/docs/en/plugins/mods/api.md |
| Testing mods | https://code.claude.com/docs/en/plugins/mods/test.md |

Not re-read for this file: the three pages. Claims about them above come from the code and earlier notes (`NOTES.md`, `glitches.md`).
