# Changelog

## 0.4.3

- The danger guard judges what would run and where a delete lands, not words in text. Agents can clean up temp folders, `.work/`, build caches and named project files. Words in notes and searches no longer trip it.
- The guard now catches deletes in backticks, `sh -c`, `eval`, `ssh` and `docker exec`, and by full path. Data, the home folder, `.git`, secrets, whole source folders, SQL deletes and order calls stay refused. Commands were judged in a trial, not run.
- Answers pressed close together in the pane reach the session as one prompt, each question and answer set apart. An answer that lifts a guard still goes alone.
- A bug note tells the capturer to write it up with `homey-bug`, not to verify it.
- The "deletes go to Trash" rule is gone: it was never the user's.

## 0.4.2

- Workers run the first command and judge by its result. Before this, a worker told by its own session history that it had no Bash kept refusing tasks, even with Bash back.
- `homey task` accepts the main role as owner, and the watcher leaves those notes alone.
- The note checks read the whole frontmatter, so tags or a summary past the first 400 bytes are no longer reported missing.

## 0.4.1

An icon, a tagline and a signature.

## 0.4.0

First package prepared for sharing. Not yet tried by anyone but its author.

- Lead and workers: the lead decides, workers do the reading, edits and notes, and a new checker reviews them.
- Status note and run plan, so any session can take over.
- Bugs flow, task links, host checks and deploy steps.
- One-line install from the repository.
- Rules steer with a reminder. Hard blocks only for deletes, risky commands and answering for the user. Deleting inside a temp folder is allowed.
