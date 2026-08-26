#!/usr/local/bin/python3
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path


NOBODY = 65534
PR_SET_NO_NEW_PRIVS = 38


def child_status(source: Path, executable: Path) -> int:
    pid = os.fork()
    if pid == 0:
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error))
            os.setgroups([])
            os.setgid(NOBODY)
            os.setuid(NOBODY)
            os.chdir("/tmp")
            os.execve(
                "/usr/bin/gcc",
                [
                    "gcc",
                    "-std=c11",
                    "-O2",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    str(source),
                    "-o",
                    str(executable),
                ],
                {
                    "HOME": "/tmp",
                    "LANG": "C.UTF-8",
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "TMPDIR": "/tmp",
                },
            )
        except BaseException as error:
            print(f"unprivileged compiler launch failed: {error}", file=sys.stderr)
            os._exit(127)
    _, status_value = os.waitpid(pid, 0)
    if os.WIFEXITED(status_value):
        return os.WEXITSTATUS(status_value)
    return 128 + os.WTERMSIG(status_value)


def main() -> int:
    if len(sys.argv) != 3:
        return 2
    source = Path(sys.argv[1]).resolve()
    executable = Path(sys.argv[2]).resolve()
    executable.unlink(missing_ok=True)
    return child_status(source, executable)


if __name__ == "__main__":
    raise SystemExit(main())
