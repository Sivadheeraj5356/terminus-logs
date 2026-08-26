"""Stop any Django runserver processes in the container."""

from __future__ import annotations

import os
import signal
import socket
import time


def _port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def main() -> None:
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        cmdline_path = f"/proc/{pid}/cmdline"
        try:
            with open(cmdline_path, encoding="utf-8", errors="ignore") as handle:
                cmdline = handle.read().replace("\x00", " ")
        except OSError:
            continue
        if "manage.py" in cmdline and "runserver" in cmdline:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass

    time.sleep(1)
    for _ in range(20):
        if not _port_is_open("127.0.0.1", 8000):
            return
        time.sleep(0.5)

    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        cmdline_path = f"/proc/{pid}/cmdline"
        try:
            with open(cmdline_path, encoding="utf-8", errors="ignore") as handle:
                cmdline = handle.read().replace("\x00", " ")
        except OSError:
            continue
        if "manage.py" in cmdline and "runserver" in cmdline:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    time.sleep(1)


if __name__ == "__main__":
    main()
