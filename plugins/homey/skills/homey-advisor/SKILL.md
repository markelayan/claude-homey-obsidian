---
name: homey-advisor
description: Two advisors for Homey, a standing junior and a one-call senior, both asked by hand. Use when a design or a question is hard enough for a second view, to act on the answer or go more rounds, to run the senior on a hard question, or when an allowed agent needs advice on a task.
---

## Who runs it
| Level | What | For |
|---|---|---|
| Junior, `advisor.model` | The `advisor` role: a standing session like the rest of the team, in `Homey/Agents.md`, so its past advice stays in its history. It may read the notes a packet names | Designing and advising with Homey, as many rounds as it takes; gap analysis |
| Senior, `advisor.senior` | One `claude -p` call: no tools, no plugins, no session, no memory. Very expensive | Hard questions only. Never automated: Homey runs it by hand, when still needed |

Each ask is logged in `.claude/homey-watch/advice.log`, senior calls with tokens and cost.

## Turn it on
Start the role like any other (`homey-agents`), run `homey agent-add advisor <local_id> <model>`, then `homey advisor <model> [role...]` and `homey advisor senior <model>`. The roles are the agents the user allows to ask. `advisor off` and `advisor senior off` turn them off. Optional settings under `advisor`: `packetChars` (24000), `perDay` (20), `seniorPerDay` (5), `timeoutSeconds` (300).

## Junior
Nothing asks it by itself: `homey ask` does not. Most questions need no advisor; a plain go-ahead or a fact never does. Ask it when the answer is hard to see and a second view would change what you do.

| Who | How |
|---|---|
| Main, on a question that needs a second view | `homey advise <question note>` |
| Main, a follow-up on a question | `homey advise <question note> "<follow-up>"` |
| Main, a design with no question | `homey task advisor "<title>" "<brief>"`; the result is in that note |
| An allowed agent | `homey advise <its task> "<question>"`; a comment wakes it when the advice is in its note |

Packet, in its Brief: Question, Why, Context, Options, the reply form, and the full text of notes named as `[[links]]` or `.md` paths or with `--plan "<note>"`. For an agent's task: its question, Brief and Comments.

The watcher tells Homey at `review`, like any task. The result also goes to `## Advice` in the note that asked: a `By:` line, then Recommendation, Reason, Risk, Missing, Plans. A later answer replaces it; the advisor keeps them all in its history. The pane shows only the recommendation. Then `status <advisor's note> done`.

## Senior
Nothing calls it: not `ask`, not the junior's answer, not the watcher, not an agent. Main only, by hand, when the user asks or when all of this is true:
- The question is hard, and many rounds with the junior have not settled it.
- Homey has read the documentation and plans it depends on.
- Every gap in `Missing` is filled, from a file or a lookup or by `homey ask`, each recorded with `homey comment <note> homey "<fact>"`.

Most questions never reach it. If in doubt, ask the junior again.

Then `homey escalate <note> [--plan <note>]...`. The answer prints to Homey, and goes to `## Senior advice` with its cost.

`escalate` refuses with no junior advice, with `Missing` open and no comment on the note, or when the senior was already asked. `--again` is only for new facts.

Packet: Question, Why, Context, Options, the junior's view, the gaps filled, then full plans. A cut hits the plans first, so check nothing needed is past `packetChars`. Reply: Recommendation, Reason, Risk, Questions, at most 300 words. Its `Questions` lists everything it still needs at once.

## What Homey does with it
| Advice | Do |
|---|---|
| Clear, and the step is reversible | Act on it and close the question with `answer`, so the user never has to look |
| A goal, a plan change, hard to undo | Leave the question for the user, with the advice on it |
| `Recommendation: none` | Fill the gap if a file or lookup can, then ask again; otherwise leave it for the user |

## Rules
- The advisors advise Homey, not the user: the user never has to ask them. They only recommend; Homey decides what to do with the advice.
- Goals, plan changes and anything hard to undo stay with the user, whatever the advice says.
- Text from the web never goes in a packet. Name a vault note that holds the source.
- Do not ask either what a file or a lookup can answer. Never send the senior what the junior can settle, and never run it to test or to see it work.

## Known glitches
- A standing session reads its definition once, so a later change to `advisor.md` does not reach it. The reply form travels in each packet for that reason.
- Junior packets push headings down two levels, so a plan's own `## Result` cannot end the note's sections.

## Do not
- Do not give the senior tools or a session: a standing Fable session cost about $1.63 cold on a question a one call answered for $0.054.
- Do not use Claude Code's built-in advisor for this: it reads the whole conversation on every call, and Claude picks when.
