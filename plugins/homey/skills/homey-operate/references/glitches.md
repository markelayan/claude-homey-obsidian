# Known glitches

Source column: `code` = read in the plugin code; `user/Homey` = recorded by them, not re-run here; `NOTES` = `.claude/homey-plugin/NOTES.md`; `Tools` = `Homey/Homey Tools.md`; `seen` = I saw it while working.

## Hooks and guards
| Glitch | Effect | Do instead | Source |
|---|---|---|---|
| The skill check looks at the command text | A Bash call, including a batch of several commands, that contains `obsidian vault=` is denied until `obsidian-cli` is loaded, even if that text is only data | Load `obsidian-cli` first in the session; load it before any batch | code, seen |
| The same check on Write | A `.md`, `.canvas` or `.base` write outside `.claude` is denied until the matching skill is loaded | Load `obsidian-markdown`, `json-canvas` or `obsidian-bases` first | code, seen |
| The skill check reads only the last 2 MB of the transcript (`transcriptBytes`) | An old load counts as not loaded | Load the skill again | code |
| The danger guard matches words in the command text: `rm`, `rmdir`, `purge`, `truncate`, `drop table`, `git reset --hard`, docker words, trade call names and more | A heredoc, echo or `homey result` that only mentions them is denied; in bypass mode the "ask" becomes a deny | Write such text with the Write tool as a file; use trash, not `rm`; do not work around the guard. The user lifts it for one turn with `.ok`. In a task run the denial names the match and says to reword; Homey gets a notice after `stallDenials` | code, seen |
| A prompt quoting `HOMEY-WORKER` once silenced Homey's own hooks | Style and stop checks skipped in Homey's session | Fixed: only a prompt that starts with `HOMEY-WORKER`, in a session that is not `tasks.homeySession`, makes a worker | User/Homey, code |
| The reply check counts every `?` outside fenced code as a question | A URL or inline code with `?` can trip "more than one question" | Keep one `?` per reply; put URLs in a fence | code |
| `.ok` does not work when the prompt contains `cross-session-message` | A message from another session cannot lift a guard | The user types `.ok` himself | code |
| Hooks and the mod fire twice if registered in both `settings.json` and the plugin | Double output | Register only in the plugin's `hooks.json` | NOTES |

## Shell
| Glitch | Effect | Do instead | Source |
|---|---|---|---|
| zsh does not split a command stored in a variable | `H="python3 .../homey"; $H x` fails: no such file | Use a function: `h(){ python3 .../homey "$@"; }` | User/Homey, seen |
| Backticks inside double quotes run as commands in zsh | A word in backticks inside `daily:append content="..."` is run as a command and vanishes from the text | No backticks in `daily:append` text, or in task briefs and comments | User/Homey |
| `homey` finds its config from the current directory | Run from `/tmp` it prints `no .claude/homey.json found` | `cd` to the vault, or set `HOMEY_CONFIG` | code, seen |
| `bin/` is on PATH only in Claude's Bash tool | Not in the user's own terminal | Use the full path | NOTES |
| Copying the vault for a test fails on `ops/obsedian/config/.XDG/wayland-1` (a socket) | rsync or `cp -R` errors | Exclude `ops` | NOTES, seen |

## Mod and sessions
| Glitch | Effect | Do instead | Source |
|---|---|---|---|
| `$.session.id()` returns a promise | Using it without `await` gives a wrong id | `await $.session.id()` (the mod does) | code |
| A session started before a mod change | Takes watcher messages only after it restarts | Restart it, or `/reload-plugins` | User/Homey |
| Edits to `register.js` or `hooks.json` | Not seen until reload or restart | `/reload-plugins`, then `/homey` | NOTES, user/Homey |
| `claude -p` has no UI | The band and pane never show there | Use a desktop or terminal session | NOTES |
| Worker sessions may lack `anthropic-skills:skill-creator` | Skill-writing tasks follow its method by hand | Say so in the task comment | seen |

