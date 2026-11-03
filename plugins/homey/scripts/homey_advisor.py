#!/usr/bin/env python3
"""Two levels of advice. Junior: the standing advisor session, by task note; its result goes in the note that asked.
Senior: one call with no tools, no plugins and no session. Nothing starts it: Homey runs it by hand, on a hard question, after the junior, from a packet holding everything."""
import hashlib, json, re, subprocess, time
from pathlib import Path
import homey_tasks as ht

SENIOR_PROMPT = """You are the senior advisor, asked once, on a hard question. You have no tools and only the packet below; it holds a junior advisor's view and the gaps already filled. Advise only from it.
You recommend; the owner decides. Goals, plan changes and steps that are hard to undo stay with the owner.
Reply in exactly this form, at most 300 words in all, with nothing else:
Recommendation: <one option label if options are given, otherwise your answer>
Reason: <why, including where you differ from the junior>
Risk: <what could go wrong>
Questions: <every question you still need answered, all at once, or none>
There is no follow-up unless the owner asks again. If the packet is too thin to choose, write `Recommendation: none` and list every question."""
JUNIOR_FORM = """Report your answer with `result` in exactly this form, one line each, with nothing else:
Recommendation: <one option label if options are given, otherwise one sentence>
Reason: <one sentence>
Risk: <one sentence>
Missing: <every gap still open, each with who or what can fill it, or none>
Plans: <wikilinks to notes that would help beyond those in the packet, or none>"""
CUT = "\n[cut at the size limit]"
PACKET_CHARS, PER_DAY, SENIOR_PER_DAY, TIMEOUT, CALL_TIMEOUT = 24000, 20, 5, 900, 300
OWNER = "advisor"


def settings(cfg):
    """The advisor block, or an error when it is off."""
    a = cfg.get("advisor") or {}
    if not a.get("model"):
        raise ht.TaskError("the advisor is off; turn it on with: homey advisor <model> [role...]")
    if OWNER not in cfg["tasks"]["owners"]:
        raise ht.TaskError("the advisor has no session; start it, then: homey agent-add advisor <local_id> <model>")
    return a


def link_names(text):
    """Notes named as [[links]] or as a path ending in .md."""
    return list(dict.fromkeys(n.strip() for n in re.findall(r"\[\[([^\]|#]+)", text) + re.findall(r"/([^/\n`|\]]+?)\.md", text)))


def find_note(vault, name, skip):
    """A note by name, preferring folders not skipped; a finished plan named in a question sits in the skipped System/Archive. Hidden folders never count."""
    found = [p for p in sorted(Path(vault).rglob(f"{name}.md")) if not any(x.startswith(".") for x in p.relative_to(vault).parts[:-1])]
    for p in found:
        if not any(x in skip for x in p.relative_to(vault).parts[:-1]):
            return p
    return found[0] if found else None


def plain_body(text):
    try:
        return ht.split_front(text)[1].strip()
    except ht.TaskError:
        return text.strip()


def build_packet(question, why, context, options, plans, cap, before_plans=()):
    """plans: (name, text), with text None when the note was not found. before_plans: (heading, text), kept ahead of the plans, which a cut hits first."""
    parts = [f"# Question\n{question}"]
    if why:
        parts.append(f"# Why it matters\n{why}")
    if context:
        parts.append(f"# Context\n{context}")
    if options:
        parts.append("# Options\n" + "\n".join(f"- {o}" for o in options))
    parts += [f"# {heading}\n{text}" for heading, text in before_plans if text]
    if plans:
        parts.append("# Plans and designs")
        for name, text in plans:
            parts.append(f"## {name}\n{text}" if text is not None else f"Not found: {name}")
    packet = "\n\n".join(parts)
    return packet if len(packet) <= cap else packet[:cap] + CUT


def marker(state_dir, path):
    return Path(state_dir) / "advising" / (hashlib.sha1(str(path).encode()).hexdigest()[:16] + ".txt")


