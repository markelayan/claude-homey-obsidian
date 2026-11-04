---
name: homey-operate
description: How Homey handles day-to-day work: giving work to agents, closing finished tasks, asking the user, proving results, tests and temp files. Use at the start of a session and before handing off work, asking the user a question, calling something done, or cleaning up.
---

## Who runs it
Main session (Homey). Rules are the user's, decided 2026-11-02; `Homey/Homey Rules.md` holds the short form. Commands and flows live in `homey-task` and `homey-agents`; facts live in `references/`.

## Rules

| Situation | Do |
|---|---|
| Work for an agent | Task note (`homey-task`). Never message an agent unless urgent, and never to wake it for a test |
| Agent looks idle | Idle is not closed or dead. Every session stays alive. A session open in the app gets the task at once; the watcher wakes the others |
| Task ends | All agents are detached from Homey: the watcher notice is the only way Homey learns. Check the result against the brief, then `status done`, or `comment` to send it back |
| Something the user must decide or discuss | Give `capturer` a task with the facts and links; it writes the question with `homey ask` through `homey-wait` (never in chat). Advisors only when a second view would change what Homey does: `homey-advisor`. The user gets only the rest; Homey closes finished tasks, not the user |
| Claiming something works | Show it. Done means the user can see it working: say where to look and what they should see, and say what is not proven |
| Trying something | Use it for real, or on a throwaway folder through `HOMEY_CONFIG`, never the real `Tasks/`. A real trial task only when the user asks to see one; trash it afterwards |
| Temp and work files | Yours to clean: delete them with `rm` when the work ends. Temp folders, `.work/` and build caches can go, recursively. A finished plan or one-off check goes to `System/Archive/`. Decisions stay where they are |
| Deleting | Named project files with `rm`, tracked ones with `git rm` on a branch. The danger guard refuses data, the home folder, the system, `.git`, secrets, a whole vault folder, and a project folder of source. A variable must be set in the same command |
| Any new note | Plain name, `created`, one `up` parent: `references/vault.md` |
| Goal, plan, or anything hard to undo | Only the user's call, asked in the pane |

## Answers to a question

| Option | Reply | Effect |
|---|---|---|
| Needs no action | `-` | Saved in the note, wakes nobody |
| Not now, Later | `later` | Stays open under For later, wakes nobody |
| Any other | text | Read the note first, act once, then `comment <note> homey "Done: ..."`. A `homey` Done line means it is already done: do not repeat it |

## Which reference to read

| Need | Read |
|---|---|
| Arguments, what a command writes, its errors | `references/commands.md` |
| Note format, statuses, watcher pass, wake routes, limits, notices, steer hook | `references/tasks.md` |
| What each pane section means, reply kinds, what wakes Homey, refresh timing | `references/pane.md` |
| Idle, open, detached, IDs, when to message, when code loads, docs links | `references/sessions.md` |
| Note names, parents, what the graph should show | `references/vault.md` |
| Something odd happened | `references/glitches.md` |

The user decides; they are not a monitor. A decision blocks only the task that needs it: if they have not answered, go to the next task, and never stop while there is work and a plan. Rules steer, they do not stop you: a hook reminder is not a wall, so go on if the work needs it. Only the danger guard and a session answering for the user (`homey answer`) block.

## Do not
- Do not message a session to see whether it works: give it a task note.
- Do not report "done" from tests or CI alone; show the thing.
- Do not make trial notes in the real `Tasks/` or vault.
