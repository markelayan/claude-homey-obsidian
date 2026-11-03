# Set up this folder with Homey

You are the agent in this folder. Run the setup yourself; the user only answers and looks. The files are in `.claude/homey-plugin/`.

## 1. Interview first
Ask with the question tool, in two rounds, and offer sensible choices. Use what the user already said.

| Round | Ask | Used for |
|---|---|---|
| 1 | The user's own name: agents address them by it. Not the vault's name | Settings |
| 1 | What this vault is for, in a sentence | First project note |
| 1 | Domain folders. Defaults: Work, Code, Research, Content | Folders, settings |
| 1 | Reply style: short (90 words, one table) or normal | Settings |
| 2 | Which agents to start (table below). Default: all | Step 3 |
| 2 | Agent models: as recommended in the table, or customize. If customize, ask per role | Step 3 |
| 2 | Advisor: wanted or not. Two levels advise this session. A junior, a standing agent that keeps its past advice, is asked when a question needs a second view. A senior, one call with no tools, is never automatic: this session runs it by hand on a hard question, after the junior. If wanted, ask the junior's model (recommended `claude-opus-5-5`), the senior's (recommended `claude-fable-5-1`, or none) and which agents may ask it (default none) | Step 4 |
| 2 | Watcher on: wakes agents for tasks, runs in the background, macOS only. Without it agents only work when opened | Step 4 |
| 2 | Bypass for agents: off by default. Agents then may read and use task commands only. Explain the risk before offering it | Step 4 |
| 2 | Demo at the end: a small project, a decision and one task per agent to test the setup, removed when the user says. Default: no | Step 6 |

## 2. Build the vault
1. Run `HOMEY_DOMAINS="<A,B>" HOMEY_STYLE="<short|normal>" sh .claude/homey-plugin/bootstrap.sh . "<name>"`. It installs the plugin for this project, makes the Obsidian templates, Bases, agent definitions and settings, and opens this folder as a vault. It never overwrites a file.
2. If it stops because Obsidian is missing, tell the user. Homey requires Obsidian, because it holds the memory: 1.14 or later, with its command line turned on.
3. If it says Obsidian could not open the vault, ask the user to use Open another vault, Open folder as vault, in Obsidian.
4. Run `H=.claude/homey-plugin/plugins/homey/bin/homey`, then `python3 $H check` and `python3 $H claim-main`, so this session is the main one.
5. Read `.claude/homey-plugin/plugins/homey/skills/homey-operate/references/vault.md`: plain names, one `up` parent, `created`, `tags`, `aliases`. Load skill `homey:obsidian-markdown` before writing any note. Every note you make follows both. Make no placeholder projects: only the one note for the purpose.
6. Write the purpose as a project note named for what it is, in the area it belongs to, type project, status active, `up` set to that area's map, from `System/Templates/Template - project.md`. Link it from the body of that map. Add one line to `Homey/Homey Facts.md`.

## 3. Start the agents
The definitions are in `.claude/agents/`. A definition is not an agent: each one needs its own session. These are the standing roles.

| Role | Recommended model | Job |
|---|---|---|
| `capturer` | `claude-haiku-5-5` | Saves ideas, decisions, facts and projects |
| `scout` | `claude-haiku-5-5` | Read-only lookups in files |
| `researcher` | `claude-haiku-5-5` | Docs and web, read-only |
| `illustrator` | `claude-haiku-5-5` | Canvases and mind maps |
| `librarian` | `claude-haiku-5-5` | Vault checks; reports only |
| `keeper` | `claude-haiku-5-5` | Harness checks; reports only |
| `skillsmith` | `claude-sonnet-5-5` | Writes and tests skills |
| `coder` | `claude-haiku-5-5` | Exact code edits from a Code task; commits with a Task line and links it |
| `ops` | `claude-haiku-5-5` | Reports host state from `homey hosts`; read-only |
| `docs` | `claude-haiku-5-5` | Updates the notes a code task names, adds a changelog line, links the code task |

