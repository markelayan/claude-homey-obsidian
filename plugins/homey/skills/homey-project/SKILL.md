---
name: homey-project
description: Create or update a project note so it shows on the Board.
---

## Who runs it
Agent `capturer`, unless the user is deciding something now.

## Steps
1. Copy `System/Templates/Template - project.md` to its domain folder (`Homey/` for this system).
2. Set `created`, and `up` to the area's map. Set `status`: idea, active, paused or done. Keep `summary` under 35 characters so Board cards show it.
3. `## Goal`: The user's words only; otherwise "the user sets this".
4. `## Tasks` stays the last section.

## Rules
Fill `summary` with one line. Use `[[wikilinks]]`. No H1: Obsidian shows the name as the title. Do not touch `Daily/` or `Home.md`, and do not set goals or change plans: only the user does. Report one line: what you did, the note path, anything unknown. Do not guess; write `unknown`.
