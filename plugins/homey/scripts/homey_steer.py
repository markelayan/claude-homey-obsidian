#!/usr/bin/env python3
"""PostToolUse hook: pass new task comments into a run the watcher started.
Silent and at once in any session the watcher did not start. Never fails the tool call."""
import json, os, sys

if not os.environ.get("HOMEY_TASK"):
    sys.exit(0)

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    import homey_tasks as ht
    note, seen_path, owner = os.environ["HOMEY_TASK"], Path(os.environ["HOMEY_SEEN"]), os.environ["HOMEY_OWNER"]
    tasks = json.loads(Path(os.environ["HOMEY_CONFIG"]).read_text())["tasks"]
    known = set(tasks["owners"]) | set(tasks["people"])
    lines = ht.comments(Path(note).read_text())
    seen = set(seen_path.read_text().split()) if seen_path.exists() else set()
    fresh, keys = [], []
    for line, key in zip(lines, ht.comment_keys(lines)):
        if key in seen:
            continue
        keys.append(key)
        if ht.author(line, known) not in (owner, "watcher"):
            fresh.append(line)
    if keys:
        seen_path.parent.mkdir(parents=True, exist_ok=True)
        with open(seen_path, "a") as f:
            f.write("".join(k + "\n" for k in keys))
    if fresh:
        text = "New comment on your task, follow it: " + " | ".join(fresh)
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}))


try:
    main()
except Exception:
    sys.exit(0)
