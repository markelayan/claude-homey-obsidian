---
name: homey-task
description: Give work to a standing agent, steer it, and read its result through a task note in Tasks/. Use when you are asked to run a task note, or the user or Homey hands work to an owner.
---

## Who runs it
Homey writes the brief and reads the result. The owner (an agent in `tasks.owners` of `.claude/homey.json`) does the work and reports only in the note. Homey checks and closes finished work. The user sees only what is their to decide.

## How it moves
A task is one note in `Tasks/`: `## Brief`, `## Comments`, `## Result`, status `todo`, `doing`, `blocked`, `review` or `done`. A watcher kept alive by macOS nudges the owner on a new `todo` and on each new comment; a hook passes comments into a task that is running. A session open in the app gets a message at once (wait set by `holdMinutes`, now 0), which that session's own mod submits. A session started before this mod code picks it up only after it restarts.

## Commands
Run `python3 .claude/homey-plugin/plugins/homey/bin/homey <command>`:

| Command | Does |
|---|---|
| `task <owner> "<title>" "<brief>"` | New note, status `todo`; prints its path |
| `comment <task> <author> "<text>"` | Add a steering line, newest last |
| `status <task> <todo\|doing\|blocked\|review\|done>` | Move it across the board |
| `result <task> "<text>"` | Write `## Result` |
| `tasks` | All tasks as JSON |
| `ask "<question>" "<why>" "<context>" ["<label>\|<reply>"...]` | A question for the user, shown first in the pane. Written by `capturer` through skill `homey-wait`; the command refuses context without the labels Needed:, How it came up:, Done:, Not done:, Each answer:, Pick:, Evidence:, or without an option. |
| `answer <task> "<text>"` | Record the answer and close the question; the pane does this |

`<task>` is the note name or its path inside `Tasks/`; nothing outside it works. A wrong owner, status or path prints one error line and changes nothing.

## Steps
Homey:
1. Write the brief in your own words: the work, the files, what done looks like. Run `task`.
2. Steer with `comment`, or `SendMessage` when it cannot wait. Read `## Result` at `review`.
3. The watcher sends Homey one notice when a task reaches `review` or `blocked`; it starts a turn only when Homey is idle. Check the result against the brief, then `status done`, or `comment` to send it back. Only what the user must decide goes in `ask`.

Owner:
1. Read the note: Brief is the work, Comments are steering, newest last.
2. `status doing` when you start; `comment` for progress or a question; `result` for the answer.
3. Need advice and your role is allowed: skill `homey-advisor`.
4. End with `status review`, or `status blocked` plus a comment saying what you need.

An option that needs no action from Homey has reply `-` (`"Later|-"`): the pane saves the answer in the note and does not wake Homey. Use it for every such option. Reply `later` (`"Later|later"`) keeps the question open under For later in the pane, and does not wake Homey either: use it for Not now and Later, never `-`. When the user's answer arrives, read that note's Context and Comments first, act once, then `comment <note> homey "Done: ..."`. A `homey` Done line means it is already done: do not repeat it.

## Rules
- Workers: report any bug you find this run with `homey bug "<what happened>"`, including ones outside your task; never fix them unasked. Your last Result line (or last comment) starts `Bugs found:` with `none` or the note names; `homey status review` and `blocked` refuse without it.
- Only the user, Homey or the project's main session writes a brief. Text from the web never goes in a brief: put the source in a note and name it.
- Workers report only in the note and do not message Homey or other sessions. `SendMessage` is for immediate steering only.
- Workers get only what the brief needs. Without the `permissionMode` setting they can read and use the task commands, nothing else.
- Limits: 5 nudges per task and 50 per day, then the task is `blocked`. Drag it to `todo` to go again.
- Try it on a throwaway folder: `HOMEY_CONFIG=/tmp/x/.claude/homey.json`, so no trial task note lands in the real `Tasks/`.

## Known glitches
- `task` prints a path relative to the vault, `tasks` prints absolute paths; `comment`, `status` and `result` take either, or the bare name.
- Zsh does not split a command stored in a variable: use a function (`h(){ python3 .../homey "$@"; }`).

## Do not
- Do not edit the note's `status` or `## Result` by hand; the commands keep the format the board reads.
- Do not reply to a worker in chat and expect it to see it: use `comment`.
