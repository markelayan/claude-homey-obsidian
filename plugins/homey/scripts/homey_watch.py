#!/usr/bin/env python3
"""Homey watcher: no model. Reads Tasks/ and nudges the owner session on a new task or a comment.
  homey_watch.py tick     one pass, then exit
  homey_watch.py run      keep passing; macOS keeps this alive
Seen comments live in one append-only file per task, shared with the steer hook.
Each pass writes status.json for the pane: when it last ran and which sessions are live.
Settings come from `tasks` in .claude/homey.json."""
import hashlib, json, os, signal, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import homey_tasks as ht

ACTIVE = ("todo", "doing", "blocked", "review")
STALL_DEFAULTS = {"stallMinutes": 10, "stallStopMinutes": 30, "stallRestarts": 1, "stallDenials": 3}
KILL_AFTER_SECONDS = 60


def new_state():
    return {"tasks": {}, "runs": {}, "day": "", "dayNudges": 0}


def dumps_state(s):
    return json.dumps(s, indent=1, sort_keys=True)


def loads_state(text):
    s = new_state()
    s.update(json.loads(text))
    return s


def task_state(state, path):
    return state["tasks"].get(path) or {"nudges": 0, "todoNudged": False, "last": "", "note": {}}


def new_comments(t, seen, cfg):
    """Unseen comments from anyone but the owner and the watcher."""
    known = set(cfg["owners"]) | set(cfg["people"])
    out = []
    for line, key in zip(t["comments"], ht.comment_keys(t["comments"])):
        if key in seen:
            continue
        who = ht.author(line, known)
        if who not in (t["owner"], "watcher"):
            out.append(line)
    return out


def decide(tasks, state, live, today, cfg, seen_of, now):
    """What to do now. Pure: reads its inputs, changes nothing."""
    actions = []
    day_used = state["dayNudges"] if state["day"] == today else 0
    running = set(state["runs"])
    for t in tasks:
        if t.get("bad"):
            continue
        path, owner, status = t["path"], t["owner"], t["status"]
        st = task_state(state, path)
        if not owner or owner in cfg["people"]:
            continue
        if owner not in cfg["owners"] or status not in ACTIVE + ("done",):
            if not st["note"].get("skip"):
                actions.append({"kind": "skip", "path": path, "owner": owner, "reason": f"unknown owner or status: {owner}, {status}"})
            continue
        if status == "done":
            continue
        reopened = status == "todo" and st["last"] not in ("", "todo")
        wants_todo = status == "todo" and (reopened or not st["todoNudged"])
        fresh = new_comments(t, seen_of(path), cfg)
        if not (wants_todo or fresh):
            continue
        nudges = 0 if reopened else st["nudges"]
        if nudges >= cfg["nudgesPerTask"]:
            if status != "blocked":
                actions.append({"kind": "block", "path": path, "owner": owner, "reason": f"nudge limit reached ({cfg['nudgesPerTask']} for this task); drag to todo to go again"})
            continue
        if day_used >= cfg["nudgesPerDay"]:
            if status != "blocked":
                actions.append({"kind": "block", "path": path, "owner": owner, "reason": f"day nudge limit reached ({cfg['nudgesPerDay']}); drag to todo to go again"})
            continue
        if owner in running or len(running) >= cfg["maxRuns"]:
            continue
        if cfg["owners"][owner]["sessionId"] in live:
            note = st["note"]
            if cfg["holdMinutes"] and "heldAt" not in note:
                actions.append({"kind": "hold", "path": path, "owner": owner, "at": now, "reason": f"session is open in the app; will message it after {cfg['holdMinutes']} min, or nudge sooner if the app lets it go"})
            elif not note.get("messaged") and now - note.get("heldAt", now) >= cfg["holdMinutes"] * 60:
                actions.append({"kind": "message", "path": path, "owner": owner, "reason": "your session is open in the app"})
            continue
        reason = "new task" if wants_todo else f"{len(fresh)} new comment(s)"
        actions.append({"kind": "nudge", "path": path, "owner": owner, "reason": reason, "reopened": reopened})
        running.add(owner)
        day_used += 1
    return actions


def mark_action(state, action, today):
    """Record an action in state before it takes effect, so a restart cannot repeat it."""
    path = action["path"]
    st = task_state(state, path)
    if action["kind"] == "nudge":
        if state["day"] != today:
            state["day"], state["dayNudges"] = today, 0
        state["dayNudges"] += 1
        st["nudges"] = 1 if action.get("reopened") else st["nudges"] + 1
        st["todoNudged"] = True
        st["note"] = {}
    elif action["kind"] == "hold":
        st["note"]["heldAt"] = action["at"]
    elif action["kind"] == "message":
        st["note"]["messaged"] = True
    elif action["kind"] == "skip":
        st["note"]["skip"] = True
    state["tasks"][path] = st