The folder's main session is the lead (`tasks.mainRole` is `lead` in the default settings): it designs and writes the tasks and never edits code.

Use the model the user chose. For each chosen role, in the Claude desktop app:
1. Start a session with the session tool: fresh context, no worktree, that model, this folder, and the prompt `HOMEY-WORKER. You are <role>. Read .claude/agents/<role>.md: that is your job. Work comes as task notes in Tasks/, through skill homey-task. Reply with one word: ready.`
   The session tool ignores a model above this session's. Check with `get_session`, and if it differs, set it with `set_session_model`.
2. When it has replied, detach it from this session, so its turns do not report here. Tasks tell you when work ends.
3. Run `python3 $H agent-add <role> <its local_ id> <model>`. This fills the settings and `Homey/Agents.md`.

If the session tool refuses (Remote Control, plugin-notice turns) or does not exist, use `python3 $H agent-add <role> --headless <model>` for each role instead of steps 1 to 3: it starts the role with `claude -p` once and records it with no app session. `verifier` stays a new session each time.

## 4. Options
Only what the user chose in the interview.
- Watcher: `python3 .claude/homey-plugin/plugins/homey/scripts/homey_watch_install.py install`
- Advisor: start role `advisor` the way step 3 does, on the junior's model, then `python3 $H advisor <model> [role...]`, and `python3 $H advisor senior <model>` if a senior was chosen
- Bypass: set `tasks.permissionMode` to `bypassPermissions` in `.claude/homey.json`

## 5. Show the user
The plugin loaded when this session started, so nothing needs reloading and the pane is already there. Do not ask the user to run `/homey`. Load skill `homey:homey-operate`. If it is unknown, this session started before the install: only then ask in chat for `/reload-plugins`, because an agent cannot run it, and go on when they reply.

Report in one table: what was made, which agents started, what was not done or not checked. From here on, anything you wait on from the user goes in the pane, with its context, never only in chat. Do not skip this question, also when a demo follows:
`python3 $H ask "Does the graph look right?" "Setup is finished" "Home, the maps, and each note under its parent" "Looks right|-" "Something is wrong|the graph looks wrong"`

Make no sample, demo or test notes or tasks here: only step 6 does, if the user chose it. Nothing else is automatic.

## 6. Demo
Only if the user chose it. They already said yes in the interview, so start without asking again. Agents never get more than this.
1. Make a note `Demo project`, type project, status active, in the first domain, `up` set to that domain's map, tag `demo`. Make a note `Demo decision`, type decision, `up` set to `Demo project`, tag `demo`, from the templates.
2. For each started agent run `python3 $H task <role> "Demo: say your job" "Read only. Read .claude/agents/<role>.md and write your job in one line as the result."` Do not message the agents.
3. With the watcher on, the agent gets its task within a minute. Do not poll the note or the log and do not sleep: end your turn, a notice wakes you. Without the watcher, say tasks wait until the agent is opened, then go to item 5 of this list.
4. A notice reaches you when a task ends. Check the result against the brief, then run `python3 $H status "<task>" done`. The user does not close them. If the user writes and no notice has come, that is a finding: read `.claude/homey-watch/watch.log` and report it, and do not work around it.
5. Tell the user in one table where to look and what they should see: `/homey` shows the demo questions and sessions, the Tasks board shows the tasks done, the Board shows `Demo project`, the graph shows both notes under the domain map.
6. Ask in the pane, with what was made as the context: `python3 $H ask "Remove the demo?" "The demo is finished" "<what was made>" "Remove it|remove the demo" "Keep it|-"`. On `remove the demo`, delete the two notes and the demo tasks with `obsidian vault=<vault> delete path=<path>`, never `permanent`, then write the Done comment on the question.
7. Close with a log entry: a `## HHmm topic` heading with the real time, bullets, then a last `- Next:` line saying what is left. Task notes do not trigger the log check, so do this yourself.
