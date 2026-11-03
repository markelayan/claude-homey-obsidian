#!/usr/bin/env python3
"""Keep the Homey watcher running through macOS.
  homey_watch_install.py install | uninstall | status | refresh
Each folder has its own job, so a second vault leaves the first one running.
Only file outside the vault: ~/Library/LaunchAgents/com.homey.watch.<folder>-<hash>.plist"""
import hashlib, os, plistlib, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_config():
    """A kit inside a project belongs to that project. An installed plugin takes the folder it is run for."""
    if HERE.parents[2].name == "homey-plugin":
        return HERE.parents[3] / "homey.json"
    if os.environ.get("HOMEY_CONFIG"):
        return Path(os.environ["HOMEY_CONFIG"]).resolve()
    d = Path.cwd().resolve()
    for p in [d, *d.parents]:
        if (p / ".claude" / "homey.json").is_file():
            return p / ".claude" / "homey.json"
    sys.exit("no .claude/homey.json found: run this in a folder set up with Homey")


CONFIG = find_config()
ROOT = CONFIG.parent.parent


def label_for(root):
    slug = re.sub(r"[^a-z0-9]+", "-", root.name.lower()).strip("-")
    digest = hashlib.sha1(str(root).encode()).hexdigest()[:6]
    return f"com.homey.watch.{slug}-{digest}"


LABEL = label_for(ROOT)
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
TARGET = f"gui/{os.getuid()}"


def plist(python=sys.executable, home=str(Path.home())):
    logs = ROOT / ".claude" / "homey-watch"
    return {
        "Label": LABEL,
        "ProgramArguments": [python, str(HERE / "homey_watch.py"), "run"],
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "ProcessType": "Background",
        "EnvironmentVariables": {
            "HOMEY_CONFIG": str(CONFIG),
            "HOME": home,
            "PATH": f"{home}/.local/bin:{Path(python).parent}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
        "StandardOutPath": str(logs / "launchd.log"),
        "StandardErrorPath": str(logs / "launchd.log"),
    }


def launchctl(*args):
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def install():
    (ROOT / ".claude" / "homey-watch").mkdir(parents=True, exist_ok=True)
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    launchctl("bootout", f"{TARGET}/{LABEL}")
    PLIST.write_bytes(plistlib.dumps(plist()))
    r = launchctl("bootstrap", TARGET, str(PLIST))
    if r.returncode:
        sys.exit(f"bootstrap failed: {r.stderr.strip()}")
    print("installed")


def uninstall():
    launchctl("bootout", f"{TARGET}/{LABEL}")
    PLIST.unlink(missing_ok=True)
    print("uninstalled")


def refresh():
    """After a plugin update the watcher's script moved: point the job at this copy. Does nothing if no job exists."""
    if not PLIST.exists():
        return
    if plistlib.loads(PLIST.read_bytes())["ProgramArguments"][1] != str(HERE / "homey_watch.py"):
        install()


def status():
    r = launchctl("print", f"{TARGET}/{LABEL}")
    if r.returncode:
        print("not running; plist " + ("present" if PLIST.exists() else "absent"))
        return
    state = pid = ""
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("state ="):
            state = line.split("=", 1)[1].strip()
        if line.startswith("pid ="):
            pid = line.split("=", 1)[1].strip()
    print(f"{state} pid {pid}")


if __name__ == "__main__":
    cmds = {"install": install, "uninstall": uninstall, "status": status, "refresh": refresh}
    if sys.argv[1:] and sys.argv[1] in cmds:
        cmds[sys.argv[1]]()
    else:
        print(__doc__)
        sys.exit(2)
