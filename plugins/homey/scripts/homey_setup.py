#!/usr/bin/env python3
"""First setup of a vault: folders, Obsidian templates and Bases, agents, settings, first daily note.
  homey_setup.py --vault <folder> --name <your name> [--domains A,B] [--style short|normal] [--dry-run]
Safe to rerun: it never overwrites a file, and says what it made and what it kept.
Obsidian is required: it holds the memory, so setup stops if the Obsidian command line is missing.
Agents run with no bypass unless you set tasks.permissionMode yourself."""
import argparse, json, re, shutil, subprocess, sys, time
from pathlib import Path
import homey_tasks as ht

SETUP = Path(__file__).resolve().parent.parent / "setup"


HOME = "Ho" "me.md"
DEFAULT_DOMAINS = ["Work", "Code", "Research", "Content"]


def map_note(area):
    day = time.strftime("%Y-%m-%d")
    body = f"Notes in {area} link here through their `up` property. Open backlinks or the graph to see them."
    if area == "Homey":
        body = "The system behind this vault: [[Homey Rules|rules]], [[Homey Facts|facts]], [[Homey Tools|tools]] and [[Agents|agents]]."
    return f'---\ntype: map\nsummary: "Everything in {area}"\ncreated: {day}\nup: "[[Home]]"\ntags:\n  - map\n  - {area.lower()}\n---\n{body}\n'


def fit(rel, text, domains, maps):
    """A starter file with this vault's date, maps and domains in place of the defaults."""
    name = rel.as_posix()
    if name == HOME:
        text = text.replace("{{maps}}", " · ".join(f"[[{m} map]]" for m in maps))
    if rel.parts[0] == "Homey":
        text = text.replace("{{created}}", time.strftime("%Y-%m-%d"))
    if not domains:
        return text
    if name == "CLAUDE.md":
        text = text.replace(" ".join(f"`{d}/`" for d in DEFAULT_DOMAINS), " ".join(f"`{d}/`" for d in domains))
    elif name == HOME:
        text = text.replace(" · ".join(f"`{d}/`" for d in DEFAULT_DOMAINS), " · ".join(f"`{d}/`" for d in domains))
    elif name == "System/Bases/Vault.base":
        old = "".join(f'        - file.inFolder("{d}")\n' for d in DEFAULT_DOMAINS)
        text = text.replace(old, "".join(f'        - file.inFolder("{d}")\n' for d in domains))
    elif name == ".obsidian/graph.json":
        graph = json.loads(text)
        defaults = [fr"path:/^{d}\//" for d in DEFAULT_DOMAINS]
        colors = [g["color"] for g in graph["colorGroups"] if g["query"] in defaults]
        others = [g for g in graph["colorGroups"] if g["query"] not in defaults]
        graph["colorGroups"] = [{"query": fr"path:/^{d}\//", "color": colors[i % len(colors)]} for i, d in enumerate(domains)] + others
        text = json.dumps(graph, indent=2)
    return text


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "user"


def settings(name, vault, domains, style):
    c = json.loads((SETUP / "homey.default.json").read_text())
    who = slug(name)
    c["user"] = {"name": name, "id": who}
    c["hooks"]["obsidianVault"] = vault.name
    c["tasks"]["people"] = [who] + c["tasks"]["people"]
    if style == "short":
        c["hooks"]["style"] = "Reply to {user} in at most 90 words with one table or diagram. Put detail in a vault note and link it. Use the vault flows: each has a `homey-*` skill."
        c["hooks"]["checks"].append("replyCheck")
    if domains:
        fixed = [d for d in c["domains"] if d in ("Homey", "Inbox", "Tasks")]
        c["domains"] = fixed[:1] + domains + fixed[1:]
        c["hooks"]["projectDomains"] = list(domains)
        c["hooks"]["summaryDomains"] = list(domains) + ["Homey"]
    return c


def place(target, write, dry, made, kept):
    if target.exists():
        kept.append(target)
        return
    made.append(target)
    if not dry:
        target.parent.mkdir(parents=True, exist_ok=True)
        write(target)