def is_advising(state_dir, path, timeout=TIMEOUT):
    try:
        return time.time() - marker(state_dir, path).stat().st_mtime < timeout
    except OSError:
        return False


def mark(state_dir, path):
    f = marker(state_dir, path)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("1")


def used_today(state_dir):
    try:
        day = time.strftime("%Y-%m-%d")
        return sum(line.startswith(day) and " senior " not in line for line in (Path(state_dir) / "advice.log").read_text().splitlines())
    except OSError:
        return 0


def check(cfg, state_dir, task, user_id, question):
    """Raises when this note may not be advised on right now. Returns the settings."""
    a = settings(cfg)
    if task.get("bad"):
        raise ht.TaskError(task["bad"])
    if task["status"] == "done":
        raise ht.TaskError("already answered: " + task["name"])
    if task["owner"] != user_id:
        if task["owner"] not in (a.get("agents") or []):
            raise ht.TaskError(f"{task['owner']} is not allowed to ask the advisor; the owner lists agents in advisor.agents")
        if not question:
            raise ht.TaskError("an agent's task needs its own question: homey advise <task> \"<question>\"")
    if used_today(state_dir) >= a.get("perDay", PER_DAY):
        raise ht.TaskError(f"the advisor's limit of {a.get('perDay', PER_DAY)} questions a day is reached")
    return a


def read_plans(vault, cfg, names):
    plans = []
    for name in dict.fromkeys(names):
        note = find_note(vault, name, cfg.get("skipDirs") or [])
        plans.append((name, plain_body(note.read_text("utf-8", "ignore")) if note else None))
    return plans


def advise(cfg, vault, root, state_dir, path, user_id, question="", extra_plans=()):
    """Give the advisor a task note holding the packet. Returns that note; its result reaches the asking note through deliver."""
    path = Path(path)
    task = ht.read_task(path)
    a = check(cfg, state_dir, task, user_id, question)
    text = path.read_text()
    if task["owner"] == user_id:
        q, why, context = question or task["summary"], task["brief"], ht.optional_section(text, "Context")
        options = [o["label"] for o in task["options"]]
    else:
        q, why, options = question, "", []
        context = "\n".join([task["brief"], *task["comments"]])
    plans = read_plans(vault, cfg, [*link_names(why + "\n" + context), *extra_plans])
    packet = build_packet(q, why, context, options, plans, a.get("packetChars", PACKET_CHARS), [("Reply form", JUNIOR_FORM)])
    packet = re.sub(r"(?m)^#", "###", packet)  # a plan's own ## Result must not end the note's sections
    made = ht.create(path.parent, OWNER, "Advise " + q, packet, {"advises": path.stem})
    mark(state_dir, path)
    with open(Path(state_dir) / "advice.log", "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {path.stem} model={a['model']} packet={len(packet)}\n")
    return made


def deliver(cfg, state_dir, path, text, user_id):
    """After a result on an advisor's note: the advice goes in the note that asked. An agent gets a comment, which wakes it."""
    name = ht.props(Path(path).read_text()).get("advises")
    target = Path(path).parent / f"{name}.md"
    if not name or not target.is_file():
        return
    model = (cfg.get("advisor") or {}).get("model", "")
    ht.set_section(target, "Advice", f"By: advisor, {model}, {time.strftime('%H:%M')}\n{text.strip()}")
    marker(state_dir, target).unlink(missing_ok=True)
    if ht.props(target.read_text()).get("owner") != user_id:
        ht.add_comment(target, OWNER, "Advice is in the note")


def senior_today(state_dir):
    day = time.strftime("%Y-%m-%d")
    try:
        return sum(line.startswith(day) and " senior " in line for line in (Path(state_dir) / "advice.log").read_text().splitlines())
    except OSError:
        return 0


