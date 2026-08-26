#!/usr/local/bin/python3
from __future__ import annotations

import ctypes
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path


NOBODY = 65534
PR_SET_NO_NEW_PRIVS = 38
SANDBOX = Path("/opt/oci-layer-gate-sandbox")


def prepare_system() -> None:
    if (SANDBOX / ".ready").is_file():
        return
    shutil.rmtree(SANDBOX, ignore_errors=True)
    SANDBOX.mkdir(mode=0o755)
    SANDBOX.chmod(0o755)
    (SANDBOX / "app").mkdir(mode=0o755)
    (SANDBOX / "app").chmod(0o755)
    marker = SANDBOX / ".ready"
    marker.touch(mode=0o444)
    marker.chmod(0o444)


def stage_runtime(program: Path) -> None:
    result = subprocess.run(
        ["ldd", str(program)],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    libraries: set[Path] = set()
    for line in result.stdout.splitlines():
        for token in line.split():
            if token.startswith("/"):
                libraries.add(Path(token))
                break
    if not libraries:
        raise RuntimeError("candidate runtime dependencies were not found")
    for source in libraries:
        destination = SANDBOX / source.relative_to("/")
        destination.parent.mkdir(parents=True, exist_ok=True)
        parent = destination.parent
        while parent != SANDBOX:
            parent.chmod(0o755)
            parent = parent.parent
        shutil.copyfile(source.resolve(), destination)
        destination.chmod(0o755)


def prepare_run(program: Path, policy: Path, manifest: Path, destination: Path) -> None:
    for name in ("input", "output", "tmp"):
        path = SANDBOX / name
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
    input_dir = SANDBOX / "input"
    input_dir.mkdir(mode=0o755)
    shutil.copyfile(manifest, input_dir / "layers.manifest")
    (input_dir / "layers.manifest").chmod(0o444)
    shutil.copyfile(policy, input_dir / "extraction.policy")
    (input_dir / "extraction.policy").chmod(0o444)
    for source in manifest.parent.glob("*.tar"):
        target = input_dir / source.name
        shutil.copyfile(source, target)
        target.chmod(0o444)
    (SANDBOX / "output").mkdir(mode=0o777)
    (SANDBOX / "output").chmod(0o777)
    if destination.is_file():
        shutil.copyfile(destination, SANDBOX / "output/report.json")
        (SANDBOX / "output/report.json").chmod(0o666)
    (SANDBOX / "tmp").mkdir(mode=0o1777)
    (SANDBOX / "tmp").chmod(0o1777)
    stage_runtime(program)
    target = SANDBOX / "app/layer-gate"
    shutil.copyfile(program, target)
    target.chmod(0o755)


def child_status() -> int:
    pid = os.fork()
    if pid == 0:
        try:
            os.chroot(SANDBOX)
            os.chdir("/app")
            libc = ctypes.CDLL(None, use_errno=True)
            if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error))
            os.setgroups([])
            os.setgid(NOBODY)
            os.setuid(NOBODY)
            os.execve(
                "/app/layer-gate",
                [
                    "/app/layer-gate",
                    "/input/extraction.policy",
                    "/input/layers.manifest",
                    "/output/report.json",
                ],
                {"LANG": "C.UTF-8", "PATH": "/usr/bin:/bin", "TMPDIR": "/tmp"},
            )
        except BaseException as error:
            print(f"sandbox launch failed: {error}", file=sys.stderr)
            os._exit(127)
    _, status_value = os.waitpid(pid, 0)
    if os.WIFEXITED(status_value):
        return os.WEXITSTATUS(status_value)
    return 128 + os.WTERMSIG(status_value)


def export_output(destination: Path) -> None:
    source = SANDBOX / "output/report.json"
    try:
        details = source.lstat()
    except FileNotFoundError:
        destination.unlink(missing_ok=True)
        return
    if not stat.S_ISREG(details.st_mode):
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def main() -> None:
    if sys.argv[1:] == ["--prepare"]:
        prepare_system()
        return
    if len(sys.argv) != 5:
        raise SystemExit(2)
    program = Path(sys.argv[1]).resolve()
    policy = Path(sys.argv[2]).resolve()
    manifest = Path(sys.argv[3]).resolve()
    destination = Path(sys.argv[4]).resolve()
    prepare_system()
    prepare_run(program, policy, manifest, destination)
    status_value = child_status()
    export_output(destination)
    raise SystemExit(status_value)


if __name__ == "__main__":
    main()
