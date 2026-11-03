---
name: homey-setup
description: First setup of a folder as a Homey vault: Obsidian templates, Bases, agents, settings. Use when the user installs Homey, asks to set it up, or the pane says homey.json is missing.
---

## Who runs it
The agent in the folder being set up. Homey in another vault only copies the files with `copy-kit.sh` and gives the prompt.

## Steps
Follow `.claude/homey-plugin/BOOTSTRAP.md`: interview, build the vault, start the agents, options, show the user. If that file is missing, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/homey_setup.py" --help` and ask the user.

## Known limits
| Item | Limit |
|---|---|
| Agent sessions | Need the desktop app's session tool |
| Reading a session's CLI ID | Uses the app's session file; macOS path only |
| Watcher | macOS only for now |
