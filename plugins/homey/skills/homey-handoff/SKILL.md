---
name: homey-handoff
description: Move Homey's main role to a new session, cheaply. Use when the user wants to continue in a fresh session, or when this one has grown long and costly.
---

## Who runs it
A script and a one-call Haiku. No session spends a turn on it when the user presses `Hand off to new session` in the pane's Now tab.

## Steps
The press runs `homey handoff --session <id>`: Haiku reads that session's transcript, with no tools, writes `Homey/Session handoff.md`, frees the main role and logs `- Next: read [[Session handoff]]`. Then the app's new-session page opens with the prompt filled in: `Read Homey/Session handoff.md and continue from its Next.` The user checks the folder is this vault and presses Enter.

If a session is asked to hand off in words, it runs `homey handoff` the same way, says the prompt above, and stops. Do not read the note.

## What happens next
The new session's Resume hook gives it the rules and `- Next:`. Its first prompt that is not a worker's takes the main role, so notices and pane answers go there. If the user writes here first, this session takes it back.

Settings under `handoff`: `model` (`claude-haiku-5-5`), `chars` (40000, newest kept).

What Haiku gets: the last compaction summary, the user's words since, and replies cut to 500 characters. Tool output, skills, notices and hidden text stay out. It answers in at most 250 words.

## Known glitches
- The app starts a session only on a message typed in the desktop app, so the user's Enter is the one step left. The link (`claude://code/new?q=`) has no documented folder for a local session.
- A note is one model's summary of the chat only: tool output is left out. Lasting corrections belong in `Homey/Homey Rules.md` too.
- Notices wait while the role is free.
- The next handoff replaces the note.
