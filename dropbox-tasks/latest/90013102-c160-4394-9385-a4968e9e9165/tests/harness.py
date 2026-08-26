"""Harness helpers for isolated proxy/backend subprocess cases."""

from __future__ import annotations

import json
import shutil
import signal
import socket
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APP = Path("/app")
PROXY_BIN = APP / "bin" / "proxy-local"
BACKEND_BIN = APP / "bin" / "backend-capture"
TRACE_PATH = Path("/output/request-trace.json")
DEFAULT_TIMEOUT = 30.0


@dataclass
class CaseContext:
    test_name: str
    root: Path = field(init=False)
    proxy_sock: Path = field(init=False)
    backend_sock: Path = field(init=False)
    ready_file: Path = field(init=False)
    state_dir: Path = field(init=False)
    capture_path: Path = field(init=False)
    audit_log: Path = field(init=False)
    config_path: Path = field(init=False)
    profiles_dir: Path = field(init=False)
    keyring_path: Path = field(init=False)
    _backend_proc: subprocess.Popen[bytes] | None = field(default=None, init=False, repr=False)
    _proxy_proc: subprocess.Popen[bytes] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        safe = self.test_name.replace("/", "_")
        self.root = Path(f"/tmp/verifier/{safe}")
        self.proxy_sock = self.root / "proxy.sock"
        self.backend_sock = self.root / "backend.sock"
        self.ready_file = self.root / "proxy.ready"
        self.state_dir = self.root / "state"
        self.capture_path = self.root / "backend-capture.json"
        self.audit_log = self.root / "audit.jsonl"
        self.config_path = self.root / "proxy.json"
        self.profiles_dir = self.root / "profiles"
        self.keyring_path = self.root / "keyring.json"

    def prepare_dirs(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "spool").mkdir(parents=True, exist_ok=True)
        self._clear_shared_outputs()

    def _clear_shared_outputs(self) -> None:
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        if TRACE_PATH.exists():
            TRACE_PATH.unlink()
        if self.capture_path.exists():
            self.capture_path.unlink()
        if self.audit_log.exists():
            self.audit_log.unlink()

    def start_backend(self) -> None:
        if self.backend_sock.exists():
            self.backend_sock.unlink()
        self._backend_proc = subprocess.Popen(
            [
                str(BACKEND_BIN),
                "--listen-unix",
                str(self.backend_sock),
                "--output",
                str(self.capture_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        self._wait_for_socket(self.backend_sock)

    def start_proxy(
        self,
        *,
        replay_on_start: bool = False,
        backend_online: bool = True,
    ) -> None:
        if not backend_online and self.backend_sock.exists():
            self.backend_sock.unlink()
        elif backend_online and self._backend_proc is None:
            self.start_backend()

        if self.proxy_sock.exists():
            self.proxy_sock.unlink()
        if self.ready_file.exists():
            self.ready_file.unlink()

        cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
        cfg["replay_on_start"] = replay_on_start
        self.config_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

        self._proxy_proc = subprocess.Popen(
            [
                str(PROXY_BIN),
                "serve",
                "--listen-unix",
                str(self.proxy_sock),
                "--backend-unix",
                str(self.backend_sock),
                "--config",
                str(self.config_path),
                "--profiles",
                str(self.profiles_dir),
                "--keyring",
                str(self.keyring_path),
                "--state-dir",
                str(self.state_dir),
                "--audit-log",
                str(self.audit_log),
                "--trace",
                str(TRACE_PATH),
                "--ready-file",
                str(self.ready_file),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            cwd=str(APP),
        )
        self._wait_for_ready()

    def run_recover(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(PROXY_BIN),
                "recover",
                "--backend-unix",
                str(self.backend_sock),
                "--config",
                str(self.config_path),
                "--profiles",
                str(self.profiles_dir),
                "--keyring",
                str(self.keyring_path),
                "--state-dir",
                str(self.state_dir),
                "--audit-log",
                str(self.audit_log),
                "--trace",
                str(TRACE_PATH),
            ],
            cwd=str(APP),
            text=True,
            capture_output=True,
            check=False,
            timeout=DEFAULT_TIMEOUT,
        )

    def send_raw(self, payload: bytes, *, timeout: float = 5.0) -> bytes:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(str(self.proxy_sock))
            sock.sendall(payload)
            chunks: list[bytes] = []
            while True:
                try:
                    part = sock.recv(65536)
                except socket.timeout:
                    break
                if not part:
                    break
                chunks.append(part)
                joined = b"".join(chunks)
                if b"\r\n\r\n" in joined:
                    header, rest = joined.split(b"\r\n\r\n", 1)
                    cl = None
                    for line in header.split(b"\r\n"):
                        if line.lower().startswith(b"content-length:"):
                            cl = int(line.split(b":", 1)[1].strip())
                            break
                    if cl is None:
                        if b"transfer-encoding: chunked" in header.lower():
                            if joined.endswith(b"0\r\n\r\n"):
                                break
                        else:
                            break
                    elif len(rest) >= cl:
                        break
            return b"".join(chunks)

    def read_trace(self) -> dict[str, Any]:
        if not TRACE_PATH.is_file():
            raise FileNotFoundError(f"trace file missing: {TRACE_PATH}")
        return json.loads(TRACE_PATH.read_text(encoding="utf-8"))

    def read_audit_lines(self) -> list[dict[str, Any]]:
        if not self.audit_log.is_file():
            return []
        lines = []
        for line in self.audit_log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                lines.append(json.loads(line))
        return lines

    def spool_records(self) -> list[Path]:
        spool = self.state_dir / "spool"
        if not spool.is_dir():
            return []
        return sorted(spool.glob("*.json"))

    def stop_proxy(self, *, grace: float = 1.0) -> None:
        if self._proxy_proc is None:
            return
        if self._proxy_proc.poll() is None:
            self._proxy_proc.send_signal(signal.SIGTERM)
            try:
                self._proxy_proc.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                self._proxy_proc.kill()
                self._proxy_proc.wait(timeout=grace)
        self._proxy_proc = None

    def stop_backend(self, *, grace: float = 1.0) -> None:
        if self._backend_proc is None:
            return
        if self._backend_proc.poll() is None:
            self._backend_proc.send_signal(signal.SIGTERM)
            try:
                self._backend_proc.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                self._backend_proc.kill()
                self._backend_proc.wait(timeout=grace)
        self._backend_proc = None

    def cleanup(self) -> None:
        self.stop_proxy()
        self.stop_backend()
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)

    def _wait_for_ready(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.ready_file.is_file() and self._proxy_proc and self._proxy_proc.poll() is None:
                return
            if self._proxy_proc and self._proxy_proc.poll() is not None:
                stderr = self._proxy_proc.stderr.read().decode() if self._proxy_proc.stderr else ""
                raise RuntimeError(f"proxy exited early: {stderr}")
            time.sleep(0.05)
        raise TimeoutError(f"proxy ready file not created: {self.ready_file}")

    def _wait_for_socket(self, path: Path, timeout: float = DEFAULT_TIMEOUT) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if path.exists():
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                        sock.settimeout(0.2)
                        sock.connect(str(path))
                        return
                except OSError:
                    pass
            time.sleep(0.05)
        raise TimeoutError(f"unix socket not ready: {path}")


def response_status(raw: bytes) -> int:
    line = raw.split(b"\r\n", 1)[0].decode("latin-1", errors="replace")
    parts = line.split()
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])
    return 0


def response_json(raw: bytes) -> dict[str, Any]:
    if b"\r\n\r\n" not in raw:
        return {}
    body = raw.split(b"\r\n\r\n", 1)[1]
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}
