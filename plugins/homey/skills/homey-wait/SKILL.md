---
name: homey-wait
description: Write a full question for the user into the pane with homey ask, from facts and links a lead hands you in a task. Use when a task says to put a question for the user.
---

## Who runs it
Agent `capturer`, from a task note. The lead (Homey or the project's main session) hands the question, facts and links; capturer writes the note. A question is never asked in chat.

## Flow
1. Lead writes a task for capturer: the question, why it matters, every fact for each label below, and links to notes.
2. Capturer runs `homey ask "<question>" "<why>" "<context>" "<label>|<reply>"...`. The command refuses a thin one: the context needs each label below with text after it, and at least one option.
3. The user answers in the pane (the Open note button shows the whole note). A reply `-` only saves; `later` keeps it open.
4. The asker reads the note's Context and Comments, acts once, then records it with `homey comment <note> <asker> "Done: ..."`.

## Context labels (all required, each followed by text)
- `Needed:` the decision or input wanted from the user
- `How it came up:` what led to the question
- `Done:` what is already finished
- `Not done:` what waits on the answer
- `Each answer:` what every option does
- `Pick:` the lead's recommended option and why
- `Evidence:` links to notes or sources behind it

## Do not
- Add a fact you were not given. If a label has nothing, say what is missing in the task Result and stop; do not guess.
- Put text with backticks or a dollar sign in double quotes; use single quotes.
- Ask the question in chat, or ask one without a Pick.
- Write a job for the user: a question ends with a question mark and asks for a decision. If the task hands you a command for the user to run, report that in the Result and stop.

## Known glitches
- A refused `ask` prints one line naming the missing labels or the missing option; fix the text and run it again.
