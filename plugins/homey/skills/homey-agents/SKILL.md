---
name: homey-agents
description: Start, resume, record and reset the standing agents.
---

## Who runs it
Main session.

## Steps
1. Standing roles are persisted app sessions, listed with IDs in `Homey/Agents.md`. Give work as a task note, flow `homey-task`. Use `SendMessage` to the `local_` ID only for immediate steering.
2. No subagents for these roles. A start through the app session tool needs a message typed in the desktop app, not Remote Control. When the tool refuses (Remote Control, plugin-notice turns), start the role with no app session: `homey agent-add <role> --headless <model>`. It runs `claude -p` once from the project root, records the owner and the `Homey/Agents.md` row, and refuses a role already recorded. The watcher wakes it with `claude -p --resume`; the pane shows it as free.
3. Each brief starts with `HOMEY-WORKER`, so hooks skip the style note and stop checks. Guards still apply.
4. `verifier` is a new session each time, so it stays independent.
5. Results land in the task note. Workers do not message Homey. A result from a direct message: save it to the vault in the same turn.
