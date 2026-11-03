---
name: homey-make-skill
description: Create or fix a skill and its workflow, try it on a real case, and record its details and glitches.
---

## Who runs it
Agent `skillsmith`.

## Steps
1. Check `.claude/homey-plugin/plugins/homey/skills/` first and extend a skill rather than duplicating it.
2. Check current docs at code.claude.com/docs/en/skills.md when a feature matters; do not rely on memory.
3. Load `anthropic-skills:skill-creator` and follow it to write the skill; skip its test step. Do not rewrite its method here. Add this vault's format: a short `description`, `## Who runs it`, `## Steps`. Every description loads for every agent.
   For a plugin, load `cowork-plugin-management:create-cowork-plugin` or `cowork-plugin-customizer`, and check it fits Claude Code: its description says it needs Cowork mode. If it does not fit, stop and report.
4. Try the workflow on the real case in the brief. If it changes real data or leaves this Mac, ask through the main session about that step and carry on with the rest.
5. Add what the run taught: `## Known glitches` and `## Do not`, each with what to do instead.
6. Report one table: step, result, proof. Say what was not tried. Agents that hit a glitch report it; add it here.
