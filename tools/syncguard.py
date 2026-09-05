#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
syncguard - know whether your knowledge base finished syncing before you write.

The problem: you keep the base in a synced folder (OneDrive, Dropbox, Drive,
Syncthing, a network share) so you can work from more than one machine. You open
the laptop and start editing before the sync client finished pulling what you did
on the desktop. Now you have written on top of a stale version, and the client
resolves it by leaving two files with "conflicted copy" in the name.

Waiting "a few minutes" is guessing. This checks.

How it works: when you finish on a machine, it writes .sync/<host>.json holding a
hash of every note in the base. When you start on another machine, it recomputes
that hash locally and compares. Same hash means the sync really did land. A
different hash means it has not arrived yet - so wait, do not write.

The hash normalises line endings, so Windows and Linux agree on identical content.

    python tools/syncguard.py --check          exit 0 if up to date, 1 if not
    python tools/syncguard.py --wait 180       block until it lands (or time out)
    python tools/syncguard.py --stamp          "I finished here" (run when done)
    python tools/syncguard.py --status         show every machine's stamp

Point it somewhere else with a path:

    python tools/syncguard.py /path/to/base --check

Wire --wait into a session hook and the guard runs itself. See docs/SYNC.md.

ENTIRELY OPTIONAL. If you work from one machine, you never need this file. It
is not wired into notelint and notelint does not import it.

It also does not care which sync client you use - OneDrive, Dropbox, Drive,
Syncthing, a git remote, rsync over SSH, a NAS. It only compares content, so
anything that eventually makes two folders match will work.

Configure it with .sync/config.json, all keys optional:

    {
      "enabled": true,
      "machines": ["desktop", "laptop"],
      "skip": ["Archive", "big-media"]
    }

  enabled   false turns the guard into a no-op that always succeeds, so you can
            leave the hook wired up and switch the behaviour off.
  machines  only these hostnames count. Have three machines but only sync two?
            List the two. An unlisted machine is ignored by --check and never
            blocks you.
  skip      extra directory names to leave out of the hash. Whatever you exclude
            from syncing must be listed here too, or the two machines hash
            different sets of files and never agree.