def obsidian(*args):
    """Output of an Obsidian command, or None when it cannot be reached."""
    try:
        r = subprocess.run(["obsidian", *args], capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 and "unable to find Obsidian" not in r.stdout else None


def open_vault(vault):
    """Register and open the vault through Obsidian's own route, the one its vault switcher uses. True when Obsidian lists it."""
    if obsidian("version") is None:
        subprocess.run(["open", "-g", "-a", "Obsidian"], capture_output=True)
        for _ in range(15):
            time.sleep(1)
            if obsidian("version") is not None:
                break
    known = obsidian("vaults") or ""
    if vault.name in known.split("\n"):
        return True
    code = f"require('electron').ipcRenderer.sendSync('vault-open',{json.dumps(str(vault))},false)"
    if "true" not in (obsidian("eval", f"code={code}") or ""):
        return False
    for _ in range(10):
        time.sleep(1)
        if vault.name in (obsidian("vaults") or "").split("\n"):
            return True
    return False


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--vault", required=True)
    a.add_argument("--name", required=True)
    a.add_argument("--domains", default="")
    a.add_argument("--style", choices=("short", "normal"), default="normal")
    a.add_argument("--dry-run", action="store_true")
    o = a.parse_args(argv)
    if not o.name.strip():
        sys.exit("setup: --name is empty")
    if not shutil.which("obsidian"):
        sys.exit("setup: Obsidian command line not found. Homey requires Obsidian: install 1.14 or later, turn on its command line in Settings, then run setup again.")
    vault = Path(o.vault).expanduser().resolve()
    domains = [d.strip() for d in o.domains.split(",") if d.strip()]
    made, kept = [], []
    maps = ["Homey"] + (domains or DEFAULT_DOMAINS)
    for f in sorted((SETUP / "vault").rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(SETUP / "vault")
        if domains and rel.parts[0] in ("Work", "Code", "Research", "Content"):
            continue
        if rel.parts[0] == "Homey" or rel.as_posix() in (HOME, "CLAUDE.md", "System/Bases/Vault.base", ".obsidian/graph.json"):
            place(vault / rel, lambda t, f=f, rel=rel: t.write_text(fit(rel, f.read_text(), domains, maps)), o.dry_run, made, kept)
        else:
            place(vault / rel, lambda t, f=f: shutil.copyfile(f, t), o.dry_run, made, kept)
    for m in maps:
        folder = m
        place(vault / folder / f"{m} map.md", lambda t, m=m: t.write_text(map_note(m)), o.dry_run, made, kept)
    for d in domains:
        place(vault / d / ".gitkeep", lambda t: t.write_text(""), o.dry_run, made, kept)
    for f in sorted((SETUP / "agents").iterdir()):
        place(vault / ".claude" / "agents" / f.name, lambda t, f=f: t.write_text(ht.fill_vault(f.read_text(), vault.name, ".")), o.dry_run, made, kept)
    place(vault / ".claude" / "homey.json", lambda t: t.write_text(json.dumps(settings(o.name.strip(), vault, domains, o.style), indent=2) + "\n"), o.dry_run, made, kept)
    today = time.strftime("%Y-%m-%d")
    place(vault / "Daily" / f"{today}.md", lambda t: t.write_text("## Setup\n- Vault set up by Homey\n- Next: ask the user what to work on first\n"), o.dry_run, made, kept)
    head = "Would make" if o.dry_run else "Made"
    print(f"{head} {len(made)} files, kept {len(kept)} that already exist, in {vault}")
    for t in kept:
        print("  kept " + str(t.relative_to(vault)))
    if o.dry_run:
        return
    if open_vault(vault):
        print(f"Obsidian has it open as the vault {vault.name}.")
        print("Next: start Claude Code here. Homey loads its skill by itself.")
    else:
        print("Obsidian could not open it by itself. In Obsidian: Open another vault, Open folder as vault, then pick this folder.")
        print("Then start Claude Code here. Homey loads its skill by itself.")


if __name__ == "__main__":
    main()
