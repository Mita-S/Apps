#!/usr/bin/env bash
# Publish the standalone digit-canvas-studio repo into this repo's
# digit-canvas-studio/ subfolder, then push to GitHub.
#
# Usage:  ./publish-digit-canvas-studio.sh ["commit message"]
#
# Commit your work in the standalone repo FIRST -- subtree pulls committed
# history, so uncommitted edits there are invisible to this script.
set -euo pipefail

APPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="digit-canvas-studio"
REMOTE="dcs"
SRC="/Users/mitashah/Documents/Intellipaat/digit-canvas-studio"
cd "$APPS_DIR"

if [ -n "$(git status --porcelain)" ]; then
  echo "error: $APPS_DIR has uncommitted changes; commit or stash them first." >&2
  exit 1
fi
if [ -n "$(git -C "$SRC" status --porcelain)" ]; then
  echo "error: $SRC has uncommitted changes." >&2
  echo "       Commit them there first:  git -C \"$SRC\" commit -am 'your message'" >&2
  exit 1
fi

echo "==> pulling $PREFIX from $SRC"
git subtree pull --prefix="$PREFIX" "$REMOTE" main --squash \
  -m "${1:-Update $PREFIX}"

echo "==> pushing to GitHub"
git push origin main
echo "==> done: https://github.com/Mita-S/Apps/tree/main/$PREFIX"
