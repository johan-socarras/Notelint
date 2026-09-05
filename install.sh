#!/bin/sh
# notelint installer - Linux and macOS.
#
#   curl -fsSL https://raw.githubusercontent.com/johan-socarras/notelint/main/install.sh | sh
#
# Install somewhere other than ~/knowledge-base:
#
#   curl -fsSL .../install.sh | sh -s -- ~/my-brain
#
# It creates a knowledge base that is self-contained: the tools live inside it,
# so if you later put the base in a synced folder, the tools travel with it.
#
# Nothing is downloaded outside your machine and nothing is uploaded anywhere.
# Read this file before running it - that is the whole point of piping to sh
# only after you have looked.

set -eu

REPO="johan-socarras/notelint"
BRANCH="main"
BASE="${1:-$HOME/knowledge-base}"

RED=''; GREEN=''; YELLOW=''; BLUE=''; DIM=''; OFF=''
if [ -t 1 ]; then
    RED=$(printf '\033[31m'); GREEN=$(printf '\033[32m')
    YELLOW=$(printf '\033[33m'); BLUE=$(printf '\033[36m')
    DIM=$(printf '\033[90m'); OFF=$(printf '\033[0m')
fi

say()  { printf '%s\n' "$*"; }
ok()   { printf '%s  OK  %s%s\n' "$GREEN" "$OFF" "$*"; }
warn() { printf '%s WARN %s%s\n' "$YELLOW" "$OFF" "$*"; }
die()  { printf '%s FAIL %s%s\n' "$RED" "$OFF" "$*" >&2; exit 1; }
step() { printf '\n%s=== %s ===%s\n' "$BLUE" "$*" "$OFF"; }
dim()  { printf '%s      %s%s\n' "$DIM" "$*" "$OFF"; }

say ""
say "${BLUE}  notelint - a linter for a knowledge base that does not rot${OFF}"
say ""

# --------------------------------------------------------------- requirements
step "Checking requirements"

PY=""
for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then
        if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)' 2>/dev/null; then
            PY="$c"; break
        fi
    fi
done
[ -n "$PY" ] || die "Python 3.8+ is required but was not found."
ok "$($PY --version 2>&1)"

DL=""
if command -v curl >/dev/null 2>&1; then DL="curl"
elif command -v wget >/dev/null 2>&1; then DL="wget"
else die "Need curl or wget to download."
fi
command -v tar >/dev/null 2>&1 || die "Need tar to unpack."
ok "$DL and tar available"

# ------------------------------------------------------------------- download
step "Downloading notelint"

TMP=$(mktemp -d 2>/dev/null || mktemp -d -t notelint)
trap 'rm -rf "$TMP"' EXIT INT TERM

URL="https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH"
if [ "$DL" = "curl" ]; then
    curl -fsSL "$URL" -o "$TMP/src.tar.gz" || die "Download failed: $URL"
else
    wget -qO "$TMP/src.tar.gz" "$URL" || die "Download failed: $URL"
fi
tar -xzf "$TMP/src.tar.gz" -C "$TMP" || die "Could not unpack the archive."

# Take whatever single directory the tarball unpacked into. Matching on the
# name would break the day the repository is renamed - GitHub names the
# directory after the repo, case and all.
SRC=$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -n 1)
[ -d "$SRC" ] || die "Unexpected archive layout: nothing unpacked."
[ -f "$SRC/notelint.py" ] || die "Unexpected archive layout: no notelint.py in $SRC."
ok "Downloaded"

# ----------------------------------------------------------------- the base
step "Creating the knowledge base"

if [ -e "$BASE" ] && [ -n "$(ls -A "$BASE" 2>/dev/null)" ]; then
    warn "$BASE already exists and is not empty."
    dim "Existing files are left untouched; only missing pieces are added."
else
    mkdir -p "$BASE"
    ok "Created $BASE"
fi

mkdir -p "$BASE/tools" "$BASE/templates"

for f in notelint.py tools/syncguard.py tools/power.py; do
    name=$(basename "$f")
    if [ -f "$BASE/tools/$name" ]; then
        dim "kept existing tools/$name"
    else
        cp "$SRC/$f" "$BASE/tools/$name"
        chmod +x "$BASE/tools/$name" 2>/dev/null || true
    fi
done
ok "Tools installed in $BASE/tools/"

if [ -f "$BASE/templates/note.md" ]; then
    dim "kept existing templates/note.md"
else
    cp "$SRC/templates/note.md" "$BASE/templates/"
fi

if [ -f "$BASE/PROTOCOL.md" ]; then
    dim "kept existing PROTOCOL.md"
else
    cp "$SRC/docs/PROTOCOL.md" "$BASE/PROTOCOL.md"
fi
ok "Protocol and note template in place"

# ------------------------------------------------------------- first project
FIRST="${NOTELINT_FIRST_PROJECT:-Example}"
if [ -d "$BASE/$FIRST/notes" ]; then
    dim "project '$FIRST' already exists"
else
    mkdir -p "$BASE/$FIRST/notes"
    TODAY=$($PY -c 'import datetime; print(datetime.date.today().isoformat())')
    cat > "$BASE/$FIRST/notes/what-this-project-is.md" <<EOF
---
title: What $FIRST is
type: fact
project: $FIRST
status: current
created: $TODAY
reviewed: $TODAY
expires:
evidence:
links:
  depends-on: []
  supersedes: []
  blocks: []
  related: []
---

## What this is

Replace this with one paragraph saying what $FIRST actually is, for someone who
has never seen it. Not what you plan to do with it - what it is today.

## How to verify

Say the command, the path or the screen that proves the sentence above is still
true. If you cannot name one, this note is not \`current\`: set status to
\`unverified\` and make checking it the first job.

A verification method that does not work is worse than none, because the next
reader trusts it.
EOF
    ok "First project created: $FIRST"
fi

# --------------------------------------------------------------- agent skill
step "Claude Code skill"

SKILL_SRC="$SRC/skills/notelint"
SKILL_DST="$HOME/.claude/skills/notelint"
if [ -d "$SKILL_SRC" ]; then
    if [ -d "$SKILL_DST" ]; then
        dim "skill already installed at $SKILL_DST"
    else
        mkdir -p "$HOME/.claude/skills"
        cp -R "$SKILL_SRC" "$SKILL_DST"
        ok "Skill installed at $SKILL_DST"
        dim "Claude Code will pick it up on the next session."
    fi
else
    warn "No skill directory in the archive; skipped."
fi

# -------------------------------------------------------------------- first run
step "First run"

cd "$BASE"
set +e
"$PY" tools/notelint.py .
RC=$?
set -e

say ""
if [ "$RC" -eq 1 ]; then
    dim "Exit code 1 means it found something - that is the tool working."
fi

# ------------------------------------------------------------------- what next
step "Done"
say ""
say "  Your base:  $BASE"
say ""
say "  Lint it, and regenerate INDEX.md / OPEN.md:"
say "    ${BLUE}cd $BASE && $PY tools/notelint.py .${OFF}"
say ""
say "  Just look, change nothing:"
say "    ${BLUE}$PY tools/notelint.py . --report-only${OFF}"
say ""
say "  Working from more than one machine? See docs/SYNC.md in the repo:"
say "    ${BLUE}$PY tools/syncguard.py . --status${OFF}"
say ""
say "  Next: write your first real note. Copy templates/note.md into"
say "  $FIRST/notes/ and fill it in. Then run the linter again."
say ""
