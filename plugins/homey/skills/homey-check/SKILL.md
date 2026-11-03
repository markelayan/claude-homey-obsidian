---
name: homey-check
description: Check delivered work against its requirement and confirm its link. Use when you are asked to verify a task's output.
---

## Who runs it
Agent `verifier`, always a fresh session, read-only.

## Steps
1. Read the task Brief's Requirement and the delivered output (diff, files, command output). Work it out yourself.
2. One verdict per requirement: confirmed, refuted or could not check, each with a file and line or the command you ran.
3. Report only gaps that affect correctness. Skip style.
4. Confirm the task's `commit` or `pr` link exists and holds the change (`git show`, the PR view command).
5. For a task of kind `code`: list the commit's changed files (`git show --stat <commit>`) and compare them with the task's `files` field (globs allowed). Any changed file outside it fails the check; name it.
6. Say what you could not check.

## Do not
- Take the asker's opinion or conclusion as evidence.
- Edit anything, or run a test suite.
- List problems just to have some: no gap, say so.
- If the run clearly hit a bug and reported `Bugs found: none`, fail the check and name the bug.