## Watcher and tasks
| Glitch | Effect | Do instead | Source |
|---|---|---|---|
| The watcher read `tasks` once at start | An agent added after the watcher started stayed an unknown owner; its task sat in `todo` with one `skip` log line | Fixed 2026-11-02: read on every pass. `vault`, `dir` and `stateDir` still need `homey_watch_install.py install` | Seen in a bootstrap trial |
| A message for an open session waits for that session's 15 s timer | Up to 15 s before it starts | Wait; `watch.log` shows "message taken" | code |
| An unnamed comment line, or one with an unknown name, counts as the user | It wakes the owner | Always write `- name: text` through `comment` | code |
| An owner's own comment never wakes it | A note by the owner to itself is ignored | Comment as `homey` or `mark` | code |
| `answer` accepts any task note and `comment` accepts any author | A wrong note gets closed | Check the name first; `answer` refuses a task already `done` | code |
| Two writers on one note at once (Obsidian and a command) | Whole-file swap: the later write wins. Not tested | Do not edit a task note by hand while it is running | code (inference) |
| `claude agents --json` fails | That pass nudges nobody; `watch.log` says `live list failed` | Check `claude` is on the watcher's PATH (`~/.local/bin` is set) | code |
| An unknown owner or status | One `skip` log line, no block, the task just sits | Fix the owner against `tasks.owners` | code |

## Obsidian
| Glitch | Effect | Do instead | Source |
|---|---|---|---|
| An open graph tab overwrites `saveData` | New graph settings vanish | Close the graph, set `app.internalPlugins.plugins.graph.instance.options`, `saveOptions()`; an open tab takes them only by `view.dataEngine.setOptions({search})`; `setViewState` silently changes nothing | Tools, user/Homey |
| Graph colour groups need `path:/^Folder\//` | `path:Folder` matches any path containing the word | Use the anchored regex | User/Homey |
| `move` needs the destination folder; `create` and `delete` cannot see dotfiles | Command fails | Make the folder first; use the Write tool or `eval` with `trashLocal` | Tools |
| Bases and search skip `.canvas` files | A canvas never appears in results | `files ext=canvas` | Tools |
| A search phrase with a colon must be quoted | Query fails | `search query='"Next:"'` | Tools |
| Stale uses file modified time | A git checkout or sync can hide or fake a stale project | Treat the count as a hint | NOTES |
| `marketplace add` or `install --scope project` rewrote the whole `settings.json` | Noisy git diff | Expect it; content of `hooks` was unchanged | NOTES |
| A notice queued while Homey is busy can arrive after the task is closed | An extra turn with nothing to do | If the note is already done, do nothing | Seen 2026-11-02 |
| One watcher job for the whole Mac | A bootstrap in a second folder took over `com.homey.watch`; the first vault's tasks stopped being watched, with no warning | Fixed: one job per folder. Check `launchctl list \| grep homey` | Seen 2026-11-02 |
| The bootstrap asked for a reload and waited in chat | The user had to interrupt, and the agent does not wake after a typed command | Fixed: `copy-kit.sh` installs the plugin before the session starts; questions go in the pane | Seen in a bootstrap trial |
| `Homey/Agents.md` loads as a nested `AGENTS.md` on a Mac | Its text is added to the session on reading a file under `Homey/`, because names ignore case | Not fixed. Renaming it is the likely way | Seen in a bootstrap trial |
| The app puts text before a start prompt | `HOMEY-WORKER` was not first, so agents were treated as main and made to write the daily log | Fixed: the marker counts at the start of any line, and only main is asked for the log | Seen in a bootstrap trial |
| A task worked on in an open session showed Stuck | Only a watcher run counted as working, so an open session's task read `Stopped without finishing` | Fixed: busy in the app counts, and 60 s grace after the note changes | Seen in a bootstrap trial |
| One session drew a giant circle | The app stretches the drawing to the pane | Fixed: width is at least 7 slots | Seen in a bootstrap trial |
| Workers skipped the note check | Capturer made a dated note with no `created` or `tags`, from this vault's old template, and nothing stopped it | Fixed: a worker is held to the standard for notes it wrote itself; templates brought up to date | Seen 2026-11-02 |

Unknown: whether other glitches exist that nobody has recorded. The skill check is skipped inside a subagent (hook data has an `agent_id`), so it does not block a subagent's own writes.

## Removing a vault from Obsidian
`vault-remove` returns false while that vault's window is open. Close it first: `obsidian vault=<name> eval code="window.close()"`, then remove it from another vault. Seen 2026-11-02.

## CLI delete hung
One `obsidian delete` deleted its note but never returned, for over 3 minutes, in a loop of 6, with the app still answering. Cause unknown; seen once, 2026-11-02. In a loop, wrap it: `timeout 20 obsidian ...`.
