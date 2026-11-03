---
name: homey-decision
description: Record a decision the user made, with its reason.
---

## Who runs it
Agent `capturer`, after the user has decided.

## Steps
1. Copy `System/Templates/Template - decision.md` to the domain folder, named `<title>.md`, with no date in the name. Set `created`, and `up` to its project or the area's map. Set `status`: `decided`, `in progress` or `done` once carried out, `superseded` when replaced (also set `superseded_by`); change it when that happens.
2. Fill Context, Decision, Why in the user's terms. Note anything not yet carried out.
3. Report the path; the main session links it from the daily log.

## Rules
Fill `summary` with one line. Use `[[wikilinks]]`. No H1: Obsidian shows the name as the title. Do not touch `Daily/` or `Home.md`, and do not set goals or change plans: only the user does. Report one line: what you did, the note path, anything unknown. Do not guess; write `unknown`.
