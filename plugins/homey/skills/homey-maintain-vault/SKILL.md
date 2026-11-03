---
name: homey-maintain-vault
description: Check the vault for missing summaries, broken links, orphans, stale projects and old resume points.
---

## Who runs it
Agent `librarian`.

## Steps
1. Run `obsidian vault=<vault> unresolved` and `orphans`, `base:query path=System/Bases/Projects.base view=Stale format=md`.
2. List typed notes without `summary`, and Inbox notes.
3. Report one table: item, problem, suggested action. Move and delete nothing: The user decides.
