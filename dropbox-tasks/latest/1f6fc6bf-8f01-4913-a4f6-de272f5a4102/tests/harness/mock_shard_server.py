#!/usr/bin/env python3
"""TCP mock shard that answers PING with PONG and closes idle connections."""
from __future__ import annotations

import argparse
import os
import select
import socket
import sys
import threading
import time
from pathlib import Path


def handle_client(conn: socket.socket, idle_close_ms: int, close_delay_ms: int) -> None:
    conn.settimeout(idle_close_ms / 1000.0)
    last_active = time.monotonic()
    try:
        while True:
            ready, _, _ = select.select([conn], [], [], 0.1)
            if ready:
                data = conn.recv(256)
                if not data:
                    break
                if data.strip() == b"PING":
                    conn.sendall(b"PONG\n")
                last_active = time.monotonic()
            if (time.monotonic() - last_active) * 1000.0 >= idle_close_ms:
                if close_delay_ms > 0:
                    time.sleep(close_delay_ms / 1000.0)
                break
    finally:
        conn.close()


def serve(host: str, port: int, idle_close_ms: int, close_delay_ms: int) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(64)
    while True:
        conn, _ = sock.accept()
        conn.setblocking(True)
        threading.Thread(
            target=handle_client,
            args=(conn, idle_close_ms, close_delay_ms),
            daemon=True,
        ).start()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--idle-close-ms", type=int, default=200)
    parser.add_argument("--close-delay-ms", type=int, default=0)
    parser.add_argument("--pid-file", type=Path)
    args = parser.parse_args()
    if args.pid_file:
        args.pid_file.parent.mkdir(parents=True, exist_ok=True)
        args.pid_file.write_text(str(os.getpid()) + "\n")
    try:
        serve(args.host, args.port, args.idle_close_ms, args.close_delay_ms)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
