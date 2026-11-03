"""Task notes: one Markdown note per task, shared by bin/homey, the watcher and the steer hook.
Shape: properties type, owner, status, summary; sections Brief, Comments, Result."""
import hashlib, json, os, re, time
from pathlib import Path

SECTIONS = ("Brief", "Comments", "Result")


class TaskError(Exception):
    pass


def split_front(text):
    m = re.match(r"---\n(.*?)\n---\n?", text, re.S)
    if not m:
        raise TaskError("no properties block")
    return m.group(1), text[m.end():]


def props(text):
    front, _ = split_front(text)
    out = {}
    for line in front.splitlines():
        if ":" in line and not line.startswith((" ", "-")):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def section(text, name):
    """Body of one section, without its heading."""
    _, body = split_front(text)
    m = re.search(rf"^## {re.escape(name)}[ \t]*\n(.*?)(?=^## |\Z)", body, re.M | re.S)
    if not m:
        raise TaskError(f"no ## {name} section")
    return m.group(1)


def comments(text):
    """Comment lines in note order. Any line that starts a list item counts, with or without a name."""
    return [l.strip() for l in section(text, "Comments").splitlines() if re.match(r"\s*[-*] +\S", l)]


def author(line, known):
    """The name before the first colon when it is a known one, else None: the user typing with no name."""
    m = re.match(r"[-*] +([\w-]+):", line)
    name = m.group(1).lower() if m else None
    return name if name in known else None


def comment_keys(lines):
    """Stable key per line; the same text twice gets two keys."""
    seen, keys = {}, []
    for line in lines:
        seen[line] = seen.get(line, 0) + 1
        keys.append(hashlib.sha1(f"{seen[line]}|{line}".encode()).hexdigest()[:16])
    return keys


def write(path, text):
    """Whole-file swap, so Obsidian and the watcher never read half a note."""
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def one_line(text):
    return " ".join(str(text).split())


