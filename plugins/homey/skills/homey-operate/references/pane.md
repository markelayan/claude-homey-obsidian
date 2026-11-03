# The Homey pane and band

Source: `hooks/register.js` (the mod), `bin/homey data`, `.claude/homey.json` keys `band` and `panes`. Opened with `/homey` or the Board button in the band. Needs the desktop app; `claude -p` cannot show it.

## Band (above the prompt)
One dim line from `band`: `Next: <latest - Next:> · Inbox n · Stale n · Tasks n`. Tasks = unchecked `- [ ]` lines. A problem replaces it with a red line. `/homey now` prints the same line, `/homey find <term>` searches, with no model turn.

## Tabs
Set by `panes` in `homey.json`; hotkeys 1 to 4. The tab label shows a count when the pane is rich.

| Tab | Type | Count | Shows |
|---|---|---|---|
| Now | tasks | Questions open + stuck tasks | The sections below |
| Projects | board | Projects | Projects grouped by status (idea, active, paused, done); red dot and `Stale` for an active project not touched for `staleDays` (14); Open button |
| Decisions | decisions | Decisions | The newest 8 (`limits.decisions`) grouped by date, Today first; Open button |
| Bugs | table | Open bugs | Table `Homey/Bugs.md`, heading `Open` (columns Bug, State, Reporter, Task); a missing file shows empty; a closed bug leaves the tab | Open the task note |
| Issues | table | Rows | A table set under `panes` in `homey.json`, grouped by the last column (its source note), one bullet per issue; Open button for the source |

## Now tab, top to bottom
| Section | Means | The user does |
|---|---|---|
| `● Watcher is off: tasks will not start` | `status.json` is older than 3 ticks + 30 s | Turn it on: `files.md` |
| Waiting on you | Open questions from `homey ask` (owner mark, not put off). Red dot, question, why, one button per option, Other, Open note (the full note with its Context); the For later rows have Open note too | Press an option, or Other and type |
| Stuck | Tasks whose state is needs: `blocked` (shows the last comment), `doing` with no run (Stopped without finishing), a run quiet for `stallMinutes`, no session picked, or watcher off | Details; comment; Run again; Open note or session |
| `✓ Nothing needs you` | The two sections above are empty | Nothing |
| Sessions | One circle per owner: green working, cyan open in the app but idle, grey free; legend counts | Nothing |
| Working now | Tasks whose state is working (a live run: "Working for N min; last activity M min ago", plus guard denials) | Nothing |
| Waiting to start | Queued ("Starting in a few seconds", "After its current task") or held ("Open in the app; message left for it") | Nothing |
| For later | Questions put off with reply `later`; short rows with Details | Open one to answer it |
| `Homey is checking N finished` | Tasks in `review`: Homey closes them | Nothing |
| Homey's next step | The latest `- Next:` | Read it |
| Counts line | Inbox, Stale, To-dos | Nothing |
| New task | Closed by default. For: owner, Task: one line, which becomes both title (cut to 70 characters) and brief | Rarely |

`done` tasks are never listed. A task row has Details: result, last three comments, a Comment box (writes `- mark: ...`), Run again when blocked, Open note, Open session.

## Reply kinds and what wakes Homey
| Reply | Source | Saved in the note | Wakes Homey |
|---|---|---|---|
| `-` | Option written `"Label\|-"` | Yes: comment, Result, status `done` | No |
| `later` | Option `"Later\|later"` | `later: <date>` only; question stays open under For later | No |
| Any other text | Option reply, or typed in Other | Yes, as `answer` does | Yes if the pane is open in Homey's own session (`tasks.homeySession`): it submits the reply as the user's message plus "This answers the question in <note>. Read its Context first, act once, then record what you did in that note." In another session only a toast: "Saved. Homey sees it on its next message." |
| A typed answer | Other, or the box shown when a question has no options | Yes | Same, prefixed `Answer to "<question>": ` |

A comment from the pane (`mark`) on an agent task wakes the owner through the watcher, not Homey.

## Refresh timing
| Event | Refresh |
|---|---|
| Session start, `/homey`, any pane action | At once |
| Pane open | Every 15 s |
| Pane closed | Every 4th 15 s pass (about 60 s) |
| Messages for this session (`take`) | Every 15 s, pane open or not |
| Watcher state | The watcher writes it every 10 s; the pane reads the file |

A change in `register.js` shows only after `/reload-plugins` or a restart (`sessions.md`). Terminal surface or no SVG support: a plain text list instead of the rich pane.

Unknown: how the rows look in the terminal surface; not run.

## Who gets an answer
The session whose pane was pressed gets the answer as a prompt, and becomes main. Nothing is left waiting for a role that is free or held elsewhere.

## Advisor
Homey asks the advisor by hand, with `homey advise`, on the few questions that need it; the user has nothing to press. Until it answers the row says `Advisor is thinking`. Then only `Junior recommends: ...` shows on the row; the rest is in the note, for Homey. `Senior recommends: ...` shows under it. The advisor's task shows on the board like any other. Skill `homey-advisor`.
