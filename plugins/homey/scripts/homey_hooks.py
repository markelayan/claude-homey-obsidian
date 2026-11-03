#!/usr/bin/env python3
"""Homey's Claude Code hooks: homey_hooks.py <resume|prompt|checkpoint|logcheck|canvas|guard>.

Same behavior as the former .claude/hooks/homey.py. All settings come from the `hooks`
key of .claude/homey.json ($HOMEY_CONFIG overrides; the project dir is $CLAUDE_PROJECT_DIR).
A missing required key gives one error line (stderr, exit 1) instead of a guess.
Vault files are read and written directly so every hook works with Obsidian closed.
"""
import json
import os
import fnmatch
import re
import shlex
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

REQUIRED = ["checks", "style", "words", "askFirst", "tradeToolPattern", "homeFile", "homeWritePattern",
            "editTools", "noteSkills", "cliSkill", "outsideOk", "projectDomains", "summaryDomains",
            "hooksSkipDirs", "templatesDir", "rulesFile", "dailyTemplate", "nextPrefix", "obsidianVault",
            "activeStatus", "limits"]
LIMITS = ["replyWords", "tableAfterWords", "maxQuestions", "transcriptBytes", "headBytes", "projectHeadChars", "changedNames"]
CHECKS = ["resume", "style", "words", "capture", "ctx", "checkpoint", "logcheck", "projectCheck", "summaryCheck",
          "screenshotCheck", "replyCheck", "noteCheck", "canvas", "dangerGuard", "homeGuard", "scopeGuard", "skillCheck", "agentGuard", "logTimeCheck", "roleGuard", "pluginLock", "statusCheck", "planCheck", "paneQuestions", "commitLink", "taskScope", "noTestRuns", "bug", "approvalGuard"]
TOP = ["vault", "dailyDir", "inboxDir", "staleDays"]


class Bad(Exception):
    pass


class NotSetUp(Bad):
    pass


CONFIG_FILE = None


def load_config():
    global CONFIG_FILE
    env = os.environ.get("HOMEY_CONFIG")
    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    path = Path(env) if env else (Path(proj) / ".claude" / "homey.json" if proj else None)
    if path is None:
        d = Path.cwd().resolve()
        path = next((p / ".claude" / "homey.json" for p in [d, *d.parents] if (p / ".claude" / "homey.json").is_file()), None)
    if path is None or not path.is_file():
        raise NotSetUp("no .claude/homey.json found")
    CONFIG_FILE = path
    try:
        cfg = json.loads(path.read_text())
    except ValueError as e:
        raise Bad(f"homey.json is not valid JSON: {str(e)[:80]}")
    if not isinstance(cfg, dict) or not isinstance(cfg.get("hooks"), dict):
        raise Bad("homey.json has no `hooks` object")
    miss = [k for k in TOP if k not in cfg] + ["hooks." + k for k in REQUIRED if k not in cfg["hooks"]]
    if miss:
        raise Bad("homey.json missing: " + ", ".join(miss))
    h = cfg["hooks"]
    lim = h["limits"] if isinstance(h["limits"], dict) else {}
    badl = [k for k in LIMITS if not isinstance(lim.get(k), int) or lim[k] < 1]
    if badl:
        raise Bad("homey.json hooks.limits missing or not positive ints: " + ", ".join(badl))
    unknown = [c for c in h["checks"] if c not in CHECKS] if isinstance(h["checks"], list) else ["checks is not a list"]
    if unknown:
        raise Bad("homey.json hooks.checks unknown: " + ", ".join(unknown))
    try:
        for p in h["askFirst"] + [h["tradeToolPattern"]]:
            re.compile(p)
        re.compile(h["homeWritePattern"].replace("{home}", "x").replace("{stem}", "x"))
    except (re.error, TypeError, AttributeError) as e:
        raise Bad(f"homey.json hooks pattern invalid: {str(e)[:60]}")
    root = path.parent.parent
    return cfg, (root / cfg["vault"]).resolve()


def setup():
    global CFG, H, LIM, VAULT, DAILY, INBOX, RULES, DAILY_TEMPLATE, HOME, WORDS, USER, STYLE
    CFG, VAULT = load_config()
    H = CFG["hooks"]
    LIM = H["limits"]
    DAILY = VAULT / CFG["dailyDir"]
    INBOX = VAULT / CFG["inboxDir"]
    RULES = VAULT / H["rulesFile"]
    DAILY_TEMPLATE = VAULT / H["dailyTemplate"]
    HOME = H["homeFile"]
    USER = (CFG.get("user") or {}).get("name") or "The user"
    WORDS = {k: v.replace("{user}", USER) for k, v in H["words"].items()}
    STYLE = H["style"].replace("{user}", USER)


def on(check):
    return check in H["checks"]


def emit(event, context):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}))


def block(reason):
    print(json.dumps({"decision": "block", "reason": reason}))


def today_note():
    return DAILY / f"{datetime.now():%Y-%m-%d}.md"


def daily_notes():
    return sorted(DAILY.glob("*.md"), reverse=True)


def last_line(path):
    lines = [l for l in path.read_text().splitlines() if l.strip()]
    return lines[-1] if lines else ""


def latest_next():
    for note in daily_notes():
        found = [l for l in note.read_text().splitlines() if l.startswith(H["nextPrefix"])]
        if found:
            return note.stem, found[-1]
    return None, f"{H['nextPrefix']} none yet"


def append_daily(text):
    note = today_note()
    if not note.exists():
        note.write_text(DAILY_TEMPLATE.read_text())
    body = note.read_text()
    with note.open("a") as f:
        f.write(("" if body.endswith("\n") else "\n") + text + "\n")


def vault_files():
    skip = set(H["hooksSkipDirs"])
    for root, dirs, files in os.walk(VAULT):
        rel = Path(root).relative_to(VAULT)
        dirs[:] = [d for d in dirs if not d.startswith(".") and not (rel == Path(".") and d in skip)]
        for name in files:
            if name.endswith((".md", ".canvas", ".base")):
                yield Path(root) / name


def stale_projects():
    cutoff = time.time() - CFG["staleDays"] * 86400
    count = 0
    ptype = CFG.get("types", {}).get("project", "project")
    for path in vault_files():
        if path.suffix != ".md" or path.stat().st_mtime >= cutoff:
            continue
        head = path.read_text().split("---")[1] if path.read_text().startswith("---") else ""
        if re.search(rf"^type:\s*{re.escape(ptype)}\b", head, re.M) and re.search(rf"^status:\s*{re.escape(H['activeStatus'])}\b", head, re.M):
            count += 1
    return count


def inbox_count():
    return sum(1 for p in INBOX.glob("*") if not p.name.startswith(".")) if INBOX.exists() else 0


def turn_stamp(session):
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session or "none")
    return Path(tempfile.gettempdir()) / f"homey-turn-{safe}"


