# Working from more than one machine

**This is optional.** If you work from one computer, skip this file entirely.
Nothing in notelint depends on it, and `notelint.py` never imports `syncguard.py`.

If you do work from two or three machines, the failure you will hit is not the
one you expect. It is not losing the base. It is this:

> You open the laptop and start writing before the sync client finished pulling
> what you did on the desktop last night. Now you have edited a stale version.
> The client resolves that by leaving two files with `conflicted copy` in the
> name, and your knowledge base quietly grows a second truth.

Waiting "a few minutes" is guessing, and it fails on the day the sync took six.
`tools/syncguard.py` replaces the guess with a check.

## How the guard works

When you finish working on a machine, it writes `.sync/<hostname>.json` holding a
hash of every note in the base. When you start on another machine, it recomputes
that hash locally and compares.

Same hash means the sync really landed. Different hash means it has not arrived
yet, so you should wait rather than write.

```sh
python tools/syncguard.py . --status     # what every machine last reported
python tools/syncguard.py . --check      # exit 0 if up to date, 1 if not
python tools/syncguard.py . --wait 180   # block until it lands, or give up
python tools/syncguard.py . --stamp      # "I finished here" - run when done
```

The important design point: **the check lives on the receiving side.** You never
have to prove the other machine finished uploading. The machine you sit down at
tells you whether everything arrived.

The hash normalises line endings, so a base edited on Windows and on Linux
produces the same value for the same content.

## Which sync tool to use

The guard does not care. It compares content, so anything that eventually makes
two folders match will work. Pick whichever suits you:

| Tool | Good for | Watch out for |
|---|---|---|
| **OneDrive / Dropbox / Drive** | The other machine can be off; the cloud is the middleman | No official OneDrive client for Linux — use [abraunegg/onedrive](https://github.com/abraunegg/onedrive) |
| **Syncthing** | Nothing leaves your network, end-to-end encrypted | Peer to peer: needs a machine that is always on, or the two never meet |
| **A git remote** | Real merges instead of conflict copies, plus history | You have to pull and push; put the base in a private repo if it is not public |
| **rsync over SSH / a NAS** | Full control, no third party | Only works when both ends are reachable |

A note on Syncthing, because it is the one people reach for when they want
everything to stay in their own network: it is genuinely peer to peer, which
means if the desktop is off, the laptop syncs with nothing. Two laptops that are
never on at the same time never converge. If you want "nothing leaves my
network" **and** "the other machine can be off", you need something always on —
a Raspberry Pi or a NAS running Syncthing costs a few watts and solves it.

## Configuration

Everything is optional. Create `.sync/config.json` in the base:

```json
{
  "enabled": true,
  "machines": ["desktop", "laptop"],
  "skip": ["Archive", "big-media"]
}
```

**`enabled`** — set it to `false` and the guard becomes a no-op that always
succeeds. Useful when you have the hook wired up but are working from one
machine for a while, or when you want the tool present but silent.

**`machines`** — only these hostnames count. Have three machines but only sync
two? List the two. An unlisted machine still gets stamped, still shows up in
`--status` marked `[-]`, and never blocks you.

**`skip`** — extra directory names left out of the hash.

> **The one rule that matters:** whatever you exclude from syncing must also be
> in `skip`. If one machine hashes files the other machine does not have, the two
> hashes can never match and the guard will block you forever. Keep the excluded
> set and the skipped set identical.

## Wiring it into an agent

If you use Claude Code, a `SessionStart` hook makes the guard run itself, so the
agent cannot start writing into a half-synced base. In `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/base/tools/syncguard.py /path/to/base --wait 180"
          }
        ]
      }
    ]
  }
}
```

And when you finish, `--stamp` records where you left off. If you also use
`tools/power.py` to shut the machine down at the end of a session, stamp first:

```sh
python tools/syncguard.py . --stamp && python tools/power.py shutdown --in 60
```

That ordering matters. The stamp is the last thing written, so it is the last
thing uploaded — which is what makes "the stamp arrived" a good proxy for
"everything arrived".

## Things that will bite you

**Editing on two machines at once.** The guard detects a stale base; it does not
prevent two people (or two of your own sessions) writing simultaneously. If you
want real merges rather than conflict copies, use git as the transport.

**Virtual machines and snapshots.** If you are trying a distro in a VM, do not
point a two-way sync at your real account. Use a download-only mode while you
evaluate. Restoring a VM snapshot leaves the sync client's local database out of
step with the server, and some clients resolve that by deleting — which then
propagates. Resync from scratch after any snapshot restore.

**Files-on-demand / online-only placeholders.** OneDrive on Windows and similar
features elsewhere leave zero-byte stubs that are downloaded on first read. The
guard treats an unreadable file as "not ready", which is the correct answer, but
if your whole base is placeholders you will want to pin it as always-available.

**Dual boot on one disk.** Mounting the Windows partition from Linux to reach the
same folder looks tempting and mostly is not worth it: full-disk encryption gets
in the way, placeholders do not hydrate, and it does nothing for the case where
the other machine is a different computer. Sync both sides independently instead.

## Making it yours

None of this is fixed. The guard is one file, about 250 lines, no dependencies —
readable in a sitting. If you want a different hashing scheme, a different stamp
format, a lock file, integration with your own sync tool, or a check that also
verifies the linter passes before stamping, change it.

That is the point of it being here rather than in a service you cannot open. Ask
whatever AI assistant you use to modify it for you — the file is small enough to
hand over whole, and the tests in `tests/` will tell you if you broke something.