def check_senior(cfg, state_dir, task, text, again):
    """Raises unless the junior has answered, its gaps are filled and the senior has not been asked. Returns the settings."""
    a = settings(cfg)
    if not a.get("senior"):
        raise ht.TaskError("no senior advisor; set one with: homey advisor senior <model>")
    if task["status"] == "done":
        raise ht.TaskError("already answered: " + task["name"])
    junior = ht.optional_section(text, "Advice")
    if not junior:
        raise ht.TaskError("ask the junior first: homey advise <note>")
    m = re.search(r"(?m)^Missing:[ \t]*(.*)$", junior)
    if m and m.group(1).strip().lower().rstrip(".") not in ("", "none") and not task["comments"]:
        raise ht.TaskError("fill the junior's gaps first: homey comment <note> homey \"<fact>\"")
    if ht.optional_section(text, "Senior advice") and not again:
        raise ht.TaskError("the senior was already asked; it is asked once. Use --again only with new facts")
    if senior_today(state_dir) >= a.get("seniorPerDay", SENIOR_PER_DAY):
        raise ht.TaskError(f"the senior's limit of {a.get('seniorPerDay', SENIOR_PER_DAY)} calls a day is reached")
    return a


def escalate(cfg, vault, root, state_dir, path, extra_plans=(), again=False):
    """One senior call. Saves the answer in the note and returns it."""
    path = Path(path)
    task = ht.read_task(path)
    text = path.read_text()
    a = check_senior(cfg, state_dir, task, text, again)
    why, context = task["brief"], ht.optional_section(text, "Context")
    junior = ht.optional_section(text, "Advice")
    plans = read_plans(vault, cfg, [*link_names("\n".join([why, context, junior, *task["comments"]])), *extra_plans])
    packet = build_packet(task["summary"], why, context, [o["label"] for o in task["options"]], plans, a.get("packetChars", PACKET_CHARS),
                          [("Junior advisor's view", junior), ("Gaps filled since", "\n".join(task["comments"]))])
    answer, usage, cost = run_call(cfg, a, root, packet)
    ht.set_section(path, "Senior advice", f"By: senior advisor, {a['senior']}, {time.strftime('%H:%M')}, ${cost:.3f}\n{answer}")
    tokens = sum(usage.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    with open(Path(state_dir) / "advice.log", "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} senior {path.stem} model={a['senior']} in={tokens} out={usage.get('output_tokens', 0)} cost={cost}\n")
    return answer


def call_args(claude, model, prompt=SENIOR_PROMPT):
    return [claude, "-p", "--model", model, "--tools", "", "--setting-sources", "", "--strict-mcp-config",
            "--disable-slash-commands", "--no-session-persistence", "--system-prompt", prompt, "--output-format", "json"]


def one_call(cfg, model, prompt, root, packet, timeout=CALL_TIMEOUT):
    """One call with no tools, no plugins and no session. Returns its answer, usage and cost."""
    claude = str(Path(cfg["tasks"]["claudeBin"]).expanduser())
    try:
        r = subprocess.run(call_args(claude, model, prompt), input=packet, capture_output=True, text=True, cwd=root, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as e:
        raise ht.TaskError(f"the call did not run: {e}")
    try:
        d = json.loads(r.stdout)
    except ValueError:
        raise ht.TaskError(f"the call failed: {(r.stderr or r.stdout)[:160]}")
    if r.returncode or d.get("is_error"):
        raise ht.TaskError(f"the call failed: {str(d.get('result'))[:160]}")
    answer = re.sub(r"(?m)^#+\s*(?=(Recommendation|Reason|Risk|Questions|Missing):)", "", str(d.get("result", ""))).strip()
    return answer, d.get("usage") or {}, d.get("total_cost_usd", 0)


def run_call(cfg, a, root, packet):
    return one_call(cfg, a["senior"], SENIOR_PROMPT, root, packet, a.get("timeoutSeconds", CALL_TIMEOUT))