def tail_lines(transcript):
    with open(transcript, "rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - LIM["transcriptBytes"]))
        return f.read().decode("utf-8", "ignore").splitlines()


def context_tokens(transcript):
    """Tokens in the last main-thread request, or None if unknown or just compacted."""
    if not transcript or not Path(transcript).exists():
        return None
    for line in reversed(tail_lines(transcript)):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("subtype") == "compact_boundary":
            return None
        usage = (entry.get("message") or {}).get("usage") if entry.get("type") == "assistant" else None
        if usage and not entry.get("isSidechain"):
            total = sum(usage.get(k, 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
            if total:
                return total
    return None


def status_text():
    """The status note for a take-over: updated time and body, cut to statusChars. Empty if none."""
    f = H.get("statusFile")
    path = VAULT / f if f else None
    if not path or not path.is_file():
        return ""
    text = path.read_text("utf-8", "ignore")
    m = re.match(r"---\n(.*?)\n---\n?", text, re.S)
    updated = re.search(r"^updated:\s*(.+)$", m.group(1), re.M).group(1).strip().strip("\"'") if m and re.search(r"^updated:\s*(.+)$", m.group(1), re.M) else "unknown"
    body = text[m.end():] if m else text
    return f"Status, updated {updated}:\n" + body.strip()[:LIM.get("statusChars", 4000)]


def resume(data):
    if not on("resume"):
        return
    if "/plugins/cache/" in str(Path(__file__).resolve()):
        subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "homey_watch_install.py"), "refresh"], capture_output=True, timeout=15, env=dict(os.environ, HOMEY_CONFIG=str(CONFIG_FILE)))
    if not subprocess.run(["pgrep", "-x", "Obsidian"], capture_output=True).stdout:
        subprocess.run(["open", "-g", f"obsidian://open?vault={H['obsidianVault']}"], capture_output=True)
    role = role_of(data)
    main_like = is_main_role(data, role)
    if not main_like and isinstance(role_info(role), dict):
        return emit("SessionStart", f"{role_info(role).get('rules', '')} You may {role_limits(role)}{' Form: ' + FORM_RULE if role_info(role).get('bash', 'any') != 'any' else ''} {BUG_RULE} {PLAN_WORKER if on('planCheck') else ''} {STEER_RULE}".strip())
    source, nxt = latest_next()
    status = status_text()
    mine = role_info(role) if role not in (None, "main") else None
    extra = [f"Your role is {role}. {mine.get('rules', '')} You may {role_limits(role)}", ""] if isinstance(mine, dict) else []
    lines = ([status, ""] if status else []) + extra + [
        "Homey rules:",
        re.sub(r"\A---\n.*?\n---\n", "", RULES.read_text(), flags=re.S).strip(),
        "",
        f"Resume point ({source or 'no log yet'}): {nxt}",
        f"Inbox: {inbox_count()}. Stale projects: {stale_projects()}.",
        BUG_RULE,
        STEER_RULE,
    ]
    why = plan_problem() if on("planCheck") else None
    if why:
        lines.append(f"{why}. Before other work, run {PLAN_FIX}.")
    tasks = CFG.get("tasks") or {}
    main = tasks.get("homeySession") in ("", None, data.get("session_id"))
    if main and H.get("startSkill"):
        lines.append(f"Load skill {H['startSkill']} with the Skill tool before other work.")
    emit("SessionStart", "\n".join(lines))


def bug_note(text, data=None):
    """`.bug <text>`: the same creation as `homey bug`, reporter the user, no tokens spent."""
    if not text:
        return "No bug noted: add text after .bug"
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import homey_tasks as ht
    if not CFG.get("bugsFile"):
        return "No bug noted: bugsFile is not set in homey.json"
    path = ht.add_bug(VAULT / CFG["tasks"]["dir"], VAULT / CFG["bugsFile"], text, (CFG.get("user") or {}).get("id") or "user")
    return f"Bug noted: {Path(path).stem}. capturer writes it up; the verifier checks it after."


def capture(text):
    if not text:
        return "Nothing captured: add text after .cap"
    title = re.sub(r"[^\w\s-]", "", " ".join(text.split()[:6])).strip() or "capture"
    INBOX.mkdir(exist_ok=True)
    path = INBOX / f"{title}.md"
    n = 2
    while path.exists():
        path, n = INBOX / f"{title} {n}.md", n + 1
    home = Path(HOME).stem
    path.write_text(f'---\ntype: capture\nsummary: ""\ncreated: {datetime.now():%Y-%m-%d}\nup: "[[{home}]]"\ntags:\n  - capture\n---\n{text}\n')
    return f"Captured: {CFG['inboxDir']}/{path.name}"


def main_session():
    return (CFG.get("tasks") or {}).get("homeySession")


def claim_if_free(session, text):
    """After a handoff the main role is free: the first prompt that is not a worker's takes it."""
    if (CFG.get("tasks") or {}).get("homeySession") != "" or not session or re.search(r"(?m)^HOMEY-WORKER", text):
        return
    path = CONFIG_FILE
    full = json.loads(path.read_text())
    full["tasks"]["homeySession"] = session
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(full, indent=2) + "\n")
    os.replace(tmp, path)
    CFG["tasks"]["homeySession"] = session


def worker_stamp(session):
    return turn_stamp(session).with_suffix(".worker")


def approval_stamp(session):
    return turn_stamp(session).with_suffix(".ok")


def transcript_entries(transcript, across_compaction=False):
    """Parsed transcript lines after the last compaction, oldest first."""
    if not transcript or not Path(transcript).exists():
        return []
    entries = []
    for line in tail_lines(transcript):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("subtype") == "compact_boundary" and not across_compaction:
            entries = []
        elif isinstance(entry, dict):
            entries.append(entry)
    return entries


