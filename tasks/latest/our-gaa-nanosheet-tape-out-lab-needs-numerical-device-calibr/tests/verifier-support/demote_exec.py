#!/usr/bin/env python3
"""Drop privileges then exec a command (fallback when setpriv is unavailable)."""

from __future__ import annotations

import os
import sys


def main() -> int:
    if len(sys.argv) < 5 or "--" not in sys.argv:
        print("usage: demote_exec.py UID GID -- CMD [ARGS...]", file=sys.stderr)
        return 2
    sep = sys.argv.index("--")
    uid = int(sys.argv[1])
    gid = int(sys.argv[2])
    cmd = sys.argv[sep + 1 :]
    if not cmd:
        print("demote_exec: missing command", file=sys.stderr)
        return 2
    os.setgid(gid)
    os.setuid(uid)
    os.execvp(cmd[0], cmd)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
