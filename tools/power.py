#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
power - shut down or suspend the machine after a countdown you can still cancel.

Written for the case where you tell an agent "when you finish, shut down the
computer". The agent runs one command and walks away; you keep a window in which
nothing has happened yet and Ctrl+C still takes it back.

    python tools/power.py shutdown              shut down in 60s
    python tools/power.py suspend --in 30       sleep in 30s
    python tools/power.py shutdown --in 0       immediately, no countdown
    python tools/power.py shutdown --dry-run    say what it would do, do nothing
    python tools/power.py cancel                cancel a shutdown already queued

Close applications first, so unsaved work is not lost to a forced kill:

    python tools/power.py shutdown --close code,chrome

The countdown runs inside this process, which is what makes it behave the same
on Windows, Linux and macOS: cancelling is always Ctrl+C or closing the window.
`cancel` is only for a shutdown queued through the OS scheduler by something
else.

No dependencies. Python 3.8+.
"""
import argparse
import platform
import shutil
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SYSTEM = platform.system()


def run(cmd, dry):
    if dry:
        print("  [dry-run] " + " ".join(cmd))
        return 0
    try:
        return subprocess.run(cmd, check=False).returncode
    except FileNotFoundError:
        print("  Command not found: " + cmd[0])
        return 127


def close_apps(names, dry):
    """Ask applications to close before the machine goes down."""
    for name in names:
        name = name.strip()
        if not name:
            continue
        if SYSTEM == "Windows":
            # /IM matches the image name; taskkill without /F asks politely first.
            target = name if name.lower().endswith(".exe") else name + ".exe"
            cmd = ["taskkill", "/IM", target]
        else:
            cmd = ["pkill", "-x", name]
        print("  closing " + name)
        run(cmd, dry)


def shutdown_command():
    if SYSTEM == "Windows":
        return ["shutdown", "/s", "/t", "0"]
    if SYSTEM == "Darwin":
        return ["osascript", "-e", 'tell application "System Events" to shut down']
    # Linux and the BSDs: logind handles this without root on a normal desktop.
    if shutil.which("systemctl"):
        return ["systemctl", "poweroff"]
    return ["shutdown", "-h", "now"]


def suspend_command():
    if SYSTEM == "Windows":
        # Note: if hibernation is enabled, Windows hibernates instead of sleeping.
        # Turn it off with `powercfg -h off` if you want true sleep.
        return ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]
    if SYSTEM == "Darwin":
        return ["pmset", "sleepnow"]
    if shutil.which("systemctl"):
        return ["systemctl", "suspend"]
    return ["pm-suspend"]


def cancel_queued(dry):
    """Cancel a shutdown queued with the OS scheduler (not one of ours)."""
    if SYSTEM == "Windows":
        code = run(["shutdown", "/a"], dry)
    elif shutil.which("shutdown"):
        code = run(["shutdown", "-c"], dry)
    else:
        print("  Nothing to cancel on this platform.")
        return 0
    if code == 0:
        print("  Cancelled.")
    else:
        print("  Nothing was queued (or it was queued by this script - use Ctrl+C).")
    return 0


def countdown(seconds, action):
    if seconds <= 0:
        return True
    print("  Ctrl+C cancels. Nothing has happened yet.")
    print("")
    try:
        for left in range(seconds, 0, -1):
            sys.stdout.write("\r  " + action + " in " + str(left) + "s...   ")
            sys.stdout.flush()
            time.sleep(1)
        print("")
        return True
    except KeyboardInterrupt:
        print("")
        print("  Cancelled. The machine stays on.")
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="power",
        description="Shut down or suspend after a countdown you can cancel.")
    ap.add_argument("action", choices=["shutdown", "suspend", "cancel"])
    ap.add_argument("--in", dest="delay", type=int, default=60, metavar="SEC",
                    help="seconds before acting (default 60; 0 acts at once)")
    ap.add_argument("--close", default="", metavar="A,B",
                    help="comma-separated apps to close first")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would happen, change nothing")
    a = ap.parse_args(argv)

    print("")
    if a.dry_run:
        print("  DRY RUN - nothing will actually happen.")

    if a.action == "cancel":
        return cancel_queued(a.dry_run)

    verb = "Shutting down" if a.action == "shutdown" else "Suspending"
    print("  " + verb + " this machine (" + SYSTEM + ")")
    if a.close:
        print("  Will close first: " + a.close)
    print("")

    if not countdown(a.delay, verb):
        return 130

    if a.close:
        close_apps(a.close.split(","), a.dry_run)
        # Give windows a moment to flush anything they were saving.
        if not a.dry_run:
            time.sleep(3)

    cmd = shutdown_command() if a.action == "shutdown" else suspend_command()
    print("  " + " ".join(cmd))
    code = run(cmd, a.dry_run)
    if code not in (0, None) and not a.dry_run:
        print("")
        print("  That returned " + str(code) + ". On some Linux setups you need")
        print("  a polkit rule, or run it with sudo.")
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  Cancelled.")
        sys.exit(130)
