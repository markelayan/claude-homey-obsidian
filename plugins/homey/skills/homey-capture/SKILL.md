---
name: homey-capture
description: Save a new idea, to-do or later topic the user raises mid-chat, without interrupting the chat. Run by the capturer agent.
---

## Who runs it
Agent `capturer`, in the background. The main session sends the user's words and 1 to 3 lines of context, then keeps talking.

## Steps
Frontmatter is `type`, `summary`, `created`, `up`, between `---` lines. Vault rules: `homey-operate`, `references/vault.md`.
1. Read the words given. Keep the user's meaning; add no ideas of your own.
2. To-do for a known project (`Grep` `type: project`): append `- [ ] <task>` under `## Tasks`, which is last in the note.
3. Anything else: create `Inbox/<short title>.md` inside the vault folder your agent file or nudge names, with `type: capture`, `summary`, `created`, `up`, then `## Said` (the user's words) and `## Context`.
4. If asked to gather facts, read only what the brief names and add them under `## Facts`, each with its source.

## Rules
Fill `summary` with one line. Use `[[wikilinks]]`. No H1: Obsidian shows the name as the title. Do not touch `Daily/` or `Home.md`, and do not set goals or change plans: only the user does. Report one line: what you did, the note path, anything unknown. Do not guess; write `unknown`.
