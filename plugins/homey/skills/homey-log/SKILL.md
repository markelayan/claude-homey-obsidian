---
name: homey-log
description: Write the session log and the resume point.
---

## Who runs it
Main session only: one writer keeps `- Next:` last.

## Steps
1. `obsidian vault=<vault> daily:append content="..."`: a `## HHmm topic` heading with the real time from `$(date +%H%M)`, then bullets with `[[links]]`.
2. End with the latest `- Next:` bullet.
3. Write after each meaningful step.
