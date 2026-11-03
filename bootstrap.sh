#!/bin/sh
# Run by the agent in the folder being set up: see BOOTSTRAP.md. Installs Homey and makes the vault. Safe to rerun.
#   sh bootstrap.sh <vault folder> "<your name>" [marketplace source]
set -e
VAULT="$1"; NAME="$2"; HERE="$(cd "$(dirname "$0")" && pwd)"; SOURCE="${3:-$HERE}"
[ -n "$VAULT" ] && [ -n "$NAME" ] || { echo 'usage: sh bootstrap.sh <vault folder> "<your name>" [marketplace source]'; exit 2; }
command -v claude >/dev/null || { echo "bootstrap: Claude Code not found"; exit 1; }
command -v python3 >/dev/null || { echo "bootstrap: python3 not found"; exit 1; }
command -v obsidian >/dev/null || { echo "bootstrap: Obsidian command line not found. Homey requires Obsidian: install 1.14 or later and turn on its command line."; exit 1; }
MARKET="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["name"])' "$HERE/.claude-plugin/marketplace.json")"
mkdir -p "$VAULT"; cd "$VAULT"
claude plugin marketplace add "$SOURCE" --scope project
claude plugin install "homey@$MARKET" --scope project
python3 "$HERE/plugins/homey/scripts/homey_setup.py" --vault . --name "$NAME" --domains "${HOMEY_DOMAINS:-}" --style "${HOMEY_STYLE:-normal}"
