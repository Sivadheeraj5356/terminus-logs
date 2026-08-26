from __future__ import annotations
import filecmp
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path("/app/repo")
REPO_PACKAGES = REPO_ROOT / "packages"

RESTORED_PACKAGES = (
    "printer",
    "printer-ansi",
)

EFFECT_UPSTREAM_COMMIT = "3e59443be029e99d2b457bb43f682feb5ebcd2e0"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _semver_tuple(version: str) -> tuple[int, int, int] | None:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", version.lstrip("v"))
    if m is None:
        return None
    return tuple(map(int, m.groups()))


def _workspace_spec_satisfies(spec: str, version: str) -> bool:
    raw = spec.removeprefix("workspace:").strip()

    if raw in ("", "*", "^", "~"):
        return True

    actual = _semver_tuple(version)
    if actual is None:
        return False

    if raw.startswith("^"):
        req = _semver_tuple(raw[1:])
        return req is not None and actual[0] == req[0] and actual >= req

    if raw.startswith("~"):
        req = _semver_tuple(raw[1:])
        return (
            req is not None
            and actual[0] == req[0]
            and actual[1] == req[1]
            and actual[2] >= req[2]
        )

    req = _semver_tuple(raw)
    return req is not None and actual == req


def _compare_dirs(left: Path, right: Path) -> None:
    cmp = filecmp.dircmp(left, right)

    assert not cmp.left_only, (
        f"Unexpected files in restored package:\n{sorted(cmp.left_only)}"
    )

    assert not cmp.right_only, (
        f"Missing files:\n{sorted(cmp.right_only)}"
    )

    assert not cmp.diff_files, (
        f"Modified files:\n{sorted(cmp.diff_files)}"
    )

    assert not cmp.funny_files

    for sub in cmp.common_dirs:
        _compare_dirs(left / sub, right / sub)


def test_packages_are_genuinely_restored() -> None:
    """
    Behavioral test 1: verifies that the deleted workspace packages are 
    restored with correct manifests, source trees, etc.
    """

    expected = {
        "printer": "@effect/printer",
        "printer-ansi": "@effect/printer-ansi",
    }

    for dirname, package_name in expected.items():
        pkg = REPO_PACKAGES / dirname

        assert pkg.is_dir(), f"{pkg} was not restored"

        manifest_path = pkg / "package.json"
        assert manifest_path.is_file()

        manifest = load_json(manifest_path)

        assert manifest["name"] == package_name
        assert isinstance(manifest["version"], str)
        assert (pkg / "src").is_dir()

    printer = load_json(REPO_PACKAGES / "printer" / "package.json")
    printer_ansi = load_json(REPO_PACKAGES / "printer-ansi" / "package.json")

    deps = printer_ansi.get("dependencies", {})

    assert "@effect/printer" in deps

    spec = deps["@effect/printer"]

    assert spec.startswith("workspace:")

    assert _workspace_spec_satisfies(
        spec,
        printer["version"],
    )


def test_restored_packages_match_upstream_repository() -> None:
    """
    Behavioral test 2: Compares the repaired repo against the upstream repo 
    at the commit, which this task is pinned to (not live HEAD).
    """

    with tempfile.TemporaryDirectory(prefix="effect-upstream-") as tmp:

        upstream = Path(tmp) / "effect"
        upstream.mkdir()

        # Shallow-fetch the exact pinned commit rather than cloning the
        # (large) monorepo's full history or floating HEAD.
        subprocess.run(
            ["git", "init", "-q", str(upstream)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        subprocess.run(
            [
                "git",
                "-C",
                str(upstream),
                "remote",
                "add",
                "origin",
                "https://github.com/Effect-TS/effect.git",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        subprocess.run(
            [
                "git",
                "-C",
                str(upstream),
                "fetch",
                "--depth",
                "1",
                "origin",
                EFFECT_UPSTREAM_COMMIT,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        subprocess.run(
            ["git", "-C", str(upstream), "checkout", "FETCH_HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        upstream_packages = upstream / "packages"

        for name in RESTORED_PACKAGES:
            restored = REPO_PACKAGES / name
            pristine = upstream_packages / name

            assert pristine.is_dir(), (
                f"Upstream package missing: {pristine}"
            )

            assert restored.is_dir(), (
                f"Restored package missing: {restored}"
            )

            _compare_dirs(restored, pristine)




def test_restored_packages_form_a_valid_workspace() -> None:
    """
    Behavioral test 3: verifies that the repaired packages participate correctly
    in a real pnpm workspace by running a genuine pnpm install.
    """

    package_map = {}

    for pkg_dir in REPO_PACKAGES.iterdir():
        manifest_path = pkg_dir / "package.json"
        if not manifest_path.is_file():
            continue
        manifest = load_json(manifest_path)
        package_map[manifest["name"]] = pkg_dir.name

    from collections import deque

    closure = {"printer", "printer-ansi"}
    queue = deque(closure)

    while queue:
        dirname = queue.popleft()
        manifest = load_json(REPO_PACKAGES / dirname / "package.json")

        for section in (
            "dependencies",
            "peerDependencies",
            "devDependencies",
        ):
            for dep, spec in manifest.get(section, {}).items():
                if not spec.startswith("workspace:"):
                    continue

                target = package_map.get(dep)
                if target is not None and target not in closure:
                    closure.add(target)
                    queue.append(target)

    with tempfile.TemporaryDirectory(prefix="printer-workspace-") as tmp:
        workspace = Path(tmp)

        (workspace / "packages").mkdir()

        for dirname in sorted(closure):
            shutil.copytree(
                REPO_PACKAGES / dirname,
                workspace / "packages" / dirname,
                symlinks=True,
            )

        (workspace / "package.json").write_text(
            json.dumps({"private": True}, indent=2) + "\n"
        )

        (workspace / "pnpm-workspace.yaml").write_text(
            "packages:\n"
            "  - 'packages/*'\n"
        )

        install = subprocess.run(
            [
                "pnpm",
                "install",
                "--ignore-scripts",
            ],
            cwd=workspace,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        assert install.returncode == 0, install.stdout

        script = (
            "const {createRequire}=require('module');"
            "const req=createRequire(process.cwd()+'/package.json');"
            "process.stdout.write(req.resolve('@effect/printer'));"
        )

        resolve = subprocess.run(
            [
                "pnpm",
                "--filter",
                "@effect/printer-ansi",
                "exec",
                "node",
                "-e",
                script,
            ],
            cwd=workspace,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        assert resolve.returncode == 0, resolve.stdout

        resolved = Path(resolve.stdout.strip()).resolve()
        expected = (workspace / "packages" / "printer").resolve()

        assert resolved.is_relative_to(expected), (
            f"Expected @effect/printer to resolve inside {expected}, "
            f"got {resolved}"
        )