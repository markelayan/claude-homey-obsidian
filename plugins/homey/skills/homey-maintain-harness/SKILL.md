---
name: homey-maintain-harness
description: Check Claude Code changes, settings drift, hook health, skill list size and token use.
---

## Who runs it
Agent `keeper`.

## Steps
1. Read the changelog at code.claude.com/docs/en/changelog.md for versions since the last check in `Homey/Homey Tools.md`.
2. Compare `.claude/settings.json` and `~/.claude/settings.json` with `Homey/Homey Tools.md`. Key names only, never secret values.
3. Count skills listed at startup. Read token use per agent from `~/.claude/projects/<this project>rain/*/subagents/*.jsonl`, numbers only.
4. Report one table: item, change, effect here. Change nothing: The user decides.