def yaml_quote(text):
    return '"' + one_line(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def file_name(title):
    clean = re.sub(r'[\\/:*?"<>|#^\[\]]', " ", one_line(title))
    return " ".join(clean.split())[:80].strip() or "task"


def create(folder, owner, title, brief, extra=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{time.strftime('%Y-%m-%d %H%M')} {file_name(title)}"
    path, n = folder / f"{stem}.md", 1
    while path.exists():
        n += 1
        path = folder / f"{stem} {n}.md"
    more = "".join(f"{k}: {yaml_quote(v)}\n" for k, v in (extra or {}).items())
    write(path, f"---\ntype: task\nowner: {owner}\nstatus: todo\nsummary: {yaml_quote(title)}\n{more}---\n"
                f"## Brief\n{brief.strip()}\n\n## Comments\n\n## Result\n")
    return path


def create_ask(folder, owner, question, why, context, options):
    """A question for the user, who owns the note, so the watcher leaves it alone. options: (label, reply) pairs.
    Context is what Homey reads when the answer comes: how it arose, what is already done, what each answer does."""
    if not context.strip():
        raise TaskError("a question needs its context")
    labels = ["Needed:", "How it came up:", "Done:", "Not done:", "Each answer:", "Pick:", "Evidence:"]
    missing = [l for l in labels if not re.search(re.escape(l) + r"[ \t]*\S", context)]
    if missing:
        raise TaskError("the context is missing, or has no text after: " + " ".join(missing))
    if not options:
        raise TaskError("a question needs at least one option")
    path = create(folder, owner, question, why)
    t = path.read_text()
    lines = "".join(f"- {one_line(l)} | {one_line(r)}\n" for l, r in options)
    write(path, t.replace("## Comments\n", f"## Context\n{context.strip()}\n\n## Options\n{lines}\n## Comments\n", 1))
    return path


def options(text):
    """[(label, reply)] from the Options section; none when the note has no such section."""
    try:
        body = section(text, "Options")
    except TaskError:
        return []
    out = []
    for line in body.splitlines():
        m = re.match(r"[-*] +(.+?) \| (.+)$", line.strip())
        if m:
            out.append({"label": m.group(1), "reply": m.group(2)})
    return out


def add_comment(path, who, text):
    t = Path(path).read_text()
    section(t, "Comments")
    line = f"- {who}: {one_line(text)}\n"
    m = re.search(r"^## Comments[ \t]*\n(.*?)(?=^## |\Z)", t, re.M | re.S)
    body = m.group(1).rstrip("\n")
    new = (body + "\n" if body else "") + line + "\n"
    write(path, t[: m.start(1)] + new + t[m.end(1):])


def set_status(path, status):
    t = Path(path).read_text()
    front, body = split_front(t)
    if not re.search(r"^status:", front, re.M):
        raise TaskError("no status property")
    write(path, "---\n" + re.sub(r"^status:.*$", f"status: {status}", front, flags=re.M) + "\n---\n" + body)


def set_prop(path, key, value):
    """Set one frontmatter property: replace it, or add it last."""
    t = Path(path).read_text()
    front, body = split_front(t)
    line = f"{key}: {yaml_quote(value)}"
    if re.search(rf"^{re.escape(key)}:", front, re.M):
        front = re.sub(rf"^{re.escape(key)}:.*$", lambda m: line, front, count=1, flags=re.M)
    else:
        front = front.rstrip("\n") + "\n" + line
    write(path, "---\n" + front + "\n---\n" + body)


def set_later(path, day):
    """The user put this question off: it stays open, under For later in the pane."""
    t = Path(path).read_text()
    front, body = split_front(t)
    front = re.sub(r"^later:.*\n?", "", front, flags=re.M).rstrip("\n")
    write(path, "---\n" + front + f"\nlater: {day}" + "\n---\n" + body)


def set_result(path, text):
    t = Path(path).read_text()
    section(t, "Result")
    m = re.search(r"^## Result[ \t]*\n(.*?)(?=^## |\Z)", t, re.M | re.S)
    write(path, t[: m.start(1)] + text.strip() + "\n" + t[m.end(1):])


def optional_section(text, name):
    try:
        return section(text, name).strip()
    except TaskError:
        return ""


def set_section(path, name, body):
    """Replace a section, or add it just before Comments."""
    t = Path(path).read_text()
    m = re.search(rf"^## {re.escape(name)}[ \t]*\n(.*?)(?=^## |\Z)", t, re.M | re.S)
    if m:
        write(path, t[: m.start(1)] + body.strip() + "\n\n" + t[m.end(1):])
    else:
        write(path, t.replace("## Comments\n", f"## {name}\n{body.strip()}\n\n## Comments\n", 1))


def read_task(path):
    """One task as data, or {'bad': reason} when the note cannot be read as a task."""
    path = Path(path)
    try:
        text = path.read_text()
        p = props(text)
        if p.get("type") != "task":
            return {"path": str(path), "name": path.stem, "bad": "not a task note"}
        return {"path": str(path), "name": path.stem, "owner": p.get("owner", ""), "status": p.get("status", ""),
                "summary": p.get("summary", ""), "comments": comments(text), "result": section(text, "Result").strip(),
                "brief": section(text, "Brief").strip(), "options": options(text), "later": p.get("later", ""), "advice": optional_section(text, "Advice"), "senior": optional_section(text, "Senior advice")}
    except (OSError, UnicodeDecodeError, TaskError) as e:
        return {"path": str(path), "name": path.stem, "bad": str(e)}


def all_tasks(folder):
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return [read_task(p) for p in sorted(folder.glob("*.md"))]


def inbox_file(state_dir, session, path):
    """Where a message for an open session waits until that session's mod takes it."""
    return Path(state_dir) / "inbox" / f"{session}--{hashlib.sha1(str(path).encode()).hexdigest()[:16]}.json"


def take_messages(state_dir, session):
    """Claim this session's waiting messages. The rename means each is taken once; the watcher settles them."""
    inbox = Path(state_dir) / "inbox"
    taken = inbox / "taken"
    out = []
    for f in sorted(inbox.glob(f"{session}--*.json")):
        taken.mkdir(parents=True, exist_ok=True)
        try:
            os.rename(f, taken / f.name)
            out.append(json.loads((taken / f.name).read_text()))
        except (OSError, ValueError):
            continue
    return out


BUG_STATES = ["reported", "verified", "not reproduced", "fixed"]
BUG_HEAD = ["| Bug | State | Reporter | Task |", "|---|---|---|---|"]


def cell(text):
    """One table cell: no pipe, no line break."""
    return " ".join(str(text).replace("|", "/").split())


def bug_rows(text):
    """{'Open': [row lines], 'Closed': [row lines]} from the Bugs note."""
    out = {}
    for name in ("Open", "Closed"):
        m = re.search(rf"^## {name}[ \t]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
        lines = [l.strip() for l in (m.group(1) if m else "").splitlines() if l.strip().startswith("|")]
        out[name] = [l for l in lines if not l.startswith("| Bug |") and not re.fullmatch(r"\|[-| :]+\|", l)]
    return out


def write_bugs(bugs_file, rows, front=None):
    """Whole-note rewrite of the Bugs note: front matter kept or made, two tables."""
    bugs_file = Path(bugs_file)
    if front is None:
        front = ('type: index\nsummary: "Bugs reported and their state; Open feeds the Bugs tab"\n'
                 f"created: {time.strftime('%Y-%m-%d')}\nup: \"[[Homey map]]\"\ntags:\n  - homey\n  - bugs\naliases:\n  - Bugs")
    body = "".join(f"## {n}\n" + "\n".join(BUG_HEAD + rows[n]) + "\n\n" for n in ("Open", "Closed"))
    bugs_file.parent.mkdir(parents=True, exist_ok=True)
    write(bugs_file, "---\n" + front + "\n---\n" + body)


def read_bugs(bugs_file):
    bugs_file = Path(bugs_file)
    if not bugs_file.is_file():
        return None, {"Open": [], "Closed": []}
    text = bugs_file.read_text()
    front, _ = split_front(text)
    return front, bug_rows(text)


def add_bug(folder, bugs_file, text, reporter):
    """A bug is a normal task note for capturer (kind bug, bug reported) plus a row in the Bugs note. Returns the note path."""
    text = str(text).strip()
    if not text:
        raise TaskError("a bug needs text")
    words = re.sub(r"[^\w\s-]", "", " ".join(text.split()[:8])).strip() or "bug"
    path = create(folder, "capturer", "Bug: " + words, text, {"kind": "bug", "bug": "reported", "reporter": reporter})
    front, rows = read_bugs(bugs_file)
    rows["Open"].append(f"| {cell(words)} | reported | {cell(reporter)} | {Path(path).stem} |")
    write_bugs(bugs_file, rows, front)
    return path


def set_bug_state(bugs_file, task_path, state):
    """Set bug: in the task note and move or update its row: fixed and not reproduced go to Closed."""
    if state not in BUG_STATES:
        raise TaskError("unknown bug state: " + str(state) + "; states: " + ", ".join(BUG_STATES))
    pr = props(Path(task_path).read_text())
    if pr.get("kind") != "bug":
        raise TaskError("not a bug note: " + Path(task_path).stem)
    stem = Path(task_path).stem
    front, rows = read_bugs(bugs_file)
    found = None
    for name in ("Open", "Closed"):
        for line in rows[name]:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and cells[-1] == stem:
                found = cells
                rows[name].remove(line)
                break
        if found:
            break
    set_prop(task_path, "bug", state)
    if found is None:
        found = [cell(pr.get("summary", stem).replace("Bug: ", "", 1)), state, cell(pr.get("reporter", "")), stem]
    found[1] = state
    target = "Closed" if state in ("fixed", "not reproduced") else "Open"
    rows[target].append("| " + " | ".join(found) + " |")
    write_bugs(bugs_file, rows, front)


def add_changelog(path, line, task_stem, commit):
    """One row at the top of today's section of the changelog note (newest section first); the note is made on first use."""
    path = Path(path)
    text = str(line).strip()
    if not text:
        raise TaskError("a changelog line needs text")
    today = time.strftime("%Y-%m-%d")
    front, sections = None, {}
    if path.is_file():
        old = path.read_text()
        front, body = split_front(old)
        for m in re.finditer(r"^## (\d{4}-\d{2}-\d{2})[ \t]*\n(.*?)(?=^## |\Z)", body, re.M | re.S):
            rows = [l.strip() for l in m.group(2).splitlines() if l.strip().startswith("|")]
            sections[m.group(1)] = [l for l in rows if not l.startswith("| Change |") and not re.fullmatch(r"\|[-| :]+\|", l)]
    if front is None:
        front = ('type: index\nsummary: "What changed, in one plain line each, newest day first"\n'
                 f"created: {today}\nup: \"[[Homey map]]\"\ntags:\n  - homey\n  - changelog\naliases:\n  - Changelog")
    sections.setdefault(today, []).insert(0, f"| {cell(text)} | {cell(task_stem)} | {cell(commit or '-')} |")
    head = ["| Change | Task | Commit |", "|---|---|---|"]
    body = "".join(f"## {d}\n" + "\n".join(head + sections[d]) + "\n\n" for d in sorted(sections, reverse=True))
    path.parent.mkdir(parents=True, exist_ok=True)
    write(path, "---\n" + front + "\n---\n" + body)


DEPLOY_LABELS = ["Services", "Steps", "Expected", "Rollback"]


def deploy_parts(brief):
    """({label: [lines]}, [problems]) from a Deploy brief: Services:, Steps:, Expected:, Rollback:; Steps and Rollback are `- ` lines."""
    parts, cur = {}, None
    for line in str(brief).splitlines():
        m = re.match(r"\s*(Services|Steps|Expected|Rollback):\s*(.*)$", line)
        if m:
            cur = m.group(1)
            parts[cur] = [m.group(2)] if m.group(2).strip() else []
        elif cur is not None and line.strip():
            parts[cur].append(line.strip())
    problems = []
    for label in DEPLOY_LABELS:
        lines = parts.get(label)
        if not lines:
            problems.append(f"{label}:")
        elif label in ("Steps", "Rollback") and not all(l.startswith("- ") and l[2:].strip() for l in lines):
            problems.append(f"{label}: (one command per line, each starting with `- `)")
    return parts, problems


def fill_vault(text, name, folder):
    """Name the vault and its folder in an agent file, in place of the <vault> placeholder."""
    where = f"`{name}` (folder `{folder}`; every note path in a skill is inside it, so `Inbox/x.md` is `{folder}/Inbox/x.md`)"
    return text.replace("`<vault>`", where).replace("<vault>", name)