No dependencies. Python 3.8+.
"""
import argparse
import hashlib
import json
import platform
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

STAMP_DIR = ".sync"

# Never hashed: regenerable, machine-local, or excluded from syncing anyway.
# Anything listed here must ALSO be excluded from your sync client, or the two
# machines will hash different sets of files and never agree.
SKIP = {
    STAMP_DIR, ".git", ".github", "__pycache__", ".pytest_cache", ".mypy_cache",
    "node_modules", "target", ".venv", "venv", "dist", "build", ".idea", ".vscode",
}

# Sync clients name their conflict files in predictable ways. A conflict copy is
# not part of the base: counting it would make the hash differ forever.
CONFLICT_MARKERS = (
    "conflicted copy",        # Dropbox
    "conflicto",              # OneDrive, Spanish
    "copia en conflicto",     # OneDrive, Spanish
    "sync-conflict",          # Syncthing
    "(case conflict)",
)


def load_config(base: Path) -> dict:
    """Read .sync/config.json. Every key is optional; absent means defaults."""
    f = base / STAMP_DIR / "config.json"
    if not f.is_file():
        return {}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("Warning: " + str(f) + " is not valid JSON; ignoring it.",
              file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def skip_set(cfg: dict) -> set:
    extra = cfg.get("skip") or []
    if isinstance(extra, str):
        extra = [extra]
    return SKIP | {str(x) for x in extra}


def is_skipped(rel: Path, skip: set) -> bool:
    return any(part in skip for part in rel.parts)


def is_conflict_copy(name: str) -> bool:
    low = name.lower()
    return any(marker in low for marker in CONFLICT_MARKERS)


def notes_in(base: Path, skip: set):
    """Every markdown file that makes up the base, in a stable order."""
    found = []
    for path in base.rglob("*.md"):
        rel = path.relative_to(base)
        if is_skipped(rel, skip) or is_conflict_copy(path.name):
            continue
        found.append(rel)
    # Sort on an explicit "/" key so Windows and POSIX produce the same order.
    return sorted(found, key=lambda r: "/".join(r.parts).lower())


def hash_base(base: Path, cfg=None):
    """A single hash over every note. Returns (hex digest, note count)."""
    cfg = {} if cfg is None else cfg
    acc = hashlib.sha256()
    found = notes_in(base, skip_set(cfg))
    for rel in found:
        key = "/".join(rel.parts)
        try:
            raw = (base / rel).read_bytes()
        except OSError:
            # A file the sync client has not hydrated yet counts as "not ready".
            raw = b"<UNREADABLE>"
        # Normalise line endings: CRLF and LF must hash the same.
        acc.update(key.encode("utf-8"))
        acc.update(b"\0")
        acc.update(hashlib.sha256(raw.replace(b"\r\n", b"\n")).digest())
    return acc.hexdigest(), len(found)


def machine_name() -> str:
    raw = socket.gethostname().split(".")[0]
    clean = "".join(c if c.isalnum() or c in "-_" else "-" for c in raw)
    return clean or "unknown"


def read_stamps(base: Path):
    d = base / STAMP_DIR
    if not d.is_dir():
        return []
    out = []
    for f in d.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("hash"):
            out.append(data)
    return sorted(out, key=lambda d: d.get("utc", ""), reverse=True)


def counted_machines(cfg: dict):
    """Hostnames whose stamps count, or None meaning 'all of them'."""
    listed = cfg.get("machines")
    if not listed:
        return None
    if isinstance(listed, str):
        listed = [listed]
    return {str(m).lower() for m in listed}


def stamp(base: Path, cfg=None, quiet=False):
    cfg = {} if cfg is None else cfg
    d = base / STAMP_DIR
    d.mkdir(parents=True, exist_ok=True)
    digest, count = hash_base(base, cfg)
    me = machine_name()
    record = {
        "machine": me,
        "system": platform.system(),
        "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hash": digest,
        "notes": count,
    }
    (d / (me + ".json")).write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8")
    if not quiet:
        print("Stamped " + me + " - " + str(count) + " notes - " + digest[:16] + "...")
    return record


def check(base: Path, cfg=None):
    """Returns (up_to_date, message)."""
    cfg = {} if cfg is None else cfg

    # Switched off on purpose: succeed without looking, so a wired-up hook
    # costs nothing for someone who works from a single machine.
    if cfg.get("enabled") is False:
        return True, "Sync guard disabled in .sync/config.json."

    digest, count = hash_base(base, cfg)
    me = machine_name()
    only = counted_machines(cfg)

    others = []
    for s in read_stamps(base):
        name = str(s.get("machine", ""))
        if name == me:
            continue
        # An unlisted machine never blocks you: that is how you sync two of
        # three machines and let the third drift on purpose.
        if only is not None and name.lower() not in only:
            continue
        others.append(s)

    if not others:
        return True, "No stamps from other machines yet (first run here)."

    last = others[0]
    if last.get("hash") == digest:
        return True, ("Up to date with " + str(last.get("machine"))
                      + " (" + str(count) + " notes).")

    return False, ("OUT OF SYNC. " + str(last.get("machine")) + " left "
                   + str(last.get("notes", "?")) + " notes at " + str(last.get("utc"))
                   + "; this machine has " + str(count)
                   + " and the hash differs. The sync has not landed yet.")


def wait(base: Path, limit: int, cfg=None) -> int:
    cfg = {} if cfg is None else cfg
    start = time.monotonic()
    spun = False
    while True:
        ok, message = check(base, cfg)
        if ok:
            if spun:
                print("")
            print("OK - " + message)
            return 0
        elapsed = time.monotonic() - start
        if elapsed >= limit:
            print("")
            print("TIMED OUT after " + str(limit) + "s.")
            print(message)
            print("")
            print("Check that your sync client is actually running, then either")
            print("wait longer or resolve it by hand before writing.")
            return 1
        spun = True
        sys.stdout.write("\rWaiting for sync... "
                         + str(int(limit - elapsed)) + "s left   ")
        sys.stdout.flush()
        time.sleep(5)


def status(base: Path, cfg=None):
    cfg = {} if cfg is None else cfg
    digest, count = hash_base(base, cfg)
    only = counted_machines(cfg)

    print("Base:  " + str(base))
    print("Here:  " + machine_name() + " - " + str(count) + " notes - "
          + digest[:16] + "...")
    if cfg.get("enabled") is False:
        print("Guard: disabled in .sync/config.json (checks always pass)")
    if only is not None:
        print("Guard: only counting " + ", ".join(sorted(only)))
    print("")

    stamps = read_stamps(base)
    if not stamps:
        print("No stamps yet. Run --stamp when you finish working.")
        return
    print("Stamps (most recent first):")
    for s in stamps:
        name = str(s.get("machine"))
        if s.get("hash") == digest:
            mark = "="
        elif only is not None and name.lower() not in only and name != machine_name():
            mark = "-"
        else:
            mark = "!"
        print("  [" + mark + "] " + name.ljust(16)
              + str(s.get("system", "?")).ljust(9) + str(s.get("utc"))
              + "  " + str(s.get("notes")) + " notes")
    print("")
    print("  [=] matches what is on disk here")
    print("  [!] that machine has something this one has not received yet")
    if only is not None:
        print("  [-] not in 'machines', so it never blocks you")


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="syncguard",
        description="Verify a synced knowledge base is up to date before writing.")
    ap.add_argument("base", nargs="?", default=".", help="base directory (default: .)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="exit 0 if up to date")
    g.add_argument("--stamp", action="store_true", help="record this machine's state")
    g.add_argument("--status", action="store_true", help="show all stamps")
    g.add_argument("--wait", type=int, nargs="?", const=180, metavar="SEC",
                   help="block until the sync lands (default 180s)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    base = Path(a.base).resolve()
    if not base.is_dir():
        print("Not a directory: " + str(base))
        return 2

    cfg = load_config(base)

    if a.stamp:
        stamp(base, cfg, quiet=a.quiet)
        return 0
    if a.status:
        status(base, cfg)
        return 0
    if a.wait is not None:
        return wait(base, a.wait, cfg)

    ok, message = check(base, cfg)
    if not a.quiet:
        print(("OK - " if ok else "WARN - ") + message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
