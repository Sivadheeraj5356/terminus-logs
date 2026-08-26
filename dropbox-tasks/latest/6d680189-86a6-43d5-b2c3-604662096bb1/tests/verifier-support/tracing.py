"""Task-owned syscall trace guard for the gaa-extract verifier.

The verifier tests are mounted read-only at /tests and the oracle solution tree
is mounted at /solution. The Cargo build and every invocation of the submitted
/app/bin/gaa-extract binary are launched through run_traced() so that neither a
build script nor the compiled binary can open the reference tests or the
oracle Rust sources, and so the isolated model-fit check can additionally
forbid re-reading raw measurement inputs.

Enforcement uses strace on the open/openat/openat2 syscalls. Each successful
open is inspected two ways: the kernel-resolved file descriptor path emitted by
`strace -y` (which already collapses symlinks and magic aliases such as
/proc/self/root) and the realpath of the raw path argument. If either resolves
inside a protected root the run is rejected.

Submitted builds and binaries run as the restricted agent uid/gid so they cannot
rewrite root-owned verifier fixtures under /opt/verifier-fixtures.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

STRACE = shutil.which("strace") or "/usr/bin/strace"
SETPRIV = shutil.which("setpriv") or "/usr/bin/setpriv"

TESTS_ROOT = "/tests"
SOLUTION_ROOT = "/solution"
BUNDLED_DATA_ROOT = "/app/data"
FIXTURE_ROOT = "/opt/verifier-fixtures"

# Shared libraries / loader paths always permitted under allowlist policies.
_SYSTEM_ALLOW_PREFIXES = (
    "/lib",
    "/lib64",
    "/usr/lib",
    "/usr/lib64",
    "/usr/local/lib",
    "/etc",
    "/proc",
    "/dev",
    "/sys",
    "/usr/share",
    "/usr/local/cargo",
    "/root/.rustup",
    "/home/agent",
    "/tmp",
    "/var/tmp",
)

# open("path" | openat(AT_FDCWD | N<dir>, "path" | openat2(..., "path"
_OPEN_LINE = re.compile(r"\bopen(?:at|at2)?\(")
_ARG_PATH = re.compile(r'"((?:[^"\\]|\\.)*)"')
_RESULT_FD = re.compile(r"=\s*(\d+)<([^>]*)>")
_DIRFD_PATH = re.compile(r"^\s*\d+<([^>]*)>")
_PID_PREFIX = re.compile(r"^(?:\[pid\s+(\d+)\]\s*|(\d+)\s+)")
_CHDIR = re.compile(r"\bchdir\(\"((?:[^\"\\]|\\.)*)\"\)\s*=\s*0")
_RENAME_LINE = re.compile(r"\b(?:rename(?:at|at2)?)\(")


@dataclass(frozen=True)
class JournalEvent:
    """One ordered open or rename syscall emitted by the traced process tree."""

    kind: str
    paths: tuple[str, ...]


class TraceViolation(RuntimeError):
    """Raised when a traced process opened a protected path."""


_DENIED_MEASUREMENT_NAMES = frozenset(
    {
        "iv_sweep.csv",
        "cv_sweep.csv",
        "geometry_manifest.json",
        "contact_resistance.json",
    }
)


@dataclass(frozen=True)
class ReadPolicy:
    """Access policy for a traced process."""

    denied_roots: tuple[str, ...] = ()
    # When set, opens must resolve under one of these prefixes (or a system
    # loader prefix). Used to enforce model-fit "tapeout + bounds only".
    allowed_prefixes: tuple[str, ...] | None = None
    deny_measurement_basenames: bool = False

    def with_allowed(self, *paths: str) -> ReadPolicy:
        """Allow exact resolved paths (parents handled as dirfd-only in is_denied)."""
        extras: list[str] = []
        for path in paths:
            if not path:
                continue
            extras.append(os.path.realpath(path))
        base = list(self.allowed_prefixes or ())
        return replace(self, allowed_prefixes=tuple(dict.fromkeys([*base, *extras])))

    def is_denied(self, resolved: str) -> bool:
        if not resolved:
            return False
        norm = os.path.realpath(resolved)
        base = os.path.basename(norm)
        if self.deny_measurement_basenames and base in _DENIED_MEASUREMENT_NAMES:
            return True
        if self.allowed_prefixes is not None:
            for prefix in _SYSTEM_ALLOW_PREFIXES:
                if norm == prefix or norm.startswith(prefix + os.sep):
                    return False
            allowed_exact = {
                os.path.realpath(allowed) for allowed in self.allowed_prefixes if allowed
            }
            if norm in allowed_exact:
                return False
            # Parent directory inode only (openat dirfd) — never all descendants,
            # so staged/renamed measurements under /app/state cannot bypass the
            # tapeout-only rule. Atomic-write temp siblings of allowed outputs are OK.
            for allowed_norm in allowed_exact:
                parent = os.path.dirname(allowed_norm)
                if not parent:
                    continue
                if norm == parent:
                    return False
                if os.path.dirname(norm) == parent and base == f".{os.path.basename(allowed_norm)}.tmp":
                    return False
            return True
        for root in self.denied_roots:
            root_norm = os.path.realpath(root)
            if norm == root_norm or norm.startswith(root_norm + os.sep):
                return True
        return False


# General policy: block mounted verifier tests and oracle solution trees.
TESTS_POLICY = ReadPolicy(denied_roots=(TESTS_ROOT, SOLUTION_ROOT))
# Model-fit isolation: allowlist filled per invoke + measurement basename denylist.
# Also denies /solution so a tapeout-only fit cannot load the oracle Rust sources.
MODEL_FIT_POLICY = ReadPolicy(
    denied_roots=(TESTS_ROOT, SOLUTION_ROOT, BUNDLED_DATA_ROOT, FIXTURE_ROOT),
    allowed_prefixes=(),
    deny_measurement_basenames=True,
)


def _unescape(raw: str) -> str:
    return raw.replace('\\"', '"').replace("\\\\", "\\")


def _resolve(base_cwd: str, dirfd_path: str | None, arg_path: str) -> str:
    if os.path.isabs(arg_path):
        return arg_path
    base = dirfd_path if dirfd_path else base_cwd
    return os.path.join(base, arg_path)


def _scan(trace_path: str, launch_cwd: str, policy: ReadPolicy) -> list[str]:
    violations: list[str] = []
    cwd_by_pid: dict[str | None, str] = {}
    with open(trace_path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            pid_match = _PID_PREFIX.match(line)
            pid = None
            body = line
            if pid_match:
                pid = pid_match.group(1) or pid_match.group(2)
                body = line[pid_match.end() :]
            cwd = cwd_by_pid.get(pid, launch_cwd)

            chdir_match = _CHDIR.search(body)
            if chdir_match:
                target = _unescape(chdir_match.group(1))
                cwd_by_pid[pid] = os.path.realpath(
                    target if os.path.isabs(target) else os.path.join(cwd, target)
                )
                continue

            if not _OPEN_LINE.search(body):
                continue

            call_start = body.index("(")
            args = body[call_start + 1 :]

            # Kernel-resolved descriptor path (handles symlinks and aliases).
            result = _RESULT_FD.search(body)
            if result and policy.is_denied(result.group(2)):
                violations.append(result.group(2))
                continue

            dirfd = _DIRFD_PATH.match(args)
            dirfd_path = dirfd.group(1) if dirfd else None
            arg = _ARG_PATH.search(args)
            if not arg:
                continue
            candidate = _resolve(cwd, dirfd_path, _unescape(arg.group(1)))
            if policy.is_denied(candidate):
                violations.append(candidate)
    return violations


def _parse_journal(trace_path: str, launch_cwd: str) -> list[JournalEvent]:
    events: list[JournalEvent] = []
    cwd_by_pid: dict[str | None, str] = {}
    with open(trace_path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            pid_match = _PID_PREFIX.match(line)
            pid = None
            body = line
            if pid_match:
                pid = pid_match.group(1) or pid_match.group(2)
                body = line[pid_match.end() :]
            cwd = cwd_by_pid.get(pid, launch_cwd)

            chdir_match = _CHDIR.search(body)
            if chdir_match:
                target = _unescape(chdir_match.group(1))
                cwd_by_pid[pid] = os.path.realpath(
                    target if os.path.isabs(target) else os.path.join(cwd, target)
                )
                continue

            if _RENAME_LINE.search(body):
                paths = [_unescape(p) for p in _ARG_PATH.findall(body)]
                resolved: list[str] = []
                for raw in paths[-2:]:
                    candidate = raw if os.path.isabs(raw) else os.path.join(cwd, raw)
                    resolved.append(os.path.realpath(candidate))
                if len(resolved) >= 2:
                    events.append(JournalEvent(kind="rename", paths=(resolved[-2], resolved[-1])))
                elif len(resolved) == 1:
                    events.append(JournalEvent(kind="rename", paths=(resolved[0],)))
                continue

            if not _OPEN_LINE.search(body):
                continue

            call_start = body.index("(")
            args = body[call_start + 1 :]
            result = _RESULT_FD.search(body)
            if result:
                events.append(
                    JournalEvent(kind="open", paths=(os.path.realpath(result.group(2)),))
                )
                continue

            dirfd = _DIRFD_PATH.match(args)
            dirfd_path = dirfd.group(1) if dirfd else None
            arg = _ARG_PATH.search(args)
            if not arg:
                continue
            candidate = _resolve(cwd, dirfd_path, _unescape(arg.group(1)))
            events.append(JournalEvent(kind="open", paths=(os.path.realpath(candidate),)))


    return events


def run_syscall_journal(
    cmd: list[str],
    *,
    cwd: str | None = None,
    env: dict | None = None,
    timeout: float | None = 120,
    as_agent: bool = True,
    policy: ReadPolicy = TESTS_POLICY,
) -> tuple[subprocess.CompletedProcess[str], list[JournalEvent]]:
    """Run cmd under strace and return ordered open/rename events plus exit status."""
    if not Path(STRACE).exists():
        raise RuntimeError(
            "strace is required by the gaa-extract trace guard but was not found"
        )
    launch_cwd = os.path.realpath(cwd) if cwd else os.getcwd()
    fd, trace_path = tempfile.mkstemp(prefix="gaa_journal_", suffix=".log", dir="/tmp")
    os.close(fd)
    wrapped = _wrap_as_agent(cmd, as_agent=as_agent)
    traced = [
        STRACE,
        "-f",
        "-qq",
        "-y",
        "-s",
        "8192",
        "-e",
        "trace=open,openat,openat2,rename,renameat,renameat2",
        "-o",
        trace_path,
        *wrapped,
    ]
    try:
        completed = subprocess.run(
            traced,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        violations = _scan(trace_path, launch_cwd, policy)
        events = _parse_journal(trace_path, launch_cwd)
    finally:
        try:
            os.unlink(trace_path)
        except OSError:
            pass
    if violations:
        raise TraceViolation(
            "traced process opened protected path(s): " + ", ".join(sorted(set(violations)))
        )
    return (
        subprocess.CompletedProcess(
            args=cmd,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        ),
        events,
    )


def assert_tapeout_committed_via_temp_rename(
    events: list[JournalEvent],
    destination: Path,
) -> None:
    """Require a rename from a sibling temp file into the tapeout destination."""
    dest = os.path.realpath(destination)
    dest_name = destination.name
    commits = [
        event
        for event in events
        if event.kind == "rename"
        and len(event.paths) == 2
        and event.paths[1] == dest
        and f".{dest_name}.tmp" in os.path.basename(event.paths[0])
    ]
    if not commits:
        rename_targets = [
            event.paths for event in events if event.kind == "rename" and event.paths
        ]
        raise AssertionError(
            "characterize must commit tapeout via rename from a .{name}.tmp sibling; "
            f"destination={dest} rename_events={rename_targets}"
        )


def assert_no_measurement_reads_after_tapeout_seal(
    events: list[JournalEvent],
    *,
    tapeout_path: Path,
    data_dir: Path,
    measurement_names: tuple[str, ...],
) -> None:
    """After the tapeout rename commit, no bundled measurement input may be reopened."""
    dest = os.path.realpath(tapeout_path)
    dest_name = tapeout_path.name
    seal_index = None
    for index, event in enumerate(events):
        if (
            event.kind == "rename"
            and len(event.paths) == 2
            and event.paths[1] == dest
            and f".{dest_name}.tmp" in os.path.basename(event.paths[0])
        ):
            seal_index = index
    if seal_index is None:
        raise AssertionError(
            f"combined run never committed tapeout via temp rename: {dest}"
        )

    data_root = os.path.realpath(data_dir)
    allowed_basenames = set(measurement_names)
    post_seal: list[str] = []
    for event in events[seal_index + 1 :]:
        if event.kind != "open" or not event.paths:
            continue
        opened = event.paths[0]
        base = os.path.basename(opened)
        if base not in allowed_basenames:
            continue
        if opened == os.path.join(data_root, base) or opened.startswith(data_root + os.sep):
            post_seal.append(opened)
    if post_seal:
        raise AssertionError(
            "model-fit stage reopened bundled measurements after tapeout seal: "
            + ", ".join(sorted(set(post_seal)))
        )


def agent_uid_gid() -> tuple[int, int]:
    uid = int(os.environ.get("TB3_AGENT_UID", "10001"))
    gid = int(os.environ.get("TB3_AGENT_GID", "10001"))
    return uid, gid


def _wrap_as_agent(cmd: list[str], *, as_agent: bool) -> list[str]:
    if not as_agent:
        return cmd
    uid, gid = agent_uid_gid()
    if Path(SETPRIV).exists():
        return [
            SETPRIV,
            f"--reuid={uid}",
            f"--regid={gid}",
            "--clear-groups",
            "--",
            *cmd,
        ]
    # Fallback: python demote helper kept next to this module.
    demote = Path(__file__).resolve().parent / "demote_exec.py"
    return [os.environ.get("TB3_PYTHON", "/opt/verifier-venv/bin/python3"), str(demote), str(uid), str(gid), "--", *cmd]


def run_traced(
    cmd: list[str],
    *,
    policy: ReadPolicy = TESTS_POLICY,
    cwd: str | None = None,
    env: dict | None = None,
    timeout: float | None = None,
    as_agent: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run cmd under strace and reject reads that resolve into protected roots."""
    if not Path(STRACE).exists():
        raise RuntimeError(
            "strace is required by the gaa-extract trace guard but was not found"
        )
    launch_cwd = os.path.realpath(cwd) if cwd else os.getcwd()
    fd, trace_path = tempfile.mkstemp(prefix="gaa_trace_", suffix=".log", dir="/tmp")
    os.close(fd)
    wrapped = _wrap_as_agent(cmd, as_agent=as_agent)
    traced = [
        STRACE,
        "-f",
        "-qq",
        "-y",
        "-s",
        "8192",
        "-e",
        "trace=open,openat,openat2",
        "-o",
        trace_path,
        *wrapped,
    ]
    try:
        completed = subprocess.run(
            traced,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        violations = _scan(trace_path, launch_cwd, policy)
    finally:
        try:
            os.unlink(trace_path)
        except OSError:
            pass
    if violations:
        raise TraceViolation(
            "traced process opened protected path(s): " + ", ".join(sorted(set(violations)))
        )
    return subprocess.CompletedProcess(
        args=cmd,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def capture_rename_targets(
    cmd: list[str],
    *,
    cwd: str | None = None,
    env: dict | None = None,
    as_agent: bool = True,
) -> list[str]:
    """Return destination paths observed in rename/renameat syscalls."""
    if not Path(STRACE).exists():
        raise RuntimeError("strace is required for atomic-write coverage")
    fd, trace_path = tempfile.mkstemp(prefix="gaa_rename_", suffix=".log", dir="/tmp")
    os.close(fd)
    wrapped = _wrap_as_agent(cmd, as_agent=as_agent)
    traced = [
        STRACE,
        "-f",
        "-qq",
        "-y",
        "-s",
        "8192",
        "-e",
        "trace=rename,renameat,renameat2",
        "-o",
        trace_path,
        *wrapped,
    ]
    try:
        completed = subprocess.run(
            traced,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        targets: list[str] = []
        with open(trace_path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not _RENAME_LINE.search(line):
                    continue
                # Prefer kernel-resolved destination fd path when present.
                # rename("/tmp/.x.tmp", "/app/state/calibration_tapeout.json") = 0
                # renameat(..., "...tmp" -> "...json") shapes also appear.
                paths = _ARG_PATH.findall(line)
                if len(paths) >= 2:
                    targets.append(_unescape(paths[-1]))
                fd_paths = re.findall(r"<([^>]+)>", line)
                if fd_paths:
                    targets.append(fd_paths[-1])
    finally:
        try:
            os.unlink(trace_path)
        except OSError:
            pass
    if completed.returncode != 0:
        raise RuntimeError(
            f"rename trace command failed rc={completed.returncode}: {completed.stderr}"
        )
    return targets


