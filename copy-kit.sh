#!/bin/sh
# Copy the files a folder needs and install the plugin there, so a session started in it has the plugin from the start. Its own agent runs the bootstrap.
#   sh copy-kit.sh <folder>
# Each folder gets its own marketplace name: the registry and plugin cache are global and keyed by name, so a shared name makes folders overwrite each other.
set -e
TARGET="$1"; HERE="$(cd "$(dirname "$0")" && pwd)"
[ -n "$TARGET" ] || { echo "usage: sh copy-kit.sh <folder>"; exit 2; }
KIT="$TARGET/.claude/homey-plugin"
mkdir -p "$KIT"
TARGET="$(cd "$TARGET" && pwd)"; KIT="$TARGET/.claude/homey-plugin"
SLUG="$(basename "$TARGET" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//; s/-$//')"
HASH="$(printf '%s' "$TARGET" | shasum | cut -c1-6)"
MARKET="homey-$SLUG-$HASH"
rsync -a --exclude __pycache__ --exclude node_modules --exclude NOTES.md --exclude copy-kit.sh "$HERE/" "$KIT/"
python3 - "$KIT/.claude-plugin/marketplace.json" "$MARKET" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["name"] = sys.argv[2]
json.dump(d, open(p, "w"), indent=2)
PY
echo "Copied to $KIT"
cd "$TARGET"
claude plugin marketplace add "$KIT" --scope project >/dev/null
claude plugin install "homey@$MARKET" --scope project >/dev/null
echo "Plugin $MARKET installed for this folder. Start the session now: it loads at start."
if [ -f "$TARGET/.claude/homey.json" ]; then
  HOMEY_CONFIG="$TARGET/.claude/homey.json" python3 "$KIT/plugins/homey/bin/homey" upgrade || echo "homey upgrade failed: run it by hand"
fi
