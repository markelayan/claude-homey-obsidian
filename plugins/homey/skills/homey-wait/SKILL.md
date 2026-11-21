---
name: homey-wait
description: Write a full question for the user into the pane with homey ask, from facts and links a lead hands you in a task. Use when a task says to put a question for the user.
---

## Who runs it
Agent `capturer`, from a task note. The lead (Homey or the project's main session) hands the question, facts and links; capturer writes the note. A question is never asked in chat.

## Only what is the user's
Search first: the project's notes, then the main brain vault. Never put in the pane a question about the user's method, a study, or anything already written down: the lead or Homey answers it, with the source in the note.
The pane is only for a goal or plan change, a deploy, order path, a config approval, a flat statement, and what nothing written can settle.

## Flow
1. Lead writes a task for capturer: the question and why it matters, with what it already has.
2. **Get the details.** Read the brief and every note and file it names. Pull out what was decided, the numbers, the paths and the user's exact words.
3. **Check it is not already there.** Search `Tasks/`, open and done, the project notes, rules, facts and decisions for the same question.
   - Same question open: do not make a new one. Add what is new to that note with `homey comment`.
   - Already answered: do not ask. Put the answer, its source and the related notes in the task, and tell the lead with `homey result`, then `status review`.
   - Nothing needed from the lead, only information to keep: add it to the note, `homey result`, then `status done`. No reply.
4. **Verify.** Check each fact against its source: note, file and line, or read time. What cannot be checked goes in as `unknown`.
5. **Draft it** in clear formatting, below, and run `homey ask "<question>" "<why>" "<context>" "<label>|<reply>"... --urgency urgent|normal|low`. The command refuses a thin one: the context needs each label below with text after it, and at least one option.
   `--urgency`: urgent when work or money waits on it now, low when nothing does, else normal. A question nobody has touched wakes the asker when idle after 1, 4 or 24 hours, `tasks.refreshHours`. The asker answers it if it now can, updates it, or leaves it.
6. The user answers in the pane (the Open note button shows the whole note). A reply `-` only saves; `later` keeps it open.
7. The asker reads the note's Context and Comments, acts once, then records it with `homey comment <note> <asker> "Done: ..."`.

## Clear formatting
- Plain words for someone who has not seen the work. One short sentence for each point.
- Question first, one decision, ending with a question mark. Options of a few words.
- Numbers with their unit and date. The user's words in quotes. `[[links]]` to every related note.
- A table when comparing two or more things. Say what each option does, not how it was coded.
- Never put words in the user's mouth: a reading is labelled as the lead's.

## Context labels (all required, each followed by text)
- `Needed:` the decision or input wanted from the user
- `How it came up:` what led to the question
- `Done:` what is already finished
- `Not done:` what waits on the answer
- `Each answer:` what every option does
- `Pick:` the lead's recommended option and why
- `Evidence:` links to notes or sources behind it

## Do not
- Add a fact you did not verify. If a label still has nothing after searching, write what is missing in the task Result and stop; do not guess.
- Put text with backticks or a dollar sign in double quotes; use single quotes.
- Ask the question in chat, or ask one without a Pick.
- Write a job for the user: a question ends with a question mark and asks for a decision. If the task hands you a command for the user to run, report that in the Result and stop.

## Known glitches
- A refused `ask` prints one line naming the missing labels or the missing option; fix the text and run it again.
