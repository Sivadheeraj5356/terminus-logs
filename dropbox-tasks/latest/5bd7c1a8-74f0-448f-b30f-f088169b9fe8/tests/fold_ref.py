"""Reference helpers for stratified fold assembler verifier."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

STOCK_DATASET = Path("/app/fixtures/datasets/cohort.csv")
STOCK_FOLDS = 5
STOCK_LABEL = "strata"
MANIFEST_PATH = Path("/app/var/fold_manifest.json")
RECEIPT_PATH = Path("/app/var/fold_receipt.jsonl")
WORK_DIR = Path("/app/var/fold_work")
STAGED_PATH = WORK_DIR / "cohort_staged.csv"
STAGE_SCRIPT = Path("/app/scripts/stage_cohort.sh")
JAVA_BIN = Path("/opt/java/openjdk/bin/java")
ASSEMBLE_JAR = Path("/app/target/fold-assembler-1.0.0.jar")
FOLDCTL = Path("/app/bin/foldctl")
PUBLIC_POM = Path("/app/pom.xml")
# Primary assemble runner: verifier-built jar via Java (safe rebuild in test.sh).
BIN = [str(JAVA_BIN), "-jar", str(ASSEMBLE_JAR), "assemble"]
# Public CLI documented in instruction.md — exercised once under the same guard.
BIN_FOLDCTL = [str(FOLDCTL), "assemble"]


_TRACE_DIR = Path("/logs/verifier")
_TESTS_DIR = Path("/tests")
_SOLUTION_DIR = Path("/solution")
_FORBIDDEN_READ_RETURNCODE = 125
_MISSING_WORKFLOW_RETURNCODE = 126
_STAGE_SCRIPT_ABS = "/app/scripts/stage_cohort.sh"
_BALANCE_SCRIPT_ABS = "/app/r/fold_balance.R"
_REQUIRED_WORKFLOWS = (
    {
        "label": "stage_cohort.sh",
        "script": _STAGE_SCRIPT_ABS,
        "interpreters": frozenset({"bash", "sh"}),
        "script_argv_index": 1,
        "allow_direct_script_exec": True,
    },
    {
        "label": "fold_balance.R",
        "script": _BALANCE_SCRIPT_ABS,
        "interpreters": frozenset({"Rscript"}),
        "script_argv_index": 1,
        "allow_direct_script_exec": False,
    },
)
_FORBIDDEN_PATH_PREFIXES = (
    "/tests",
    "/.verifier_tests_hidden",
    "/solution",
)
_PROC_ROOT_RE = re.compile(r"^/proc/(?:self|\d+)/root(?P<rest>/.*)?$")
_STRACE_PATH_RE = re.compile(r'"((?:\\.|[^"\\])*)"')
_PID_PREFIX_RE = re.compile(r"^(?:\[pid\s+(?P<br>\d+)\]\s+|(?P<plain>\d+)\s+)")
_EXECVE_RE = re.compile(
    r"^(?:\[pid\s+(?P<br>\d+)\]\s+|(?P<plain>\d+)\s+)?"
    r"execve(?:at)?\("
)
_EXITED_RE = re.compile(
    r"^(?:\[pid\s+(?P<br>\d+)\]\s+|(?P<plain>\d+)\s+)?"
    r"\+\+\+\s+exited with (?P<code>\d+)\s+\+\+\+"
)
_EXIT_GROUP_RE = re.compile(
    r"^(?:\[pid\s+(?P<br>\d+)\]\s+|(?P<plain>\d+)\s+)?"
    r"exit_group\((?P<code>\d+)\)"
)
_SYSCALL_RE = re.compile(
    r"\b(?P<call>open(?:at2?)?|creat|name_to_handle_at|"
    r"stat(?:x)?|lstat|fstatat(?:64)?|newfstatat|"
    r"access|faccessat(?:2)?|"
    r"readlink(?:at)?|"
    r"execve(?:at)?|fexecve|"
    r"chdir|fchdir|"
    r"getxattr|lgetxattr|listxattr|llistxattr|"
    r"open_by_handle_at|"
    r"clone(?:3)?|fork|vfork)\b"
)
_AT_FDCWD = frozenset({"AT_FDCWD", "-100"})


def _scrubbed_subprocess_env() -> dict[str, str]:
    """Drop PYTHONPATH so submitted processes cannot import verifier modules."""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return env


def _unescape_strace_path(raw: str) -> str:
    return (
        raw.replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )


def _decode_strace_path(raw: str) -> str:
    path = _unescape_strace_path(raw)
    match = _PROC_ROOT_RE.match(path)
    if match:
        rest = match.group("rest")
        path = rest if rest else "/"
    return path


def _is_forbidden_resolved(path: str) -> bool:
    try:
        resolved = str(Path(path).resolve())
    except OSError:
        resolved = os.path.normpath(path)
    for prefix in _FORBIDDEN_PATH_PREFIXES:
        if resolved == prefix or resolved.startswith(prefix + "/"):
            return True
    normalized = resolved.lstrip("./")
    for name in ("tests", ".verifier_tests_hidden", "solution"):
        if normalized == name or normalized.startswith(name + "/"):
            return True
    return False


def _join_path(base: str, child: str) -> str:
    child_path = Path(child)
    if child_path.is_absolute():
        return str(child_path)
    return str(Path(base if base else "/") / child_path)


@contextmanager
def lock_tests_from_submitted_process() -> Iterator[None]:
    """Make /tests and /solution root-only during the submitted process."""
    originals: list[tuple[Path, int]] = []

    def _lock(path: Path) -> None:
        try:
            mode = stat.S_IMODE(path.lstat().st_mode)
            originals.append((path, mode))
            if path.is_symlink():
                return
            path.chmod(0o700 if path.is_dir() else 0o600)
        except OSError:
            return

    def _lock_tree(root: Path) -> None:
        if not root.exists():
            return
        _lock(root)
        try:
            for child in root.rglob("*"):
                _lock(child)
        except OSError:
            return

    _lock_tree(_TESTS_DIR)
    _lock_tree(_SOLUTION_DIR)
    try:
        yield
    finally:
        for path, mode in reversed(originals):
            try:
                path.chmod(mode)
            except OSError:
                pass


def _wrap_unprivileged(cmd: Sequence[str]) -> list[str]:
    if shutil.which("setpriv"):
        return [
            "setpriv",
            "--reuid=65534",
            "--regid=65534",
            "--clear-groups",
            "--",
            *cmd,
        ]
    if shutil.which("runuser"):
        return ["runuser", "-u", "nobody", "--", *cmd]
    quoted = " ".join(shlex.quote(part) for part in cmd)
    return ["su", "-s", "/bin/sh", "nobody", "-c", quoted]


def _forbidden_paths_from_strace(trace_text: str) -> list[str]:
    """Resolve traced paths against per-pid cwd/dirfds/symlinks."""
    cwd: dict[int, str] = {}
    dirfds: dict[int, dict[int, str]] = {}
    found: list[str] = []
    seen: set[str] = set()
    root_pid = 0

    def ensure_pid(pid: int) -> None:
        cwd.setdefault(pid, "/app")
        dirfds.setdefault(pid, {})

    for line in trace_text.splitlines():
        pid = _line_pid(line, default=root_pid)
        ensure_pid(pid)
        call_match = _SYSCALL_RE.search(line)
        if not call_match:
            continue
        call = call_match.group("call")

        if call in {"clone", "clone3", "fork", "vfork"} and "= " in line:
            try:
                child = int(line.rsplit("= ", 1)[1].strip().split()[0])
            except ValueError:
                child = -1
            if child > 0:
                cwd[child] = cwd.get(pid, "/app")
                dirfds[child] = dict(dirfds.get(pid, {}))

        paths_in_line = [
            _decode_strace_path(match.group(1))
            for match in _STRACE_PATH_RE.finditer(line)
        ]

        if call == "chdir" and paths_in_line:
            cwd[pid] = _join_path(cwd.get(pid, "/app"), paths_in_line[0])
            continue
        if call == "fchdir":
            fd_match = re.search(r"fchdir\((\d+)\)", line)
            if fd_match:
                mapped = dirfds.get(pid, {}).get(int(fd_match.group(1)))
                if mapped:
                    cwd[pid] = mapped
            continue

        if (
            call.startswith("open")
            and "= " in line
            and "ENOENT" not in line
            and "EACCES" not in line
            and paths_in_line
        ):
            try:
                new_fd = int(line.rsplit("= ", 1)[1].strip().split()[0])
            except ValueError:
                new_fd = -1
            if new_fd >= 0:
                if call.startswith("openat"):
                    dirfd_token = line.split("(", 1)[1].split(",", 1)[0].strip()
                    if dirfd_token in _AT_FDCWD:
                        base = cwd.get(pid, "/app")
                    elif dirfd_token.lstrip("-").isdigit():
                        base = dirfds.get(pid, {}).get(
                            int(dirfd_token), cwd.get(pid, "/app")
                        )
                    else:
                        base = cwd.get(pid, "/app")
                    resolved = _join_path(base, paths_in_line[0])
                else:
                    resolved = _join_path(cwd.get(pid, "/app"), paths_in_line[0])
                dirfds.setdefault(pid, {})[new_fd] = resolved

        candidates: list[str] = []
        at_calls = {
            "openat",
            "openat2",
            "faccessat",
            "faccessat2",
            "fstatat",
            "newfstatat",
            "fstatat64",
            "name_to_handle_at",
            "execveat",
            "readlinkat",
        }
        if call in at_calls or call.startswith("openat"):
            dirfd_token = (
                line.split("(", 1)[1].split(",", 1)[0].strip()
                if "(" in line
                else "AT_FDCWD"
            )
            if dirfd_token in _AT_FDCWD:
                base = cwd.get(pid, "/app")
            elif dirfd_token.lstrip("-").isdigit():
                base = dirfds.get(pid, {}).get(int(dirfd_token), cwd.get(pid, "/app"))
            else:
                base = cwd.get(pid, "/app")
            if paths_in_line:
                candidates.append(_join_path(base, paths_in_line[0]))
        else:
            for raw_path in paths_in_line:
                candidates.append(_join_path(cwd.get(pid, "/app"), raw_path))

        for candidate in candidates:
            try:
                resolved = str(Path(candidate).resolve())
            except OSError:
                resolved = os.path.normpath(candidate)
            if _is_forbidden_resolved(resolved) or _is_forbidden_resolved(candidate):
                if resolved not in seen:
                    seen.add(resolved)
                    found.append(resolved)
    return found


def _line_pid(line: str, default: int = 0) -> int:
    match = _PID_PREFIX_RE.match(line)
    if not match:
        return default
    raw = match.group("br") or match.group("plain")
    return int(raw) if raw else default


def _execve_return_ok(line: str) -> bool:
    """True when strace reports a successful image replace (``= 0``)."""
    if "ENOENT" in line or "EACCES" in line or "EPERM" in line:
        return False
    tail = line.rsplit("=", 1)[-1].strip()
    return tail.startswith("0")


def _path_basename(path: str) -> str:
    return Path(path).name


def _is_absolute_named_executable(pathname: str, name: str) -> bool:
    """True when pathname is absolute and its final component equals ``name``.

    argv[0] spoofing is irrelevant here — callers must pass the real execve
    pathname (or an absolute nested interpreter path), never a bare basename.
    """
    if not pathname.startswith("/"):
        return False
    return _path_basename(pathname) == name


def _matches_workflow_exec(pathname: str, argv: list[str], workflow: dict) -> bool:
    """Require the real execve pathname and script in fixed argv positions.

    ``/bin/true`` with argv0 spoofed as ``Rscript`` must not count — only an
    absolute execve pathname whose basename is the interpreter may identify it.
    The script path appearing anywhere in argv is also insufficient. R must be
    an absolute ``…/Rscript`` pathname with ``/app/r/fold_balance.R`` as
    argv[1], or a shell shebang whose argv[1] is likewise an absolute
    ``…/Rscript`` path with the balance script as argv[2]. Relative names such
    as bare ``Rscript`` in argv do not count. Staging may be a direct shebang
    exec of the script path or absolute ``bash``/``sh`` with the script as
    argv[1].
    """
    script = workflow["script"]
    if workflow.get("allow_direct_script_exec") and pathname == script:
        return True
    interpreters = workflow["interpreters"]
    path_base = _path_basename(pathname)
    idx = int(workflow["script_argv_index"])

    # Use the real executable path only — never argv[0] alone.
    if "Rscript" in interpreters:
        if _is_absolute_named_executable(pathname, "Rscript"):
            return len(argv) > idx and argv[idx] == script
        # Debian Rscript is often a /bin/sh shebang wrapper; strace then shows
        # the shell as pathname with absolute …/Rscript as argv[1] and the .R
        # file as argv[2]. Relative "Rscript" argv entries are rejected.
        if path_base in {"bash", "sh", "dash"} and pathname.startswith("/"):
            if len(argv) <= idx + 1:
                return False
            return (
                _is_absolute_named_executable(argv[1], "Rscript")
                and argv[idx + 1] == script
            )
        if path_base == "env" and pathname.startswith("/"):
            if len(argv) <= idx + 1:
                return False
            return (
                _is_absolute_named_executable(argv[1], "Rscript")
                and argv[idx + 1] == script
            )
        return False

    if path_base in interpreters and pathname.startswith("/"):
        if len(argv) <= idx:
            return False
        return argv[idx] == script
    return False


def _missing_successful_workflow_execs(
    trace_text: str,
    only: Sequence[str] | None = None,
    *,
    require_exit: bool = True,
) -> list[str]:
    """Require exact successful execve of stage/R scripts that exit 0.

    Substring presence of script paths is not enough — the real executable
    pathname basename and script argv index must match the workflow contract
    (``bash …/stage_cohort.sh`` / ``Rscript …/fold_balance.R``).
    """
    only_labels = set(only) if only is not None else None
    exec_pids: dict[str, set[int]] = {
        item["label"]: set() for item in _REQUIRED_WORKFLOWS
    }
    exit_codes: dict[int, int] = {}

    for line in trace_text.splitlines():
        exit_match = _EXITED_RE.match(line) or _EXIT_GROUP_RE.match(line)
        if exit_match:
            pid_raw = exit_match.group("br") or exit_match.group("plain")
            pid = int(pid_raw) if pid_raw else 0
            exit_codes[pid] = int(exit_match.group("code"))
            continue

        if not _EXECVE_RE.match(line):
            continue
        if not _execve_return_ok(line):
            continue
        strings = [
            _unescape_strace_path(match.group(1))
            for match in _STRACE_PATH_RE.finditer(line)
        ]
        if not strings:
            continue
        pathname = strings[0]
        argv = strings[1:]
        pid = _line_pid(line, default=0)
        for workflow in _REQUIRED_WORKFLOWS:
            if _matches_workflow_exec(pathname, argv, workflow):
                exec_pids[workflow["label"]].add(pid)

    missing: list[str] = []
    for workflow in _REQUIRED_WORKFLOWS:
        label = workflow["label"]
        if only_labels is not None and label not in only_labels:
            continue
        ok = False
        for pid in exec_pids[label]:
            if not require_exit or exit_codes.get(pid, -1) == 0:
                ok = True
                break
        if not ok:
            missing.append(label)
    return missing


def _run_submitted(
    cmd: Sequence[str],
    *,
    require_workflow: bool | Sequence[str] = False,
) -> subprocess.CompletedProcess[str]:
    """Run as nobody under strace with cwd/dirfd/symlink path resolution.

    Trace logs live under root-only /logs/verifier so the child cannot unlink
    them. /tests and /solution are chmod-locked to root during the run (Harbor
    mounts cannot be renamed or bind-mounted away).
    """
    _TRACE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(_TRACE_DIR, 0o700)
    fd, trace_name = tempfile.mkstemp(
        prefix="fold-strace-", suffix=".log", dir=str(_TRACE_DIR)
    )
    os.close(fd)
    trace_path = Path(trace_name)
    os.chmod(trace_path, 0o600)

    wrapped = [
        "strace",
        "-f",
        "-e",
        "trace=file,process",
        "-o",
        str(trace_path),
        "--",
        *_wrap_unprivileged(cmd),
    ]
    try:
        with lock_tests_from_submitted_process():
            proc = subprocess.run(
                wrapped,
                capture_output=True,
                text=True,
                check=False,
                env=_scrubbed_subprocess_env(),
                cwd="/app",
                timeout=180,
            )
        trace_text = (
            trace_path.read_text(encoding="utf-8", errors="replace")
            if trace_path.exists()
            else ""
        )
        violations = _forbidden_paths_from_strace(trace_text)
        if violations:
            detail = ", ".join(violations)
            message = (
                "verifier rejected submitted process: "
                f"forbidden verifier/oracle path access: {detail}\n"
            )
            return subprocess.CompletedProcess(
                args=list(cmd),
                returncode=_FORBIDDEN_READ_RETURNCODE,
                stdout=proc.stdout,
                stderr=(proc.stderr or "") + message,
            )
        if require_workflow and proc.returncode == 0:
            only = None if require_workflow is True else list(require_workflow)
            missing = _missing_successful_workflow_execs(trace_text, only=only)
            if missing:
                # Some strace sessions omit +++ exited lines for the final image;
                # fall back to successful execve match alone when the process exited 0.
                missing = _missing_successful_workflow_execs(
                    trace_text, only=only, require_exit=False
                )
            if missing:
                message = (
                    "verifier rejected assemble: missing successful workflow "
                    f"execve+exit0 for: {missing}\n"
                )
                return subprocess.CompletedProcess(
                    args=list(cmd),
                    returncode=_MISSING_WORKFLOW_RETURNCODE,
                    stdout=proc.stdout,
                    stderr=(proc.stderr or "") + message,
                )
        return subprocess.CompletedProcess(
            args=list(cmd),
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
    finally:
        trace_path.unlink(missing_ok=True)


def reset_var() -> None:
    """Remove prior manifest and staged work artifacts."""
    if MANIFEST_PATH.exists():
        MANIFEST_PATH.unlink()
    if RECEIPT_PATH.exists():
        RECEIPT_PATH.unlink()
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    # Submitted assemble runs as an unprivileged user and must write here.
    os.chmod(Path("/app/var"), 0o777)
    os.chmod(WORK_DIR, 0o777)
    if RECEIPT_PATH.parent.exists():
        os.chmod(RECEIPT_PATH.parent, 0o777)


def read_csv_rows(dataset: Path, label_column: str) -> list[tuple[str, str]]:
    """Return (id, label) rows from a cohort CSV."""
    rows: list[tuple[str, str]] = []
    with dataset.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for record in reader:
            rows.append((record["id"].strip(), record[label_column].strip()))
    return rows


def reference_assign(
    rows: list[tuple[str, str]], fold_count: int
) -> dict[int, list[str]]:
    """Stratified round-robin assignment grouped by label."""
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row_id, label in rows:
        grouped[label].append((row_id, label))
    folds: dict[int, list[str]] = {idx: [] for idx in range(fold_count)}
    for label in sorted(grouped):
        group = sorted(grouped[label], key=lambda item: int(item[0]))
        for index, (row_id, _label) in enumerate(group):
            folds[index % fold_count].append(row_id)
    for fold_id in folds:
        folds[fold_id] = sorted(folds[fold_id], key=int)
    return folds


def reference_label_counts(
    rows: list[tuple[str, str]], assignment: dict[int, list[str]]
) -> dict[int, dict[str, int]]:
    """Build per-fold label count maps."""
    id_to_label = {row_id: label for row_id, label in rows}
    counts: dict[int, dict[str, int]] = {}
    for fold_id, row_ids in assignment.items():
        fold_counts: dict[str, int] = defaultdict(int)
        for row_id in row_ids:
            fold_counts[id_to_label[row_id]] += 1
        counts[fold_id] = dict(sorted(fold_counts.items()))
    return counts


def reference_digest(assignment: dict[int, dict[str, int]]) -> str:
    """Compute fold_digest from fold_id -> label_counts with known row counts."""
    lines: list[str] = []
    for fold_id in sorted(assignment):
        label_counts = assignment[fold_id]
        row_count = sum(label_counts.values())
        label_hist = ",".join(
            f"{label}={label_counts[label]}" for label in sorted(label_counts)
        )
        lines.append(f"{fold_id}|{row_count}|{label_hist}")
    payload = "\n".join(lines)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def reference_digest_from_rows(rows: list[tuple[str, str]], fold_count: int) -> str:
    """Compute fold_digest from cohort rows."""
    assignment = reference_assign(rows, fold_count)
    label_counts = reference_label_counts(rows, assignment)
    return reference_digest(label_counts)


def reference_balance(
    rows: list[tuple[str, str]], fold_count: int
) -> dict[str, object]:
    """Compute R-style balance metrics."""
    assignment = reference_assign(rows, fold_count)
    label_counts = reference_label_counts(rows, assignment)
    global_counts: dict[str, int] = defaultdict(int)
    for _fold_id, counts in label_counts.items():
        for label, count in counts.items():
            global_counts[label] += count
    label_columns = sorted(global_counts)
    row_count = len(rows)
    min_fold_rows = min(len(ids) for ids in assignment.values())
    max_fold_rows = max(len(ids) for ids in assignment.values())
    max_label_skew = 0.0
    for fold_id, counts in label_counts.items():
        fold_rows = len(assignment[fold_id])
        for label in label_columns:
            global_prop = global_counts[label] / row_count
            fold_prop = counts.get(label, 0) / fold_rows if fold_rows else 0.0
            max_label_skew = max(max_label_skew, abs(fold_prop - global_prop))
    return {
        "max_label_skew": max_label_skew,
        "min_fold_rows": min_fold_rows,
        "max_fold_rows": max_fold_rows,
        "label_columns": label_columns,
        "skew_band": reference_skew_band(max_label_skew),
    }


def reference_skew_band(max_label_skew: float) -> str:
    """Map max_label_skew to the documented band label."""
    if max_label_skew < 0.05:
        return "tight"
    if max_label_skew < 0.15:
        return "moderate"
    return "loose"


def reference_staged_fingerprint(staged_path: Path = STAGED_PATH) -> str:
    """SHA-256 hex over staged CSV bytes."""
    payload = staged_path.read_bytes()
    return hashlib.sha256(payload).hexdigest()


def reference_quorum_witness(rows: list[tuple[str, str]], fold_count: int) -> str:
    """SHA-256 hex over label|min_fold_id lines."""
    assignment = reference_assign(rows, fold_count)
    id_to_label = {row_id: label for row_id, label in rows}
    min_fold: dict[str, int] = {}
    for fold_id, row_ids in assignment.items():
        for row_id in row_ids:
            label = id_to_label[row_id]
            min_fold[label] = min(min_fold.get(label, fold_id), fold_id)
    lines = [f"{label}|{min_fold[label]}" for label in sorted(min_fold)]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def reference_stratum_spread_digest(
    rows: list[tuple[str, str]], fold_count: int
) -> str:
    """SHA-256 hex over per-label spread across folds."""
    assignment = reference_assign(rows, fold_count)
    label_counts = reference_label_counts(rows, assignment)
    labels = sorted({label for _row_id, label in rows})
    lines: list[str] = []
    for label in labels:
        counts = [label_counts[fold_id].get(label, 0) for fold_id in range(fold_count)]
        spread = max(counts) - min(counts)
        lines.append(f"{label}|{spread}")
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def reference_band_anchor(skew_band: str, fold_digest: str) -> str:
    """SHA-256 hex over skew_band|fold_digest."""
    body = f"{skew_band}|{fold_digest}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_epoch_seal(rotation_epoch: int, manifest_seal: str) -> str:
    """SHA-256 hex over rotation_epoch|manifest_seal."""
    body = f"{rotation_epoch}|{manifest_seal}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_ledger_root(
    staged_fingerprint: str, cohort_checksum: str, epoch_seal: str
) -> str:
    """SHA-256 hex over staged_fingerprint|cohort_checksum|epoch_seal."""
    body = f"{staged_fingerprint}|{cohort_checksum}|{epoch_seal}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_receipt_chain(manifest_seal: str, prior_chain: str = "GENESIS") -> str:
    """SHA-256 hex over previous_chain|manifest_seal."""
    body = f"{prior_chain}|{manifest_seal}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_fold_parity_digest(fold_count: int) -> str:
    """SHA-256 over fold_id|even/odd lines sorted by fold_id."""
    lines = [
        f"{fold_id}|{'even' if fold_id % 2 == 0 else 'odd'}"
        for fold_id in range(fold_count)
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def reference_label_coverage_seal(rows: list[tuple[str, str]], fold_count: int) -> str:
    """SHA-256 over label|fold_coverage lines sorted by label."""
    assignment = reference_assign(rows, fold_count)
    label_counts = reference_label_counts(rows, assignment)
    labels = sorted({label for _row_id, label in rows})
    lines: list[str] = []
    for label in labels:
        present = sum(
            1
            for fold_id in range(fold_count)
            if label_counts[fold_id].get(label, 0) > 0
        )
        lines.append(f"{label}|{present}")
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def reference_holdout_fold_id(rotation_epoch: int, fold_count: int) -> int:
    """Holdout fold is (rotation_epoch - 1) mod K."""
    return (rotation_epoch - 1) % fold_count


def reference_stratum_entropy_hint(rows: list[tuple[str, str]], fold_count: int) -> str:
    """SHA-256 over label|sparse|dense buckets by total count vs K."""
    totals: dict[str, int] = defaultdict(int)
    for _row_id, label in rows:
        totals[label] += 1
    lines = [
        f"{label}|{'sparse' if totals[label] < fold_count else 'dense'}"
        for label in sorted(totals)
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def reference_evaluation_seal(
    fold_parity_digest: str,
    label_coverage_seal: str,
    holdout_fold_id: int,
    manifest_seal: str,
) -> str:
    """SHA-256 over parity|coverage|holdout|manifest_seal."""
    body = (
        f"{fold_parity_digest}|{label_coverage_seal}|{holdout_fold_id}|{manifest_seal}"
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_assemble_attestation(
    evaluation_seal: str, ledger_root: str, stratum_entropy_hint: str
) -> str:
    """SHA-256 over evaluation_seal|ledger_root|stratum_entropy_hint."""
    body = f"{evaluation_seal}|{ledger_root}|{stratum_entropy_hint}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_fold_load_skew(rows: list[tuple[str, str]], fold_count: int) -> int:
    """max fold size minus min fold size after stratified assignment; 0 if empty."""
    if not rows:
        return 0
    assignment = reference_assign(rows, fold_count)
    sizes = [len(row_ids) for row_ids in assignment.values()]
    if not sizes:
        return 0
    return max(sizes) - min(sizes)


def reference_label_cardinality(rows: list[tuple[str, str]]) -> int:
    """Count of distinct labels across the cohort; 0 if none."""
    if not rows:
        return 0
    return len({label for _row_id, label in rows})


def reference_cohort_span_digest(rows: list[tuple[str, str]]) -> str:
    """SHA-256 of unique labels sorted lex, joined by newline; empty -> empty hash."""
    labels = sorted({label for _row_id, label in rows})
    return hashlib.sha256("\n".join(labels).encode("utf-8")).hexdigest()


def reference_balance_coupler(
    balance_anchor: str, band_anchor: str, skew_band: str
) -> str:
    """SHA-256 of balance_anchor|band_anchor|skew_band."""
    body = f"{balance_anchor}|{band_anchor}|{skew_band}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_kit_closure(
    assemble_attestation: str,
    fold_load_skew: int,
    label_cardinality: int,
    cohort_span_digest: str,
    balance_coupler: str,
) -> str:
    """SHA-256 of attestation|skew|cardinality|span|coupler with base-10 ints."""
    body = (
        f"{assemble_attestation}|{fold_load_skew}|{label_cardinality}|"
        f"{cohort_span_digest}|{balance_coupler}"
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_run_chain_digest(
    kit_closure: str, prior_run_chain: str = "GENESIS"
) -> str:
    """SHA-256 of previous_run_chain|kit_closure."""
    body = f"{prior_run_chain}|{kit_closure}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_class_prior_seal(
    fold_label_counts: dict[int, dict[str, int]], row_count: int
) -> str:
    """SHA-256 over label|prior lines built from summed fold label_counts."""
    totals: dict[str, int] = defaultdict(int)
    for counts in fold_label_counts.values():
        for label, count in counts.items():
            totals[label] += count
    if not totals or row_count <= 0:
        return hashlib.sha256(b"").hexdigest()
    lines = [f"{label}|{totals[label] / row_count:.6f}" for label in sorted(totals)]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def reference_fold_split_witness(assignment: dict[int, list[str]]) -> str:
    """SHA-256 over fold_id|first_id|last_id|size lines sorted by fold_id."""
    if not assignment:
        return hashlib.sha256(b"").hexdigest()
    lines: list[str] = []
    for fold_id in sorted(assignment):
        row_ids = assignment[fold_id]
        if not row_ids:
            lines.append(f"{fold_id}|-|-|0")
            continue
        numeric = [int(row_id) for row_id in row_ids]
        lines.append(f"{fold_id}|{min(numeric)}|{max(numeric)}|{len(row_ids)}")
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def reference_holdout_epoch_coupler(
    holdout_fold_id: int, rotation_epoch: int, fold_count: int, evaluation_seal: str
) -> str:
    """SHA-256 over holdout_fold_id|rotation_epoch|fold_count|evaluation_seal."""
    body = f"{holdout_fold_id}|{rotation_epoch}|{fold_count}|{evaluation_seal}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_stratum_stability_index(
    assignment: dict[int, list[str]], label_counts: dict[int, dict[str, int]]
) -> str:
    """SHA-256 over label|max_share|min_share across folds with positive size."""
    positive_folds = [fold_id for fold_id, ids in assignment.items() if ids]
    if not positive_folds:
        return hashlib.sha256(b"").hexdigest()
    labels: set[str] = set()
    for counts in label_counts.values():
        labels.update(counts.keys())
    lines: list[str] = []
    for label in sorted(labels):
        shares = [
            label_counts[fold_id].get(label, 0) / len(assignment[fold_id])
            for fold_id in positive_folds
        ]
        lines.append(f"{label}|{max(shares):.6f}|{min(shares):.6f}")
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def reference_fold_kit_seal(
    kit_closure: str,
    class_prior_seal: str,
    fold_split_witness: str,
    holdout_epoch_coupler: str,
    stratum_stability_index: str,
    train_fold_mask: str,
    label_pair_cooccurrence: str,
    balance_drift_witness: str,
    epoch_manifest_binder: str,
    holdout_exclusion_seal: str,
) -> str:
    """SHA-256 over kit_closure through holdout_exclusion_seal pipe chain."""
    body = (
        f"{kit_closure}|{class_prior_seal}|{fold_split_witness}|"
        f"{holdout_epoch_coupler}|{stratum_stability_index}|{train_fold_mask}|"
        f"{label_pair_cooccurrence}|{balance_drift_witness}|"
        f"{epoch_manifest_binder}|{holdout_exclusion_seal}"
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_fold_coverage_lattice(
    label_coverage_seal: str,
    fold_parity_digest: str,
    stratum_stability_index: str,
    label_cardinality: int,
) -> str:
    """SHA-256 of label_coverage_seal|fold_parity_digest|stratum_stability_index|label_cardinality."""
    body = (
        f"{label_coverage_seal}|{fold_parity_digest}|"
        f"{stratum_stability_index}|{label_cardinality}"
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_holdout_train_tension(
    train_fold_mask: str,
    holdout_exclusion_seal: str,
    holdout_epoch_coupler: str,
    fold_load_skew: int,
) -> str:
    """SHA-256 of train_fold_mask|holdout_exclusion_seal|holdout_epoch_coupler|fold_load_skew."""
    body = (
        f"{train_fold_mask}|{holdout_exclusion_seal}|"
        f"{holdout_epoch_coupler}|{fold_load_skew}"
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_skew_prior_witness(
    balance_drift_witness: str,
    class_prior_seal: str,
    balance_coupler: str,
    max_label_skew: float,
) -> str:
    """SHA-256 of balance_drift_witness|class_prior_seal|balance_coupler|skewSix."""
    body = (
        f"{balance_drift_witness}|{class_prior_seal}|"
        f"{balance_coupler}|{float(max_label_skew):.6f}"
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_epoch_receipt_binder(
    epoch_manifest_binder: str,
    run_chain_digest: str,
    receipt_chain: str,
    rotation_epoch: int,
) -> str:
    """SHA-256 of epoch_manifest_binder|run_chain_digest|receipt_chain|rotation_epoch."""
    body = (
        f"{epoch_manifest_binder}|{run_chain_digest}|{receipt_chain}|{rotation_epoch}"
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_fold_kit_outer_seal(
    fold_kit_seal: str,
    fold_coverage_lattice: str,
    holdout_train_tension: str,
    skew_prior_witness: str,
    epoch_receipt_binder: str,
) -> str:
    """SHA-256 over fold_kit_seal through epoch_receipt_binder pipe chain."""
    body = (
        f"{fold_kit_seal}|{fold_coverage_lattice}|{holdout_train_tension}|"
        f"{skew_prior_witness}|{epoch_receipt_binder}"
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_train_fold_mask(
    assignment: dict[int, list[str]], holdout_fold_id: int
) -> str:
    """SHA-256 of comma-joined sorted train fold ids excluding holdout."""
    train_ids = sorted(fold_id for fold_id in assignment if fold_id != holdout_fold_id)
    if not train_ids:
        return hashlib.sha256(b"").hexdigest()
    return hashlib.sha256(
        ",".join(str(fold_id) for fold_id in train_ids).encode("utf-8")
    ).hexdigest()


def reference_label_pair_cooccurrence(
    assignment: dict[int, list[str]], label_counts: dict[int, dict[str, int]]
) -> str:
    """SHA-256 over fold_id|a|b lines for unordered positive label pairs per fold."""
    lines: list[str] = []
    for fold_id in sorted(assignment):
        counts = label_counts.get(fold_id, {})
        positive = sorted(label for label, count in counts.items() if count > 0)
        for i, left in enumerate(positive):
            for right in positive[i + 1 :]:
                lines.append(f"{fold_id}|{left}|{right}")
    if not lines:
        return hashlib.sha256(b"").hexdigest()
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def reference_balance_drift_witness(
    rows: list[tuple[str, str]],
    fold_count: int,
    max_label_skew: float,
    skew_band: str,
) -> str:
    """SHA-256 of javaSkewSix|rSkewSix|skew_band; java skew skips empty folds."""
    assignment = reference_assign(rows, fold_count)
    label_counts = reference_label_counts(rows, assignment)
    row_count = len(rows)
    if row_count <= 0:
        java_skew = 0.0
    else:
        positive = [fold_id for fold_id, ids in assignment.items() if ids]
        if not positive:
            java_skew = 0.0
        else:
            global_counts: dict[str, int] = defaultdict(int)
            for counts in label_counts.values():
                for label, count in counts.items():
                    global_counts[label] += count
            java_skew = 0.0
            for label in sorted(global_counts):
                global_share = global_counts[label] / row_count
                for fold_id in positive:
                    fold_size = len(assignment[fold_id])
                    fold_share = label_counts[fold_id].get(label, 0) / fold_size
                    java_skew = max(java_skew, abs(fold_share - global_share))
    body = f"{java_skew:.6f}|{float(max_label_skew):.6f}|{skew_band}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_epoch_manifest_binder(
    rotation_epoch: int, fold_digest: str, class_prior_seal: str
) -> str:
    """SHA-256 of rotation_epoch|fold_digest|class_prior_seal."""
    body = f"{rotation_epoch}|{fold_digest}|{class_prior_seal}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_holdout_exclusion_seal(
    train_fold_mask: str, holdout_fold_id: int, fold_load_skew: int
) -> str:
    """SHA-256 of train_fold_mask|holdout_fold_id|fold_load_skew."""
    body = f"{train_fold_mask}|{holdout_fold_id}|{fold_load_skew}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_extended_coupling(
    rows: list[tuple[str, str]],
    fold_count: int,
    fold_digest: str,
    staged_fingerprint: str,
    rotation_epoch: int,
    prior_receipt_chain: str = "GENESIS",
    prior_run_chain: str = "GENESIS",
) -> dict[str, str | int]:
    """Recompute extended coupling fields from cohort rows."""
    seals = reference_extended_seals(rows, fold_count, fold_digest)
    balance = reference_balance(rows, fold_count)
    skew_band = reference_skew_band(float(balance["max_label_skew"]))
    receipt_chain = reference_receipt_chain(seals["manifest_seal"], prior_receipt_chain)
    epoch_seal = reference_epoch_seal(rotation_epoch, seals["manifest_seal"])
    ledger_root = reference_ledger_root(
        staged_fingerprint, seals["cohort_checksum"], epoch_seal
    )
    fold_parity_digest = reference_fold_parity_digest(fold_count)
    label_coverage_seal = reference_label_coverage_seal(rows, fold_count)
    holdout_fold_id = reference_holdout_fold_id(rotation_epoch, fold_count)
    stratum_entropy_hint = reference_stratum_entropy_hint(rows, fold_count)
    evaluation_seal = reference_evaluation_seal(
        fold_parity_digest,
        label_coverage_seal,
        holdout_fold_id,
        seals["manifest_seal"],
    )
    assemble_attestation = reference_assemble_attestation(
        evaluation_seal, ledger_root, stratum_entropy_hint
    )
    band_anchor = reference_band_anchor(skew_band, fold_digest)
    fold_load_skew = reference_fold_load_skew(rows, fold_count)
    label_cardinality = reference_label_cardinality(rows)
    cohort_span_digest = reference_cohort_span_digest(rows)
    balance_coupler = reference_balance_coupler(
        seals["balance_anchor"], band_anchor, skew_band
    )
    kit_closure = reference_kit_closure(
        assemble_attestation,
        fold_load_skew,
        label_cardinality,
        cohort_span_digest,
        balance_coupler,
    )
    run_chain_digest = reference_run_chain_digest(kit_closure, prior_run_chain)
    assignment = reference_assign(rows, fold_count)
    label_counts = reference_label_counts(rows, assignment)
    class_prior_seal = reference_class_prior_seal(label_counts, len(rows))
    fold_split_witness = reference_fold_split_witness(assignment)
    holdout_epoch_coupler = reference_holdout_epoch_coupler(
        holdout_fold_id, rotation_epoch, fold_count, evaluation_seal
    )
    stratum_stability_index = reference_stratum_stability_index(
        assignment, label_counts
    )
    train_fold_mask = reference_train_fold_mask(assignment, holdout_fold_id)
    label_pair_cooccurrence = reference_label_pair_cooccurrence(
        assignment, label_counts
    )
    balance_drift_witness = reference_balance_drift_witness(
        rows,
        fold_count,
        float(balance["max_label_skew"]),
        skew_band,
    )
    epoch_manifest_binder = reference_epoch_manifest_binder(
        rotation_epoch, fold_digest, class_prior_seal
    )
    holdout_exclusion_seal = reference_holdout_exclusion_seal(
        train_fold_mask, holdout_fold_id, fold_load_skew
    )
    fold_kit_seal = reference_fold_kit_seal(
        kit_closure,
        class_prior_seal,
        fold_split_witness,
        holdout_epoch_coupler,
        stratum_stability_index,
        train_fold_mask,
        label_pair_cooccurrence,
        balance_drift_witness,
        epoch_manifest_binder,
        holdout_exclusion_seal,
    )
    fold_coverage_lattice = reference_fold_coverage_lattice(
        label_coverage_seal,
        fold_parity_digest,
        stratum_stability_index,
        label_cardinality,
    )
    holdout_train_tension = reference_holdout_train_tension(
        train_fold_mask,
        holdout_exclusion_seal,
        holdout_epoch_coupler,
        fold_load_skew,
    )
    skew_prior_witness = reference_skew_prior_witness(
        balance_drift_witness,
        class_prior_seal,
        balance_coupler,
        float(balance["max_label_skew"]),
    )
    epoch_receipt_binder = reference_epoch_receipt_binder(
        epoch_manifest_binder,
        run_chain_digest,
        receipt_chain,
        rotation_epoch,
    )
    fold_kit_outer_seal = reference_fold_kit_outer_seal(
        fold_kit_seal,
        fold_coverage_lattice,
        holdout_train_tension,
        skew_prior_witness,
        epoch_receipt_binder,
    )
    return {
        **seals,
        "staged_fingerprint": staged_fingerprint,
        "quorum_witness": reference_quorum_witness(rows, fold_count),
        "stratum_spread_digest": reference_stratum_spread_digest(rows, fold_count),
        "skew_band": skew_band,
        "band_anchor": band_anchor,
        "rotation_epoch": rotation_epoch,
        "receipt_chain": receipt_chain,
        "epoch_seal": epoch_seal,
        "ledger_root": ledger_root,
        "fold_parity_digest": fold_parity_digest,
        "label_coverage_seal": label_coverage_seal,
        "holdout_fold_id": holdout_fold_id,
        "evaluation_seal": evaluation_seal,
        "stratum_entropy_hint": stratum_entropy_hint,
        "assemble_attestation": assemble_attestation,
        "fold_load_skew": fold_load_skew,
        "label_cardinality": label_cardinality,
        "cohort_span_digest": cohort_span_digest,
        "balance_coupler": balance_coupler,
        "kit_closure": kit_closure,
        "run_chain_digest": run_chain_digest,
        "class_prior_seal": class_prior_seal,
        "fold_split_witness": fold_split_witness,
        "holdout_epoch_coupler": holdout_epoch_coupler,
        "stratum_stability_index": stratum_stability_index,
        "train_fold_mask": train_fold_mask,
        "label_pair_cooccurrence": label_pair_cooccurrence,
        "balance_drift_witness": balance_drift_witness,
        "epoch_manifest_binder": epoch_manifest_binder,
        "holdout_exclusion_seal": holdout_exclusion_seal,
        "fold_kit_seal": fold_kit_seal,
        "fold_coverage_lattice": fold_coverage_lattice,
        "holdout_train_tension": holdout_train_tension,
        "skew_prior_witness": skew_prior_witness,
        "epoch_receipt_binder": epoch_receipt_binder,
        "fold_kit_outer_seal": fold_kit_outer_seal,
    }


def reference_cohort_checksum(rows: list[tuple[str, str]]) -> str:
    """Compute cohort_checksum from sorted id|label rows."""
    body = "\n".join(
        f"{row_id}|{label}"
        for row_id, label in sorted(rows, key=lambda item: int(item[0]))
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_assignment_seal(rows: list[tuple[str, str]], fold_count: int) -> str:
    """Compute assignment_seal from per-label fold assignment sequences."""
    assignment = reference_assign(rows, fold_count)
    id_to_fold = {
        row_id: fold_id for fold_id, row_ids in assignment.items() for row_id in row_ids
    }
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row_id, label in rows:
        grouped[label].append((row_id, label))
    lines: list[str] = []
    for label in sorted(grouped):
        group = sorted(grouped[label], key=lambda item: int(item[0]))
        sequence = ",".join(str(id_to_fold[row_id]) for row_id, _ in group)
        lines.append(f"{label}|{sequence}")
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def reference_balance_anchor(fold_digest: str, max_label_skew: float) -> str:
    """Compute balance_anchor from fold_digest and formatted skew."""
    rounded = f"{max_label_skew:.6f}"
    body = f"{fold_digest}|{rounded}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_manifest_seal(
    cohort_checksum: str,
    assignment_seal: str,
    balance_anchor: str,
    fold_count: int,
) -> str:
    """Compute manifest_seal over upstream coupling digests."""
    body = f"{cohort_checksum}|{assignment_seal}|{balance_anchor}|{fold_count}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def reference_extended_seals(
    rows: list[tuple[str, str]], fold_count: int, fold_digest: str
) -> dict[str, str]:
    """Recompute extended manifest seal fields from cohort rows."""
    balance = reference_balance(rows, fold_count)
    cohort_checksum = reference_cohort_checksum(rows)
    assignment_seal = reference_assignment_seal(rows, fold_count)
    balance_anchor = reference_balance_anchor(
        fold_digest, float(balance["max_label_skew"])
    )
    manifest_seal = reference_manifest_seal(
        cohort_checksum, assignment_seal, balance_anchor, fold_count
    )
    return {
        "cohort_checksum": cohort_checksum,
        "assignment_seal": assignment_seal,
        "balance_anchor": balance_anchor,
        "manifest_seal": manifest_seal,
    }


def read_receipt_lines() -> list[dict]:
    """Parse fold receipt JSONL lines."""
    if not RECEIPT_PATH.exists():
        return []
    lines: list[dict] = []
    for raw in RECEIPT_PATH.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            lines.append(json.loads(raw))
    return lines


def assert_public_pom_integrity(pom_path: Path = PUBLIC_POM) -> None:
    """Require the documented /app/pom.xml still packages the fold-assembler jar."""
    if not pom_path.is_file():
        raise AssertionError(f"missing public POM: {pom_path}")
    text = pom_path.read_text(encoding="utf-8")
    required_snippets = (
        "<groupId>com.foldlab</groupId>",
        "<artifactId>fold-assembler</artifactId>",
        "<version>1.0.0</version>",
        "<packaging>jar</packaging>",
        "maven-shade-plugin",
        "com.foldlab.FoldLabApp",
        "gson",
        "2.11.0",
        "maven-compiler-plugin",
        "<release>21</release>",
    )
    for snippet in required_snippets:
        if snippet not in text:
            raise AssertionError(f"public POM missing required fragment: {snippet}")
    if "/tests" in text or "/solution" in text:
        raise AssertionError("public POM must not reference /tests or /solution")


def build_jar_with_public_pom() -> Path:
    """Package a shaded jar using a sandbox copy of the public /app/pom.xml."""
    assert_public_pom_integrity()
    java_src = Path("/app/src/main/java")
    if not java_src.is_dir():
        raise AssertionError("missing /app/src/main/java for public POM build")
    build_root = Path("/logs/verifier/public-pom-build")
    if build_root.exists():
        shutil.rmtree(build_root)
    src_dst = build_root / "src" / "main" / "java"
    src_dst.mkdir(parents=True)
    shutil.copy2(PUBLIC_POM, build_root / "pom.xml")
    shutil.copytree(java_src, src_dst, dirs_exist_ok=True)
    for path in src_dst.rglob("*"):
        if path.is_symlink():
            path.unlink()
    proc = subprocess.run(
        [
            "mvn",
            "-q",
            "-o",
            "-f",
            str(build_root / "pom.xml"),
            "-DskipTests",
            "package",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(build_root),
        timeout=600,
        env=_scrubbed_subprocess_env(),
    )
    if proc.returncode != 0:
        raise AssertionError(
            "public POM Maven package failed: "
            f"{proc.stderr or proc.stdout or proc.returncode}"
        )
    jar = build_root / "target" / "fold-assembler-1.0.0.jar"
    if not jar.is_file():
        raise AssertionError(f"public POM build did not produce jar: {jar}")
    return jar


def assert_foldctl_integrity(foldctl_path: Path = FOLDCTL) -> None:
    """Require foldctl to exec the packaged jar through Java."""
    if not foldctl_path.is_file():
        raise AssertionError(f"missing foldctl: {foldctl_path}")
    text = foldctl_path.read_text(encoding="utf-8")
    if "fold-assembler-1.0.0.jar" not in text:
        raise AssertionError("foldctl must reference fold-assembler-1.0.0.jar")
    if "-jar" not in text:
        raise AssertionError("foldctl must pass -jar to Java")
    if "java" not in text.lower():
        raise AssertionError("foldctl must invoke Java")


def build_balance_probe_manifest(rows: list[tuple[str, str]], fold_count: int) -> dict:
    """Build a minimal fold_manifest-shaped object for a direct Rscript probe."""
    assignment = reference_assign(rows, fold_count)
    label_counts = reference_label_counts(rows, assignment)
    folds = []
    for fold_id in sorted(assignment):
        folds.append(
            {
                "fold_id": fold_id,
                "row_ids": assignment[fold_id],
                "label_counts": label_counts[fold_id],
            }
        )
    return {
        "row_count": len(rows),
        "fold_count": fold_count,
        "folds": folds,
    }


def run_fold_balance_rscript(manifest_path: Path) -> subprocess.CompletedProcess[str]:
    """Invoke fold_balance.R under the protected nobody/strace runner.

    Never run the balance script as root outside the lock — that would allow
    reading /tests or /solution. Always resolve an absolute ``…/Rscript``
    pathname (not an argv[0] spoof) for the probe command. Assemble workflows
    still require pathname-based ``…/Rscript`` via ``require_workflow``; a lone
    Rscript child under setpriv does not reliably emit a matchable
    execve+exit0 pair the way a Java-spawned R process does, so this probe
    relies on the protected runner plus the absolute interpreter path and a
    pre/post hash of the argv manifest file.
    """
    which = shutil.which("Rscript")
    if not which:
        raise AssertionError("Rscript is not on PATH")
    rscript = str(Path(which).resolve())
    if not _is_absolute_named_executable(rscript, "Rscript"):
        raise AssertionError(
            f"resolved interpreter must be absolute …/Rscript, got {rscript}"
        )
    Path("/app/var").mkdir(parents=True, exist_ok=True)
    os.chmod(Path("/app/var"), 0o777)
    readable = Path("/app/var") / f".verifier_balance_{os.getpid()}.json"
    shutil.copy2(manifest_path, readable)
    os.chmod(readable, 0o644)
    before = hashlib.sha256(readable.read_bytes()).hexdigest()
    try:
        proc = _run_submitted(
            [rscript, _BALANCE_SCRIPT_ABS, str(readable)],
            require_workflow=False,
        )
        after = (
            hashlib.sha256(readable.read_bytes()).hexdigest()
            if readable.is_file()
            else ""
        )
        if after != before:
            message = (
                "verifier rejected fold_balance.R: probe manifest path was modified\n"
            )
            return subprocess.CompletedProcess(
                args=list(proc.args),
                returncode=_FORBIDDEN_READ_RETURNCODE,
                stdout=proc.stdout,
                stderr=(proc.stderr or "") + message,
            )
        return proc
    finally:
        readable.unlink(missing_ok=True)


def run_assemble(
    dataset: Path = STOCK_DATASET,
    folds: int = STOCK_FOLDS,
    label: str = STOCK_LABEL,
) -> subprocess.CompletedProcess[str]:
    """Invoke the verifier-built Java jar as an unprivileged user under strace."""
    if not ASSEMBLE_JAR.is_file():
        raise AssertionError(
            f"missing assemble jar (run verifier Maven package): {ASSEMBLE_JAR}"
        )
    if not JAVA_BIN.is_file():
        raise AssertionError(f"missing java binary: {JAVA_BIN}")
    # Copy into /app/var so the unprivileged child can read TemporaryDirectory datasets.
    Path("/app/var").mkdir(parents=True, exist_ok=True)
    os.chmod(Path("/app/var"), 0o777)
    readable = Path("/app/var") / f".verifier_dataset_{os.getpid()}.csv"
    shutil.copy2(dataset, readable)
    os.chmod(readable, 0o644)
    try:
        return _run_submitted(
            [
                *BIN,
                "--dataset",
                str(readable),
                "--folds",
                str(folds),
                "--label",
                label,
            ],
            require_workflow=True,
        )
    finally:
        readable.unlink(missing_ok=True)


def run_assemble_via_foldctl(
    dataset: Path = STOCK_DATASET,
    folds: int = STOCK_FOLDS,
    label: str = STOCK_LABEL,
) -> subprocess.CompletedProcess[str]:
    """Invoke the public /app/bin/foldctl assemble under the same strace guard."""
    assert_foldctl_integrity()
    if not ASSEMBLE_JAR.is_file():
        raise AssertionError(
            f"missing assemble jar (run verifier Maven package): {ASSEMBLE_JAR}"
        )
    Path("/app/var").mkdir(parents=True, exist_ok=True)
    os.chmod(Path("/app/var"), 0o777)
    readable = Path("/app/var") / f".verifier_foldctl_{os.getpid()}.csv"
    shutil.copy2(dataset, readable)
    os.chmod(readable, 0o644)
    try:
        return _run_submitted(
            [
                *BIN_FOLDCTL,
                "--dataset",
                str(readable),
                "--folds",
                str(folds),
                "--label",
                label,
            ],
            require_workflow=True,
        )
    finally:
        readable.unlink(missing_ok=True)


def run_stage(dataset: Path, label: str) -> subprocess.CompletedProcess[str]:
    """Invoke stage_cohort.sh as an unprivileged user under strace."""
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(Path("/app/var"), 0o777)
    os.chmod(WORK_DIR, 0o777)
    readable = Path("/app/var") / f".verifier_stage_{os.getpid()}.csv"
    shutil.copy2(dataset, readable)
    os.chmod(readable, 0o644)
    try:
        return _run_submitted(
            ["bash", str(STAGE_SCRIPT), str(readable), str(WORK_DIR), label],
            require_workflow=False,
        )
    finally:
        readable.unlink(missing_ok=True)


def load_stdout_json(proc: subprocess.CompletedProcess[str]) -> dict:
    """Parse assemble stdout JSON."""
    return json.loads(proc.stdout)


def load_manifest() -> dict:
    """Load on-disk fold manifest."""
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def fold_map(manifest: dict) -> dict[int, dict]:
    """Index folds by fold_id."""
    return {fold["fold_id"]: fold for fold in manifest["folds"]}


def all_row_ids(manifest: dict) -> list[str]:
    """Flatten row ids across folds."""
    ids: list[str] = []
    for fold in manifest["folds"]:
        ids.extend(fold["row_ids"])
    return ids