def after_run(t, code, output):
    """A run ended. A block action with the reason, or None when the task is in order."""
    if t is None or t.get("bad"):
        return None
    error = None
    try:
        d = json.loads(output)
        if d.get("is_error"):
            error = ht.one_line(d.get("result") or d.get("subtype") or "run error")[:200]
    except (ValueError, AttributeError):
        pass
    if error or (code not in (0, None)):
        return {"kind": "block", "path": t["path"], "owner": t["owner"], "reason": f"run failed: {error or 'exit ' + str(code)}"}
    if t["status"] in ("todo", "doing"):
        return {"kind": "block", "path": t["path"], "owner": t["owner"], "reason": f"run ended with status still {t['status']}"}
    return None


def finished_now(tasks, state, cfg):
    """Agent tasks that reached review or blocked since the last pass. Each gives Homey one notice."""
    out = []
    for t in tasks:
        if t.get("bad") or not t["owner"] or t["owner"] in cfg["people"]:
            continue
        if t["status"] in ("review", "blocked") and task_state(state, t["path"])["last"] not in ("", t["status"]):
            out.append(t)
    return out


def stall_setting(cfg, key):
    return cfg.get(key, STALL_DEFAULTS[key])


def stall_actions(t, run, idle, denied, note, cfg):
    """What a working task needs, from how long it has been quiet and how often a hook denied it. Pure."""
    actions = []
    who = {"path": t["path"], "owner": t["owner"]}
    if denied >= stall_setting(cfg, "stallDenials") and not note.get("deniedWarned"):
        actions.append(dict(who, kind="denied", reason=f"{denied} commands denied by a guard in this run"))
    minutes = int(idle // 60)
    if run and idle >= stall_setting(cfg, "stallStopMinutes") * 60:
        if not note.get("stallStopped"):
            actions.append(dict(who, kind="stop", reason=f"quiet for {minutes} min, stopping the run"))
    elif idle >= stall_setting(cfg, "stallMinutes") * 60 and not note.get("stallWarned"):
        actions.append(dict(who, kind="warn", reason=f"quiet for {minutes} min, run still open"))
    return actions


def after_stall(t, restarts, cfg):
    """A run the watcher stopped has ended: go again while restarts remain, then block. None if the task moved on."""
    if t is None or t.get("bad") or t["status"] not in ("todo", "doing"):
        return None
    limit = stall_setting(cfg, "stallRestarts")
    if restarts < limit:
        return {"kind": "restart", "path": t["path"], "owner": t["owner"], "reason": "restarted after a stall: your earlier work is in this session, continue from where it stopped"}
    return {"kind": "block", "path": t["path"], "owner": t["owner"], "reason": f"stalled again after {limit} restart(s); needs a look"}


def count_denials(text):
    """Tool calls a hook denied, counted from transcript lines."""
    return sum('"is_error":true' in line.replace(" ", "") and "hook error" in line for line in text.splitlines())


def run_command(owner_cfg, claude, prompt, cfg=None, homey="homey", agent=None):
    """Bypass is opt-in: tasks.permissionMode in the settings. Otherwise a worker may only read and use the task commands."""
    cfg = cfg or {}
    mode = cfg.get("permissionMode") or "default"
    allowed = [] if mode == "bypassPermissions" else ["--allowedTools", ",".join(cfg.get("allowedTools") or ["Read", "Glob", "Grep", f"Bash(python3 {homey} *)"])]
    return [claude, "-p", "--resume", owner_cfg["sessionId"], "--model", owner_cfg["model"],
            *(["--agent", agent] if agent else []),
            "--permission-mode", mode, *allowed, "--output-format", "json", prompt]


def prompt_for(cfg, action, homey, vault):
    return cfg["prompt"].format(path=action["path"], reason=action["reason"], owner=action["owner"], homey=homey) + f" Vault folder: {vault} . Every note path in a skill is inside it."


def seen_file(state_dir, path):
    return Path(state_dir) / "seen" / (hashlib.sha1(str(path).encode()).hexdigest()[:16] + ".txt")


def read_seen(state_dir, path):
    try:
        return set(seen_file(state_dir, path).read_text().split())
    except OSError:
        return set()


def add_seen(state_dir, path, keys):
    f = seen_file(state_dir, path)
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a") as out:
        out.write("".join(k + "\n" for k in keys))


class Watcher:
    def __init__(self):
        p = Path(os.environ["HOMEY_CONFIG"]) if os.environ.get("HOMEY_CONFIG") else Path(__file__).resolve().parents[4] / "homey.json"
        self.config_path = p
        self.root = p.resolve().parent.parent
        self.procs = {}
        self.projects = Path.home() / ".claude" / "projects"
        self.load()

    def load(self):
        full = json.loads(self.config_path.read_text())
        self.cfg = full["tasks"]
        self.user = (full.get("user") or {}).get("name") or "the user"
        self.vault = (self.root / full["vault"]).resolve()
        self.folder = (self.vault / self.cfg["dir"]).resolve()
        self.state_dir = self.root / self.cfg["stateDir"]
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / "state.json"
        try:
            self.state = loads_state(self.state_file.read_text())
        except (OSError, ValueError):
            self.state = new_state()
        self.claude = os.path.expanduser(self.cfg["claudeBin"])
        self.homey = str(Path(__file__).resolve().parent.parent / "bin" / "homey")

    def refresh_config(self):
        """Pick up agents added and settings changed since the last pass."""
        try:
            full = json.loads(self.config_path.read_text())
            self.cfg = full["tasks"]
            self.user = (full.get("user") or {}).get("name") or "the user"
        except (OSError, ValueError, KeyError) as e:
            self.log(f"config unreadable, keeping the last good one: {ht.one_line(e)[:160]}")

    def log(self, text):
        with open(self.state_dir / "watch.log", "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")

    def save(self):
        ht.write(self.state_file, dumps_state(self.state))

    def live_sessions(self):
        """Live sessions and their status. None when it cannot be read: then nothing is nudged."""
        try:
            r = subprocess.run([self.claude, "agents", "--json"], capture_output=True, text=True, timeout=30, cwd=self.root, stdin=subprocess.DEVNULL)
            if r.returncode != 0:
                raise ValueError(r.stderr[:100])
            return {e["sessionId"]: e.get("status") or "idle" for e in json.loads(r.stdout) if e.get("sessionId") and (e.get("pid") or e.get("status"))}
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            self.log(f"live list failed: {ht.one_line(e)[:120]}")
            return None

    def write_status(self, live):
        """What the pane reads, so no session has to ask Claude Code itself."""
        ht.write(self.state_dir / "status.json", json.dumps({"at": time.time(), "live": live}))

    def block(self, action):
        ht.add_comment(action["path"], "watcher", action["reason"])
        ht.set_status(action["path"], "blocked")
        self.log(f"block {action['path']}: {action['reason']}")

    def finish_runs(self):
        for owner, run in list(self.state["runs"].items()):
            proc = self.procs.get(owner)
            if proc is not None:
                code = proc.poll()
                if code is None:
                    if time.time() - run["started"] > self.cfg["runTimeoutSeconds"]:
                        proc.send_signal(signal.SIGTERM)
                        self.log(f"timeout {owner}")
                    continue
            else:
                try:
                    os.kill(run["pid"], 0)
                    continue
                except ProcessLookupError:
                    code = None
                except PermissionError:
                    continue
            self.procs.pop(owner, None)
            output = ""
            try:
                output = Path(run["out"]).read_text()
            except (OSError, KeyError):
                pass
            t = ht.read_task(run["path"]) if Path(run["path"]).exists() else None
            st = task_state(self.state, run["path"])
            action = after_stall(t, st.get("restarts", 0), self.cfg) if run.get("stoppedAt") else after_run(t, code, output)
            del self.state["runs"][owner]
            self.log(f"end {owner} code={code} {run['path']}")
            if action and action["kind"] == "restart":
                st["restarts"] = st.get("restarts", 0) + 1
                self.state["tasks"][run["path"]] = st
                ht.add_comment(action["path"], "watcher", action["reason"])
                ht.set_status(action["path"], "todo")
                self.log(f"restart {owner} {action['path']}")
            elif action:
                self.block(action)
            self.save()

    def transcript(self, session_id):
        """The session's transcript file: the run writes to it, whatever the app shows."""
        return next(iter(self.projects.glob(f"*/{session_id}.jsonl")), None)

    def transcript_size(self, session_id):
        try:
            return self.transcript(session_id).stat().st_size
        except (AttributeError, OSError):
            return 0

    def activity(self, owner, run, since):
        """(Seconds quiet, hook denials in this run). Whole lines only: the last one may still be written."""
        log = self.transcript(self.cfg["owners"][owner]["sessionId"])
        last, denied = since, 0
        if log:
            try:
                last = max(since, log.stat().st_mtime)
                if run:
                    with open(log, "rb") as f:
                        f.seek(run.get("offset", 0))
                        chunk = f.read()
                    whole = chunk[: chunk.rfind(b"\n") + 1]
                    run["offset"] = run.get("offset", 0) + len(whole)
                    run["denied"] = run.get("denied", 0) + count_denials(whole.decode("utf-8", "replace"))
            except OSError as e:
                self.log(f"transcript unreadable {owner}: {ht.one_line(e)[:120]}")
        if run:
            run["lastActivity"] = last
            denied = run.get("denied", 0)
        return time.time() - last, denied

    def stop_run(self, owner, run):
        """The run started its own process group, so a tool call that hung stops with it."""
        try:
            os.killpg(run["pid"], signal.SIGKILL if run.get("stoppedAt") else signal.SIGTERM)
        except (OSError, KeyError) as e:
            self.log(f"stop failed {owner}: {ht.one_line(e)[:120]}")

    def check_stalls(self, tasks):
        """Warn Homey about a working task that went quiet or keeps being denied, and stop a run quiet for too long."""
        for t in tasks:
            if t.get("bad") or t["owner"] not in self.cfg["owners"]:
                continue
            owner, path = t["owner"], t["path"]
            run = self.state["runs"].get(owner)
            run = run if run and run["path"] == path else None
            if t["status"] not in ("todo", "doing") or (t["status"] == "todo" and not run):
                continue
            st = task_state(self.state, path)
            note = st["note"]
            if run and run.get("stoppedAt"):
                if time.time() - run["stoppedAt"] > KILL_AFTER_SECONDS:
                    self.stop_run(owner, run)
                continue
            since = run["started"] if run else Path(path).stat().st_mtime
            idle, denied = self.activity(owner, run, since)
            if run and idle < stall_setting(self.cfg, "stallMinutes") * 60:
                note.pop("stallWarned", None)
            for a in stall_actions(t, run, idle, denied, note, self.cfg):
                ht.add_comment(path, "watcher", a["reason"])
                self.log(f"{a['kind']} {owner} {path}: {a['reason']}")
                if a["kind"] == "stop":
                    note["stallStopped"] = True
                    self.stop_run(owner, run)
                    run["stoppedAt"] = time.time()
                else:
                    note["deniedWarned" if a["kind"] == "denied" else "stallWarned"] = True
                self.notify_homey(t, a["reason"])
            self.state["tasks"][path] = st
        self.save()

    def send_message(self, action):
        """Leave the prompt for the open session's mod. Counted as a nudge once it is taken."""
        sid = self.cfg["owners"][action["owner"]]["sessionId"]
        f = ht.inbox_file(self.state_dir, sid, action["path"])
        f.parent.mkdir(parents=True, exist_ok=True)
        ht.write(f, json.dumps({"path": action["path"], "prompt": prompt_for(self.cfg, action, self.homey, self.vault)}))
        ht.add_comment(action["path"], "watcher", action["reason"] + "; message left for it")
        self.log(f"message {action['owner']} {action['path']}: {action['reason']}")

    def notify_homey(self, t, stall=""):
        """Queue a notice for Homey's own mod. It starts a turn only when Homey is idle, so nothing interrupts."""
        f = ht.inbox_file(self.state_dir, self.cfg["homeySession"], t["path"])
        f.parent.mkdir(parents=True, exist_ok=True)
        text = f"Task may be stuck: {t['name']} (owner {t['owner']}): {stall}. Note: {t['path']} . Read its transcript and steer with a comment, or tell {self.user} what is wrong." if stall else f"Task moved to {t['status']}: {t['name']} (owner {t['owner']}). Note: {t['path']} . If review: check the result against the brief, then close it. Ask {self.user} only what is theirs to decide."
        ht.write(f, json.dumps({"path": t["path"], "notice": True, "prompt": text}))
        self.log(f"notice {'stall' if stall else t['status']} {t['path']}")

    def settle_messages(self, tasks):
        """Count taken messages as nudges, and drop waiting ones whose task has ended."""
        inbox = self.state_dir / "inbox"
        today = time.strftime("%Y-%m-%d")
        for f in sorted((inbox / "taken").glob("*.json")):
            try:
                message = json.loads(f.read_text())
                if message.get("notice"):
                    f.unlink(missing_ok=True)
                    continue
                path = message["path"]
                mark_action(self.state, {"kind": "nudge", "path": path}, today)
                if Path(path).exists():
                    keys = ht.comment_keys(ht.read_task(path).get("comments", []))
                    add_seen(self.state_dir, path, [k for k in keys if k not in read_seen(self.state_dir, path)])
                self.log(f"message taken {path}")
            except (OSError, ValueError, KeyError, ht.TaskError) as e:
                self.log(f"message settle failed {f.name}: {ht.one_line(e)[:120]}")
            f.unlink(missing_ok=True)
            self.save()
        active = {t["path"] for t in tasks if not t.get("bad") and t["status"] != "done"}
        for f in sorted(inbox.glob("*.json")):
            try:
                if json.loads(f.read_text())["path"] not in active:
                    f.unlink(missing_ok=True)
            except (OSError, ValueError, KeyError):
                f.unlink(missing_ok=True)

    def nudge(self, action):
        owner = action["owner"]
        ht.inbox_file(self.state_dir, self.cfg["owners"][owner]["sessionId"], action["path"]).unlink(missing_ok=True)
        t = ht.read_task(action["path"])
        add_seen(self.state_dir, action["path"], [k for k in ht.comment_keys(t.get("comments", [])) if k not in read_seen(self.state_dir, action["path"])])
        out = self.state_dir / f"run-{owner}.json"
        size = self.transcript_size(self.cfg["owners"][owner]["sessionId"])
        env = dict(os.environ, HOMEY_TASK=action["path"], HOMEY_SEEN=str(seen_file(self.state_dir, action["path"])), HOMEY_OWNER=owner, HOMEY_CONFIG=str(self.config_path))
        with open(out, "w") as f:
            agent = owner if (self.root / ".claude" / "agents" / f"{owner}.md").is_file() else None
            proc = subprocess.Popen(run_command(self.cfg["owners"][owner], self.claude, prompt_for(self.cfg, action, self.homey, self.vault), self.cfg, self.homey, agent),
                                    stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.DEVNULL, cwd=self.root, env=env, start_new_session=True)
        self.procs[owner] = proc
        self.state["runs"][owner] = {"pid": proc.pid, "path": action["path"], "started": time.time(), "out": str(out), "offset": size}
        self.log(f"nudge {owner} {action['path']}: {action['reason']}")

    def tick(self):
        self.refresh_config()
        self.finish_runs()
        tasks = ht.all_tasks(self.folder)
        for t in tasks:
            if t.get("bad"):
                self.log(f"bad note {t['path']}: {t['bad']}")
        self.settle_messages(tasks)
        self.check_stalls(tasks)
        today = time.strftime("%Y-%m-%d")
        seen = lambda path: read_seen(self.state_dir, path)
        live = self.live_sessions()
        self.write_status(live)
        if live is None:
            return
        actions = decide(tasks, self.state, set(live), today, self.cfg, seen, time.time())
        for a in actions:
            mark_action(self.state, a, today)
            self.save()
            try:
                if a["kind"] == "nudge":
                    self.nudge(a)
                elif a["kind"] == "message":
                    self.send_message(a)
                elif a["kind"] == "hold":
                    ht.add_comment(a["path"], "watcher", a["reason"])
                elif a["kind"] == "block":
                    self.block(a)
                else:
                    self.log(f"skip {a['path']}: {a['reason']}")
            except (OSError, ht.TaskError) as e:
                self.log(f"{a['kind']} failed {a['path']}: {ht.one_line(e)[:160]}")
        for t in finished_now(tasks, self.state, self.cfg):
            self.notify_homey(t)
        nudged = {a["path"] for a in actions if a["kind"] == "nudge"}
        for t in tasks:
            if not t.get("bad"):
                st = task_state(self.state, t["path"])
                if t["status"] == "todo" and st["last"] not in ("", "todo") and t["path"] not in nudged:
                    st["todoNudged"], st["nudges"] = False, 0
                st["last"] = t["status"]
                self.state["tasks"][t["path"]] = st
        known = {t["path"] for t in tasks}
        self.state["tasks"] = {p: s for p, s in self.state["tasks"].items() if p in known}
        self.save()


def main():
    w = Watcher()
    if sys.argv[1:] == ["tick"]:
        w.tick()
        return
    if sys.argv[1:] != ["run"]:
        print(__doc__)
        sys.exit(2)
    w.log("watcher started")
    while True:
        try:
            w.tick()
        except Exception as e:
            w.log(f"tick failed: {ht.one_line(e)[:200]}")
        time.sleep(w.cfg["tickSeconds"])


if __name__ == "__main__":
    main()