def tool_calls(entries):
    for entry in entries:
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        for block in (entry.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                yield entry, block


def loaded_skills(transcript):
    """Skill names loaded so far, without a plugin prefix (`homey:obsidian-cli` counts as `obsidian-cli`)."""
    names = {b["input"].get("skill") for _, b in tool_calls(transcript_entries(transcript, across_compaction=True)) if b.get("name") == "Skill"}
    return {n.split(":")[-1] for n in names if isinstance(n, str)}


def skills_in_whole_transcript(transcript):
    """The tail can miss an early load in a long session, so read every Skill call in the file."""
    entries = []
    if transcript and Path(transcript).exists():
        with open(transcript, "rb") as f:
            for line in f:
                if b'"Skill"' in line:
                    try:
                        entries.append(json.loads(line))
                    except ValueError:
                        pass
    names = {b["input"].get("skill") for _, b in tool_calls(entries) if b.get("name") == "Skill"}
    return {n.split(":")[-1] for n in names if isinstance(n, str)}


def needs_cli_skill(command):
    free = H.get("cliNoSkill", [])
    return any(sub not in free for sub in re.findall(r"""\bobsidian\s+vault=(?:"[^"]*"|'[^']*'|\S+)\s+(\S+)""", command))


def screenshot_since(transcript, since):
    for entry, block in tool_calls(transcript_entries(transcript)):
        stamp = entry.get("timestamp", "")
        when = datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp() if stamp else 0
        if when >= since and "dev:screenshot" in str((block.get("input") or {}).get("command", "")):
            return True
    return False


def prompt(data):
    turn_stamp(data.get("session_id")).write_text(str(time.time()))
    text = (data.get("prompt") or "").strip()
    claim_if_free(data.get("session_id"), text)
    if re.search(r"(?m)^HOMEY-WORKER", text) and data.get("session_id") != main_session():
        worker_stamp(data.get("session_id")).write_text("1")
    approved = re.match(r"(?i)(\.ok\b|approved\b|i approve\b)", text) and "cross-session-message" not in text
    stamp = approval_stamp(data.get("session_id"))
    stamp.write_text("1") if approved else stamp.unlink(missing_ok=True)
    tokens = context_tokens(data.get("transcript_path"))
    match = re.match(r"\.([a-z]+)\b\s*(.*)", (data.get("prompt") or "").strip(), re.S)
    word = match.group(1) if match else None
    if word == "cap" and on("capture"):
        return block(capture(match.group(2).strip()))
    if word == "bug" and on("bug"):
        return block(bug_note(match.group(2).strip(), data))
    if word == "ctx" and on("ctx"):
        return block(f"Context: {tokens:,} tokens" if tokens else "Context: not measured yet")
    notes = ([STYLE] if on("style") else []) + ([WORDS[word]] if word in WORDS and on("words") else [])
    try:
        line = task_line(data.get("session_id"))
    except Exception:
        line = ""
    if line:
        notes.append(line)
    if notes and not worker_stamp(data.get("session_id")).exists():
        emit("UserPromptSubmit", " ".join(notes))


def task_line(session):
    """One line for Homey's next prompt: what moved on the board since Homey last looked."""
    tasks = CFG.get("tasks") or {}
    if session != tasks.get("homeySession"):
        return ""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import homey_tasks as ht
    now = {t["name"]: t for t in ht.all_tasks(VAULT / tasks["dir"]) if not t.get("bad")}
    look = VAULT / tasks["stateDir"] / "homey-look.json"
    try:
        before = json.loads(look.read_text())
    except (OSError, ValueError):
        before = {}
    state = {name: t["status"] for name, t in now.items()}
    moved = [f"{name} -> {state[name]}" for name in sorted(state) if before.get(name) != state[name]]
    look.parent.mkdir(parents=True, exist_ok=True)
    look.write_text(json.dumps(state))
    if not moved:
        return ""
    counts = {}
    for st in state.values():
        counts[st] = counts.get(st, 0) + 1
    order = [st for st in tasks["statuses"] if st != "done" and counts.get(st)]
    summary = ", ".join(f"{counts[st]} {st}" for st in order) or "none open"
    check = f" Check each review task and close it; ask {USER} only what is theirs to decide." if counts.get("review") else ""
    return f"Tasks: {summary}. Since last look: " + "; ".join(moved[:8]) + check


def checkpoint(data):
    if not on("checkpoint"):
        return
    _, nxt = latest_next()
    append_daily(f"## {datetime.now():%H%M} Compaction ({data.get('trigger', 'auto')})\n{nxt}")


def last_reply(transcript):
    """Newest main-thread assistant text."""
    for entry in reversed(transcript_entries(transcript)):
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        content = (entry.get("message") or {}).get("content") or []
        text = " ".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
        if text.strip():
            return text
    return ""


def reply_problem(text):
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    words = len(re.findall(r"\w[\w'%.-]*", text))
    limit = LIM["replyWords"]
    if words > limit:
        return f"Your reply is {words} words; the limit is {limit}. Move detail to a vault note, then send a shorter reply with one table or diagram and a link."
    if prose.count("?") > LIM["maxQuestions"]:
        return "Your reply asks more than one question. Keep only the one that matters most."
    if words > LIM["tableAfterWords"] and "|---" not in text and "```" not in text:
        return "Your reply has no table or diagram. Resend it with one."
    return None


def domains_without_project():
    missing = []
    for name in H["projectDomains"]:
        heads = [n.read_text("utf-8", "ignore")[:LIM["projectHeadChars"]] for n in (VAULT / name).glob("**/*.md")]
        heads = [h for h in heads if "type: map" not in h]
        if heads and not any("type: project" in h for h in heads):
            missing.append(name)
    return missing


def note_head(path):
    """The whole frontmatter, however long, else the first headBytes."""
    text = path.read_text("utf-8", "ignore")
    end = text.find("\n---", 3) if text.startswith("---") else -1
    return text[:end] if end > 0 else text[:LIM["headBytes"]]


def notes_without_summary(changed):
    found = []
    domains = tuple(H["summaryDomains"])
    for path in changed:
        if path.suffix == ".md" and path.parts[len(VAULT.parts)] in domains:
            head = note_head(path)
            if head.startswith("---") and "\ntype: " in head and "type: daily" not in head and "summary:" not in head:
                found.append(path.name)
    return found


def badly_placed_notes(changed):
    """Notes in the graph must have a plain name and one parent: see the homey-operate vault rules."""
    found = []
    domains = tuple(H["summaryDomains"]) + (CFG["inboxDir"],)
    for path in changed:
        if path.suffix != ".md" or path.parts[len(VAULT.parts)] not in domains:
            continue
        head = note_head(path)
        if re.match(r"\d{4}-\d{2}-\d{2}", path.stem):
            found.append(f"{path.name} has a date in its name")
        elif not re.search(r"^up:\s*.*\[\[", head, re.M):
            found.append(f"{path.name} has no `up` parent link")
        elif not re.search(r"^tags:", head, re.M):
            found.append(f"{path.name} has no `tags`")
    return found


def status_stamps():
    """(next_checked, bugs_checked) times from the status note's front matter, 0 when missing."""
    path = VAULT / (H.get("statusFile") or "")
    out = []
    for key in ("next_checked", "bugs_checked"):
        try:
            m = re.search(rf"^{key}:\s*\"?([0-9-]+ [0-9:]+)", path.read_text("utf-8", "ignore"), re.M)
            out.append(time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")) if m else 0)
        except (OSError, ValueError):
            out.append(0)
    return out


PLAN_FIX = "`homey state Plan '<goal, done when, steps done, steps left, step now>'`, so any session can resume from it (`none` when there is no work)"
PLAN_WORKER = "A task of more than a few steps: first run `homey comment <note> <you> 'Plan: <steps left, step now>'` and add a new one when it changes, so a new run can resume."


def plan_problem():
    """Why the main session's run plan needs writing, or None."""
    if not H.get("statusFile"):
        return None
    try:
        m = re.search(r"^plan_checked:\s*\"?([0-9-]+ [0-9:]+)", (VAULT / H["statusFile"]).read_text("utf-8", "ignore"), re.M)
        age = (time.time() - time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"))) / 60 if m else None
    except (OSError, ValueError):
        age = None
    if age is None:
        return "You have no run plan"
    return f"Your run plan is {int(age)} minutes old" if age >= LIM.get("planStaleMinutes", 60) else None


def plan_nudge(data):
    """One reminder during a long run when the plan is missing or stale, at most every planNudgeMinutes."""
    if not on("planCheck"):
        return None
    f = turn_stamp(data.get("session_id")).with_suffix(".plan")
    try:
        count, last = json.loads(f.read_text())
    except (OSError, ValueError):
        count, last = 0, 0
    count += 1
    text = None
    if time.time() - last >= LIM.get("planNudgeMinutes", 20) * 60:
        task = os.environ.get("HOMEY_TASK")
        if task:
            try:
                planned = re.search(r"^- \S+: Plan:", Path(task).read_text("utf-8", "ignore"), re.M)
            except OSError:
                planned = True
            if count >= LIM.get("planWorkerTools", 10) and not planned:
                text = "This run is long and its task note has no plan. " + PLAN_WORKER
        elif count >= LIM.get("planFirstTools", 3) and is_main_role(data, role_of(data)):
            why = plan_problem()
            if why:
                text = f"{why}. Run {PLAN_FIX}."
    f.write_text(json.dumps([count, time.time() if text else last]))
    return text


def status_stale(data, since):
    """The status commands still owed this turn ([] when none): a turn that used a work tool must run `homey state Next` and `homey state 'Bugs found'`."""
    f = H.get("statusFile")
    if not f:
        return []
    def after(entry):
        stamp = entry.get("timestamp", "")
        return (datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp() if stamp else 0) >= since
    used = {b.get("name") for e, b in tool_calls(transcript_entries(data.get("transcript_path"))) if after(e) and b.get("name") in ("Bash", "Write", "Edit", "NotebookEdit", "Agent", "Task")}
    if not used:
        return []
    nxt, bugs = status_stamps()
    owed = []
    if nxt <= since:
        owed.append("`homey state Next '...'`")
    if bugs <= since:
        owed.append("`homey state 'Bugs found' '...'` (none, or the note names from `homey bug`)")
    why = plan_problem() if on("planCheck") else None
    if why:
        owed.append(f"{PLAN_FIX} ({why.lower()})")
    return owed


def logcheck(data):
    stamp = turn_stamp(data.get("session_id"))
    if data.get("stop_hook_active") or not stamp.exists():
        return
    since = float(stamp.read_text())
    if worker_stamp(data.get("session_id")).exists():
        own = {Path(b["input"].get("file_path", "")).resolve() for _, b in tool_calls(transcript_entries(data.get("transcript_path"))) if b.get("name") in H["editTools"]}
        wrong = badly_placed_notes([p for p in vault_files() if p.stat().st_mtime > since and p.resolve() in own]) if on("noteCheck") else []
        if wrong:
            block("; ".join(wrong[:LIM["changedNames"]]) + ". Fix it: plain name, `created`, `up` set to one parent note, `tags`. Skill obsidian-markdown has the format.")
        return
    tasks = VAULT / (CFG.get("tasks") or {}).get("dir", "Tasks")
    changed = [p for p in vault_files() if p.stat().st_mtime > since and tasks not in p.parents]
    note = today_note()
    prefix = H["nextPrefix"]
    is_main = not main_session() or data.get("session_id") == main_session()
    log_missing = is_main and on("logcheck") and changed and not (note.exists() and note.stat().st_mtime > since and last_line(note).startswith(prefix))
    owed = status_stale(data, since) if is_main and on("statusCheck") else []
    status_missing = bool(owed)
    if log_missing or status_missing:
        parts = []
        if log_missing:
            names = ", ".join(sorted(p.name for p in changed)[:LIM["changedNames"]])
            parts.append(f"Vault changed this turn ({names}) but the daily log has no closing `{prefix}`. Append it with daily:append: a `## HHmm topic` heading with the real time, bullets, then `{prefix} ...` as its own last line.")
        if status_missing:
            parts.append(f"The status note {H.get('statusFile')} still needs, this turn: " + " and ".join(owed) + ". Update any other section that changed too (Goal, Open task, Done this session, Decided, Waiting on user, Hosts) so another session can take over.")
        return block(" ".join(parts) + " Then finish.")
    if approval_stamp(data.get("session_id")).exists():
        return
    missing = domains_without_project() if on("projectCheck") else []
    if changed and missing:
        return block(f"{', '.join(missing)} has notes but no project on the Board. Create one from `Template - project`, then finish.")
    unsummarized = notes_without_summary(changed) if on("summaryCheck") else []
    if unsummarized:
        return block(f"{', '.join(unsummarized[:LIM['changedNames']])} has no `summary` property. Add one line: Home and agents read it instead of the note.")
    misplaced = badly_placed_notes(changed) if on("noteCheck") else []
    if misplaced:
        return block("; ".join(misplaced[:LIM["changedNames"]]) + ". Fix it: plain name, `created`, `up` set to one parent note, `tags`. Skill obsidian-markdown has the format.")
    shown = [p for p in changed if p.name == HOME or p.suffix == ".canvas"]
    if on("screenshotCheck") and shown and not screenshot_since(data.get("transcript_path"), since):
        return block(f"{shown[0].name} changed but you did not look at it. Open it, take `obsidian vault={H['obsidianVault']} dev:screenshot`, read the image, then finish.")
    problem = reply_problem(last_reply(data.get("transcript_path"))) if on("replyCheck") else None
    if problem:
        block(problem)


def canvas_problems(path):
    try:
        doc = json.loads(path.read_text())
    except ValueError as e:
        return [f"invalid JSON: {e}"]
    nodes, edges = doc.get("nodes", []), doc.get("edges", [])
    ids = [i.get("id") for i in nodes + edges]
    node_ids = {n.get("id") for n in nodes}
    problems = [f"duplicate id {i}" for i in sorted({i for i in ids if ids.count(i) > 1}, key=str)]
    for edge in edges:
        problems += [f"edge {edge.get('id')} points to missing node {edge.get(k)}" for k in ("fromNode", "toNode") if edge.get(k) not in node_ids]
    return problems


def canvas(data):
    if not on("canvas"):
        return
    path = Path((data.get("tool_input") or {}).get("file_path", ""))
    if path.suffix != ".canvas" or not path.exists():
        return
    problems = canvas_problems(path)
    if problems:
        return block(f"{path.name}: " + "; ".join(problems))
    in_templates = VAULT / H["templatesDir"] in path.parents
    if not in_templates and path.stem not in (VAULT / HOME).read_text():
        emit("PostToolUse", f"List {path.name} under ## Canvases in {HOME}.")


def decide(decision, reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}))


def home_write_regex():
    return H["homeWritePattern"].replace("{home}", re.escape(HOME)).replace("{stem}", re.escape(Path(HOME).stem))


STEER_RULE = "Delete your own temp files with rm when the work ends; the danger guard allows rm inside a temp folder. Rules steer you; if the work needs it, go on. Ask the user only for a goal or scope change, spending money, protected-path work or deleting data; a decision blocks only its own task: if they have not answered, take the reversible path or go to the next task, and never stop while there is work and a plan."
BUG_RULE = 'Report any bug you find this run with `homey bug "<what happened>"`, including ones outside your task; never fix them unasked.'
FORM_RULE = "join commands only with && or |; no redirects, ; or command substitution, and use single quotes around text with backticks or a dollar sign."
EDIT_WORDS = {"none": "no files", "vault": "vault notes outside .claude", "vault-all": "any file in the vault", "project": "any project file outside .claude"}


def role_info(role):
    return (CFG.get("roles") or {}).get(role)


def role_of(data):
    """The worker role of this session, "main", or None. A role missing from `roles` has no limits."""
    if data.get("agent_type"):
        return data["agent_type"]
    tasks = CFG.get("tasks") or {}
    note = os.environ.get("HOMEY_TASK")
    if note:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import homey_tasks as ht
            return ht.read_task(note).get("owner") or None
        except Exception:
            pass
    session = data.get("session_id")
    for name, cfg in (tasks.get("owners") or {}).items():
        if session and cfg.get("sessionId") == session:
            return name
    if not tasks.get("homeySession") or session == tasks.get("homeySession"):
        return tasks.get("mainRole") or "main"
    return None


def is_main_role(data, role):
    """True for the main session: no role, "main", or the role that tasks.mainRole gives it."""
    main_role = (CFG.get("tasks") or {}).get("mainRole")
    if role in (None, "main"):
        return True
    return bool(main_role) and role == main_role and not data.get("agent_type") and not os.environ.get("HOMEY_TASK")


def project_root():
    return CONFIG_FILE.parent.parent.resolve()


def expand_deny(patterns):
    out = []
    for p in patterns:
        out += CFG.get("writeGitGh", []) if p == "$WRITE_GIT_GH" else [p]
    return out


def role_limits(role):
    r = role_info(role)
    bash = r.get("bash", "any")
    run = "any command" if bash == "any" else "only " + ", ".join(bash) + " commands"
    return f"edit {EDIT_WORDS.get(r.get('edit'), r.get('edit'))}, and run {run}."


def scan_command(command, joined=False):
    """Tokens of a single simple command, or None if it has operators, newlines or substitution outside quotes.
    With joined, `&&` and `|` outside quotes are kept as tokens for scan_parts."""
    quote = None
    i = 0
    while i < len(command):
        c = command[i]
        if quote == "'":
            quote = None if c == "'" else quote
        elif c == "\\":
            i += 1
        elif quote == '"':
            if c == '"':
                quote = None
            elif c == "`" or command.startswith("$(", i):
                return None
        elif c in "'\"":
            quote = c
        elif c in "\n\r`" or command.startswith("$(", i):
            return None
        i += 1
    if quote:
        return None
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        lex.commenters = ""
        tokens = list(lex)
    except ValueError:
        return None
    if not tokens or any(t and all(ch in "();<>|&" for ch in t) and not (joined and t in ("&&", "|")) for t in tokens):
        return None
    return tokens


def scan_parts(command):
    """The simple commands of `a && b | c`, or None if any other operator or substitution is outside quotes."""
    tokens = scan_command(command, joined=True)
    if tokens is None:
        return None
    parts, cur = [], []
    for t in tokens:
        if t in ("&&", "|"):
            parts.append(cur)
            cur = []
        else:
            cur.append(t)
    parts.append(cur)
    return None if any(not p for p in parts) else parts


def command_program(tokens):
    if tokens[0] == "python3" and len(tokens) > 1 and Path(tokens[1]).resolve() == Path(__file__).resolve().parents[1] / "bin" / "homey":
        return "homey"
    return tokens[0]


GIT_ARG_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix", "--config-env"}
GH_ARG_OPTS = {"-R", "--repo", "--hostname"}
GH_READ = ("list", "view", "diff", "status", "checks")


def skip_globals(args, arg_opts):
    """(global options, rest) of a git or gh argument list, so options cannot hide the subcommand."""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in arg_opts else 1
    return args[:i], args[i:]


def git_sub_problem(args, allowed):
    """Why this git command is outside the allowed read-only subcommands, or None."""
    glob, rest = skip_globals(args, GIT_ARG_OPTS)
    if any(g in ("-c", "--config-env") or g.startswith(("-c", "--exec-path")) for g in glob):
        return "git with -c or --exec-path"
    if not rest:
        return None
    sub, a = rest[0], rest[1:]
    if sub not in allowed:
        return f"git {sub}"
    if any(x.startswith(("--output", "--upload-pack", "--receive-pack", "--exec")) for x in a):
        return f"git {sub} with that option"
    if sub == "branch" and a and not (a[0] == "--list" and all(not x.startswith("-") for x in a[1:])):
        return "git branch with arguments (only no arguments, or --list)"
    if sub == "remote" and a and a != ["-v"] and a[0] not in ("show", "get-url"):
        return "git remote that changes remotes"
    return None


def gh_sub_problem(args, allowed):
    """Why this gh command is not a read-only one, or None."""
    _, rest = skip_globals(args, GH_ARG_OPTS)
    if not rest:
        return None
    sub, a = rest[0], rest[1:]
    if sub not in allowed:
        return f"gh {sub}"
    if sub == "api":
        if any(x in ("-X", "--method", "-f", "-F", "--field", "--raw-field", "--input") or x.startswith(("-X", "--method=", "--field=", "--raw-field=", "--input=")) for x in a):
            return "gh api that is not a plain read"
        return None
    if a and a[0] not in GH_READ:
        return f"gh {sub} {a[0]}"
    return None


def segment_problem(tokens, r):
    """Why one simple command breaks the role's subcommand and option rules, or None."""
    prog, args = command_program(tokens), tokens[1:]
    if prog == "homey":
        return None
    sub = r.get("bashSub") or {}
    if prog == "git" and "git" in sub:
        return git_sub_problem(args, sub["git"])
    if prog == "gh" and "gh" in sub:
        return gh_sub_problem(args, sub["gh"])
    if prog == "find" and any(t in ("-exec", "-execdir", "-ok", "-okdir", "-delete", "-fls") or t.startswith("-fprint") for t in args):
        return "find with -exec, -delete or -fprint"
    if prog == "rg" and any(t.startswith("--pre") for t in args):
        return "rg --pre"
    if prog == "obsidian" and any(t == "eval" or t.startswith("dev:") for t in args if "=" not in t):
        return "obsidian eval or dev: commands"
    return None


def write_problem(command):
    """Why a real command writes a file outside the Edit tools (sed -i, perl -i, tee, a redirect), or None."""
    for words in shell_words(command):
        if "\x00>" in words:
            k = words.index("\x00>")
            if (words[k + 1] if k + 1 < len(words) else "") not in ("/dev/null", "/dev/stderr"):
                return "a redirect to a file"
        prog, args = command_core([w for w in words if w != "\x00>"])
        if prog == "tee":
            return "tee"
        if prog == "sed" and any(a.startswith("--in-place") or re.match(r"^-[A-Za-z]*i", a) for a in args):
            return "sed -i"
        if prog == "perl" and any(re.match(r"^-[A-Za-z]*i", a) for a in args):
            return "perl -i"
    return None


def homey_call(words):
    """(subcommand, arguments) of a real homey command (homey x, or python3 .../bin/homey x), else None."""
    prog, args = command_core([w for w in words if w != "\x00>"])
    if prog == "homey":
        return (args[0], args[1:]) if args else ("", [])
    if prog.startswith("python") and args and args[0].endswith("/bin/homey"):
        return (args[1], args[2:]) if len(args) > 1 else ("", [])
    return None


def homey_sub(words):
    """The homey subcommand of a real command, else None."""
    call = homey_call(words)
    return call[0] if call else None


def note_owner(ref):
    """Owner of the Tasks/ note that ref (name or path) points to, or None."""
    folder = VAULT / (CFG.get("tasks") or {}).get("dir", "Tasks")
    name = Path(ref).name
    p = folder / (name if name.endswith(".md") else name + ".md")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import homey_tasks as ht
    try:
        return ht.props(p.read_text()).get("owner")
    except OSError:
        return None


def approval_problem(tool, tool_input):
    """No Claude session answers a question for the user: only the pane does."""
    if tool == "Bash":
        for words in shell_words(tool_input.get("command", "")):
            call = homey_call(words)
            if call and call[0] == "answer":
                return "deny", f"Approval guard: only the pane answers {USER}'s questions. {USER} can lift this with `.ok`."
    return None


def no_test_problem(command):
    """The test or CI command a real command segment starts with (config noTest prefixes), or None."""
    prefixes = [x.split() for x in CFG.get("noTest") or []]
    for words in shell_words(command):
        prog, args = command_core([w for w in words if w != "\x00>"])
        tokens = [prog] + args
        for pre in prefixes:
            if tokens[:len(pre)] == pre:
                return " ".join(pre)
    return None


def current_task_files(role):
    """(task note stem, file patterns) of this role's current task, or (None, None) when none is open."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import homey_tasks as ht
    note = os.environ.get("HOMEY_TASK")
    notes = [Path(note)] if note else []
    if not notes:
        folder = VAULT / (CFG.get("tasks") or {}).get("dir", "Tasks")
        for t in ht.all_tasks(folder):
            if not t.get("bad") and t.get("owner") == role and t.get("status") == "doing":
                notes.append(Path(t["path"]))
    if len(notes) != 1:
        return None, None
    try:
        files = ht.props(notes[0].read_text()).get("files", "")
    except OSError:
        return None, None
    return notes[0].stem, [f.strip() for f in files.split(",") if f.strip()]


def role_problem(role, tool, tool_input):
    r = role_info(role)
    if not isinstance(r, dict):
        return None

    def deny(what):
        return "deny", f"Role guard: {role} may not {what}. It may {role_limits(role)} {r.get('handOff') or ''} {USER} can lift this with `.ok`."
    if tool in ("Agent", "Task"):
        if tool_input.get("subagent_type") in (r.get("agents") or []):
            return None
        return deny("hand work to another agent")
    if tool.startswith("mcp__") and not tool.startswith("mcp__ccd_turn__"):
        if any(tool.startswith(x) for x in (r.get("mcp") or [])):
            return None
        return deny(f"use {tool}")
    if tool in H["editTools"]:
        mode = r.get("edit", "none")
        raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if mode == "none":
            return deny("edit files")
        full = Path(raw).resolve()
        base = project_root() if mode == "project" else VAULT.resolve()
        if base not in full.parents:
            return deny(f"edit {full} outside the {'project' if mode == 'project' else 'vault'}")
        if mode in ("vault", "project") and full.relative_to(project_root() if mode == "project" else base).parts[:1] == (".claude",):
            return deny("edit files under .claude")
        if r.get("taskScope") and on("taskScope"):
            stem, files = current_task_files(role)
            if stem is None:
                return "deny", f"Task scope: no task is open for {role}, so no file may be edited. {USER} can lift this with `.ok`."
            rel = os.path.relpath(full, project_root())
            if not any(fnmatch.fnmatch(rel, pat) for pat in files):
                return "deny", f"Task scope: {rel} is not in this task's files ({', '.join(files) or 'none listed'}). Comment on the task and set it blocked if more files are needed. {USER} can lift this with `.ok`."
        for rule in r.get("editDeny") or []:
            if any(str(full).startswith(str(root.resolve() / rule)) for root in (VAULT, project_root())):
                return deny(f"edit {rule} by hand; use the homey task commands")
    if tool == "Bash":
        command = tool_input.get("command", "")
        if r.get("denyHomey"):
            for words in shell_words(command):
                if homey_sub(words) in r["denyHomey"]:
                    return deny(f"run homey {homey_sub(words)}; the lead sets tasks and their files")
        if r.get("noFileWrites"):
            why = write_problem(command)
            if why:
                return deny(f"run {why}; edit files with the Edit tools")
        for pat in expand_deny(r.get("denyBash") or []):
            if re.search(pat, command):
                return deny("run this command (it writes, forces or skips a check)")
    if tool == "Bash" and r.get("bash", "any") != "any":
        allowed = list(r["bash"]) + ["echo"]
        parts = scan_parts(command)
        if parts is None:
            rough = re.split(r"&&|[;|\n]", command)
            try:
                firsts = [command_program(shlex.split(x)) for x in rough if x.strip()]
            except (ValueError, IndexError):
                firsts = []
            if firsts and all(f in allowed for f in firsts):
                if role == (CFG.get("tasks") or {}).get("mainRole"):
                    return None
                return "deny", f"Role guard: {FORM_RULE} Fix the command and retry."
            return deny("run this command")
        if any(command_program(p) not in allowed for p in parts):
            return deny("run this command")
        for p in parts:
            why = segment_problem(p, r)
            if why:
                return deny(f"run {why}")
    return None


def kit_is_copy():
    kit = Path(__file__).resolve().parents[3]
    return kit.name == "homey-plugin" and not (kit / "copy-kit.sh").is_file()


def lock_problem(tool, tool_input):
    """A copied kit is changed from the source kit through copy-kit.sh, never in place."""
    root = CONFIG_FILE.parent.parent.resolve()
    names = ["homey-plugin", "homey.json", "settings.json", "agents"]
    msg = f"Plugin lock: this kit is a copy; the source kit changes it through copy-kit.sh. {USER} can lift this with `.ok`."
    if tool in H["editTools"]:
        full = Path(tool_input.get("file_path") or tool_input.get("notebook_path") or "").resolve()
        if any(full == root / ".claude" / n or root / ".claude" / n in full.parents for n in names):
            return "deny", msg
    elif tool == "Bash":
        command = tool_input.get("command", "")
        tokens = scan_command(command)
        if tokens and command_program(tokens) == "homey":
            return None
        target = r"\.claude/(" + "|".join(re.escape(n) for n in names) + ")"
        if re.search(rf"(sed\s+-i|>|\btee\b|\b(mv|cp|rsync|install|ln)\b)[^\n;|&]*{target}|open\([^\n)]*{target}[^\n)]*['\"][wa]", command):
            return "deny", msg
    return None


def shell_words(command):
    """Segments of words from a command: quotes removed, `$(...)` left as text, `<<` heredoc bodies skipped (only outside quotes)."""
    segs, words, cur, pending = [], [], None, []
    i, n = 0, len(command)

    def end_word():
        nonlocal cur
        if cur is not None:
            words.append(cur)
            cur = None

    def end_seg():
        end_word()
        if words:
            segs.append(list(words))
            words.clear()
    while i < n:
        c = command[i]
        if c == "\\":
            if i + 1 < n:
                cur = (cur or "") + command[i + 1]
            i += 2
        elif c == "'":
            j = command.find("'", i + 1)
            j = n if j < 0 else j
            cur = (cur or "") + command[i + 1:j]
            i = j + 1
        elif c == '"':
            j, buf = i + 1, ""
            while j < n and command[j] != '"':
                if command[j] == "\\" and j + 1 < n:
                    j += 1
                buf += command[j]
                j += 1
            cur = (cur or "") + buf
            i = j + 1
        elif c == "\n":
            end_seg()
            i += 1
            for delim in pending:
                while i < n:
                    j = command.find("\n", i)
                    j = n if j < 0 else j
                    line, i = command[i:j], j + 1
                    if line.strip() == delim:
                        break
            pending = []
        elif command.startswith("<<", i) and not command.startswith("<<<", i):
            m = re.match(r"<<-?\s*(?:'([^']*)'|\"([^\"]*)\"|(\w+))", command[i:])
            end_word()
            if m:
                pending.append(m.group(1) or m.group(2) or m.group(3))
                i += m.end()
            else:
                i += 2
        elif c == ">":
            if cur is not None and cur.isdigit():
                cur = None
            end_word()
            m = re.match(r">>?(&-|&\d+)?", command[i:])
            if not m.group(1):
                words.append("\x00>")
            i += m.end()
        elif c in ";|&()":
            end_seg()
            i += 2 if command[i:i + 2] in ("&&", "||") else 1
        elif c.isspace():
            end_word()
            i += 1
        else:
            cur = (cur or "") + c
            i += 1
    end_seg()
    return segs


def command_core(words):
    """(program basename, arguments) after env assignments and env, command, time wrappers."""
    i = 0
    while i < len(words):
        w = words[i]
        if re.match(r"\w+=", w):
            i += 1
        elif os.path.basename(w) in ("env", "command", "time", "nice", "nohup", "exec"):
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 2 if words[i] == "-u" else 1
        else:
            break
    return (os.path.basename(words[i]), words[i + 1:]) if i < len(words) else ("", [])


def link_problem(command):
    """A commit or PR create must carry a `Task: <task note name>` line in its own -m or --body value; only real commands count."""
    stems = [p.stem for p in (VAULT / (CFG.get("tasks") or {}).get("dir", "Tasks")).glob("*.md")]

    def named(vals):
        return any(re.search(r"Task:\s*\[*" + re.escape(st), v) for v in vals for st in stems)
    how = "Use -m with text that holds a line `Task: <task note name>` (the note name from Tasks/)"
    for words in shell_words(command):
        prog, args = command_core(words)
        if prog == "git":
            _, rest = skip_globals(args, GIT_ARG_OPTS)
            if not rest or rest[0] != "commit":
                continue
            a, vals, k = rest[1:], [], 0
            while k < len(a):
                t = a[k]
                if t == "--file" or t.startswith("--file="):
                    return f"Commit link: -F and --file are denied. {how}, then retry."
                if t == "--message":
                    vals.append(a[k + 1] if k + 1 < len(a) else "")
                    k += 1
                elif t.startswith("--message="):
                    vals.append(t[10:])
                elif re.match(r"^-[A-Za-z]", t) and not t.startswith("--"):
                    m = re.match(r"^-([A-Za-z]*?)([mF])(.*)$", t)
                    if m and m.group(2) == "F":
                        return f"Commit link: -F and --file are denied. {how}, then retry."
                    if m:
                        if m.group(3):
                            vals.append(m.group(3))
                        else:
                            vals.append(a[k + 1] if k + 1 < len(a) else "")
                            k += 1
                k += 1
            if not vals:
                return f"Commit link: a commit with no -m is denied. {how}, then retry."
            if not named(vals):
                return f"Commit link: this commit's own -m text has no `Task: <task note name>` line. {how}, then retry."
        elif prog == "gh":
            _, rest = skip_globals(args, GH_ARG_OPTS)
            if rest[:2] != ["pr", "create"]:
                continue
            a, vals, k = rest[2:], [], 0
            while k < len(a):
                t = a[k]
                if t in ("--body-file", "-F") or t.startswith("--body-file="):
                    return "Commit link: --body-file is denied. Use --body with a line `Task: <task note name>`, then retry."
                if t in ("--body", "-b"):
                    vals.append(a[k + 1] if k + 1 < len(a) else "")
                    k += 1
                elif t.startswith("--body="):
                    vals.append(t[7:])
                elif t.startswith("-b") and not t.startswith("--"):
                    vals.append(t[2:])
                k += 1
            if not named(vals):
                return "Commit link: the PR create command needs its own --body value holding a line `Task: <task note name>` (the note name from Tasks/). Fix it and retry."
    return None


def steer_or(check, problem):
    """A problem from a steerOnly check becomes a short reminder the agent may go on from."""
    if not problem or check not in (CFG.get("steerOnly") or []) or problem[0] != "deny":
        return problem
    reason = re.sub(r" Do not retry[^.]*\.", "", problem[1])
    reason = re.sub(rf" {re.escape(USER)} can lift this with `\.ok`\.", "", reason)
    return "steer", reason.strip() + " You may go on if the work needs it."


def guard_problem(data, tool, tool_input):
    """Guards the user can lift for one turn by starting a message with `.ok`."""
    if on("approvalGuard"):
        problem = approval_problem(tool, tool_input)
        if problem:
            return problem
    if on("roleGuard"):
        problem = role_problem(role_of(data), tool, tool_input)
        if problem:
            return steer_or("taskScope" if problem[1].startswith("Task scope") else "roleGuard", problem)
    role = role_of(data)
    main_role = (CFG.get("tasks") or {}).get("mainRole")
    if on("paneQuestions") and main_role and role == main_role and is_main_role(data, role):
        if tool == "AskUserQuestion" or (tool == "mcp__ccd_turn__wrap_up" and str(tool_input.get("ask") or "").strip()):
            return steer_or("paneQuestions", ("deny", f"Pane questions: the lead does not ask {USER} in the chat. Hand `capturer` a task and follow skill homey-wait; the question goes to the pane. {USER} can lift this with `.ok`."))
    if on("noTestRuns") and tool == "Bash" and isinstance(role_info(role), dict):
        found = no_test_problem(tool_input.get("command", ""))
        if found:
            return steer_or("noTestRuns", ("deny", f"No test runs: `{found}` is a test or CI command. {USER}'s rule: tests and CI are not used here, production use is the proof. {USER} can lift this with `.ok`."))
    if on("commitLink") and tool == "Bash" and (role_info(role) or {}).get("commitLink"):
        text = link_problem(tool_input.get("command", ""))
        if text:
            return steer_or("commitLink", ("deny", text))
    if on("pluginLock") and kit_is_copy():
        problem = lock_problem(tool, tool_input)
        if problem:
            return steer_or("pluginLock", problem)
    if on("agentGuard") and tool in ("Agent", "Task") and main_session() and data.get("session_id") == main_session():
        allowed_here = (role_info(role_of(data)) or {}).get("agents") or []
        if tool_input.get("subagent_type") not in H.get("agentOk", []) + allowed_here:
            return "deny", f"Agent guard: give standing agents work by task note (skill homey-task), not a subagent. {USER} can lift this with `.ok`."
    command = tool_input.get("command", "") if tool == "Bash" else ""
    path = Path(tool_input.get("file_path") or tool_input.get("notebook_path") or "") if tool in H["editTools"] else None
    skills_needed = set()
    if path:
        full = str(path.resolve())
        r_info = role_info(role) if on("roleGuard") else None
        in_project = isinstance(r_info, dict) and r_info.get("edit") == "project" and project_root() in path.resolve().parents
        if not full.startswith(str(VAULT.resolve()) + os.sep):
            if in_project:
                return None
            if on("scopeGuard") and not full.startswith(tuple(H["outsideOk"])):
                return "deny", f"Scope guard: {full} is outside {VAULT.name}; other repos keep their own agents. {USER} can lift this with `.ok`."
            return None
        if on("homeGuard") and path.name == HOME:
            return "ask", f"Home guard: Home is {USER}'s summary dashboard. {USER} approves this edit."
        note_skills = H["noteSkills"]
        if on("skillCheck") and ".claude" not in path.parts and path.suffix in note_skills:
            skills_needed.add(note_skills[path.suffix])
    if command:
        if on("homeGuard") and re.search(home_write_regex(), command):
            return "ask", f"Home guard: this command changes Home, {USER}'s summary dashboard. {USER} approves this edit."
        if on("logTimeCheck") and "daily:append" in command:
            now = time.strftime("%H%M")
            late = [t for t in re.findall(r"##\s+(\d{4})\b", command) if t > now]
            if late:
                return "deny", f"Log time guard: heading {late[0]} is later than now, {now}. Use the real time: `$(date +%H%M)`."
        if on("skillCheck") and needs_cli_skill(command):
            skills_needed.add(H["cliSkill"])
    if skills_needed and not data.get("agent_id"):
        missing = skills_needed - loaded_skills(data.get("transcript_path"))
        if missing:
            missing -= skills_in_whole_transcript(data.get("transcript_path"))
        if missing:
            return "deny", f"Skill check: load {', '.join(sorted(missing))} with the Skill tool first, then retry."
    return None


TEMP_ROOTS = ("/tmp/", "/private/tmp/", "/var/folders/", "/private/var/folders/", "$TMPDIR/", "${TMPDIR}/", tempfile.gettempdir().rstrip("/") + "/")


def without_temp_deletes(command):
    """The command minus any `rm` that only touches a temp folder, so the danger guard judges the rest. Unsure means it stays."""
    values = {}
    for name, value in re.findall(r"\b(\w+)=\"?([^\s;\"&|]*)", command):
        values.setdefault(name, []).append(value)

    def temp_value(v):
        return v.startswith("$(mktemp") or any(v.startswith(r) and v[len(r):].strip("/") for r in TEMP_ROOTS)
    loop_vars = set(re.findall(r"\b(?:for|read)\s+(\w+)", command))
    temp_vars = {n for n, vs in values.items() if n not in loop_vars and all(temp_value(v) for v in vs)}

    def is_temp(path):
        if ".." in path or "`" in path or "$(" in path:
            return False
        m = re.fullmatch(r"\$\{?(\w+)\}?(/.*)?", path)
        if m and m.group(1) in temp_vars:
            return True
        for root in TEMP_ROOTS:
            if path.startswith(root):
                rest = path[len(root):].strip("/")
                return bool(rest) and not rest.startswith("*")
        return False

    kept = []
    for part in re.split(r"(&&|\|\||;|\n)", command):
        try:
            words = shlex.split(part)
        except ValueError:
            words = []
        if words and words[0] in ("rm", "/bin/rm"):
            targets = [w for w in words[1:] if not w.startswith("-")]
            if targets and all(is_temp(t) for t in targets):
                continue
        kept.append(part)
    return "".join(kept)


def guard(data):
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}
    command = tool_input.get("command", "") if tool == "Bash" else ""
    command = without_temp_deletes(command) if command else command
    if approval_stamp(data.get("session_id")).exists():
        return
    if on("dangerGuard") and (any(re.search(p, command) for p in H["askFirst"]) or (tool.startswith("mcp__") and re.search(H["tradeToolPattern"], tool))):
        if os.environ.get("HOMEY_TASK"):
            found = next((m.group(0).strip() for m in (re.search(p, command) for p in H["askFirst"]) if m), tool)
            decide("deny", f"Danger guard matched `{found}` in this command. A task run gets no approval, so do not retry it. If that is only words in text you are saving to the note, reword them, for example `order send` for a call name. If you really need it run, set status blocked and comment what you need.")
            return
        problem = ("ask", "Danger guard: this deletes something, starts a stopped container or touches orders.")
    else:
        problem = guard_problem(data, tool, tool_input)
    if problem:
        decision, reason = problem
        if decision == "ask" and data.get("permission_mode") == "bypassPermissions":
            decision, reason = "deny", f"{reason} This mode shows no prompt, so it is blocked. {USER} approves by starting a message with `.ok`."
        if decision == "steer":
            note = plan_nudge(data)
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": reason + (" " + note if note else "")}}))
            return
        decide(decision, reason)
        return
    note = plan_nudge(data)
    if note:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": note}}))


HANDLERS = {"resume": resume, "prompt": prompt, "checkpoint": checkpoint, "logcheck": logcheck, "canvas": canvas, "guard": guard}

if __name__ == "__main__":
    try:
        setup()
    except NotSetUp:
        if sys.argv[1:] == ["resume"]:
            emit("SessionStart", "Homey is installed but this folder is not set up. If the user asks to set it up, load skill homey:homey-setup.")
        sys.exit(0)
    except Bad as e:
        line = f"Homey hooks: {e}"
        if sys.argv[1:] == ["resume"]:
            emit("SessionStart", line)
        print(line, file=sys.stderr)
        sys.exit(1)
    HANDLERS[sys.argv[1]](json.load(sys.stdin))
