"""Black-box tests for the offline Rust dependency resolver."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

BIN = os.environ.get("RESOLVER_BIN", "/app/target/debug/prism-dependency-forge")


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n")
    return path


def registry(registry_dir: Path, package: str, body: str) -> Path:
    return write(registry_dir / f"{package}.pkg", body)


def invoke(workspace: Path, registry_dir: Path, lock: Path, report: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            BIN,
            "--workspace",
            str(workspace.resolve()),
            "--registry",
            str(registry_dir.resolve()),
            "--lock",
            str(lock.resolve()),
            "--report",
            str(report.resolve()),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def test_aliases_features_and_transitive_dependencies_are_unified(tmp_path: Path) -> None:
    """Aliases collapse to canonical packages and feature deps are revisited transitively."""
    registry_dir = tmp_path / "registry"
    workspace = write(
        tmp_path / "workspace.txt",
        """
        root app app >=1.0.0,<2.0.0 features=cli
        root helper-kit util >=1.0.0,<3.0.0 features=json
        """,
    )
    registry(
        registry_dir,
        "app",
        """
        version 1.0.0
          dep core >=1.0.0,<2.0.0 features=base
          feature cli terminal >=2.0.0,<3.0.0 features=color
        version 1.2.0
          dep core >=2.0.0,<3.0.0 features=base
          feature cli terminal >=2.0.0,<3.0.0 features=color
        """,
    )
    registry(
        registry_dir,
        "util",
        """
        version 2.0.0
          feature json serde >=1.0.0,<2.0.0
        version 2.2.0
          feature json serde >=1.0.0,<2.0.0
        """,
    )
    registry(registry_dir, "core", "version 2.5.0\n  feature base serde >=1.0.0,<2.0.0")
    registry(registry_dir, "terminal", "version 2.1.0\n  feature color ansi >=1.0.0,<2.0.0")
    registry(registry_dir, "serde", "version 1.0.0\nversion 1.1.0")
    registry(registry_dir, "ansi", "version 1.0.0")
    lock = tmp_path / "lock.json"
    report = tmp_path / "report.json"

    completed = invoke(workspace, registry_dir, lock, report)

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    doc = load(lock)
    assert [pkg["name"] for pkg in doc["packages"]] == ["ansi", "app", "core", "serde", "terminal", "util"]
    packages = {pkg["name"]: pkg for pkg in doc["packages"]}
    assert packages["app"]["version"] == "1.2.0"
    assert packages["app"]["features"] == ["cli"]
    assert packages["util"]["version"] == "2.2.0"
    assert packages["util"]["features"] == ["json"]
    assert packages["core"]["features"] == ["base"]
    assert packages["terminal"]["features"] == ["color"]
    assert packages["serde"]["version"] == "1.1.0"
    assert load(report) == {"conflicts": []}


def test_yanked_versions_are_skipped_and_prereleases_sort_below_final(tmp_path: Path) -> None:
    """Highest valid version ignores yanked releases and handles pre-release ordering."""
    registry_dir = tmp_path / "registry"
    workspace = write(tmp_path / "workspace.txt", "root api api >=1.0.0-alpha,<1.1.0")
    registry(
        registry_dir,
        "api",
        """
        version 1.0.0-alpha
        version 1.0.0
        version 1.0.1 yanked=true
        version 1.1.0-alpha
        """,
    )
    lock = tmp_path / "lock.json"
    report = tmp_path / "report.json"

    completed = invoke(workspace, registry_dir, lock, report)

    assert completed.returncode == 0, completed.stderr
    # In this resolver, 1.1.0-alpha sorts below 1.1.0 and therefore satisfies <1.1.0.
    assert load(lock)["packages"] == [
        {"name": "api", "version": "1.1.0-alpha", "features": [], "dependencies": []}
    ]


def test_conflicting_transitive_constraints_write_report_and_preserve_lock(tmp_path: Path) -> None:
    """Resolution conflicts exit 2, explain the package, and preserve existing lock bytes."""
    registry_dir = tmp_path / "registry"
    workspace = write(
        tmp_path / "workspace.txt",
        """
        root left left >=1.0.0,<2.0.0
        root right right >=1.0.0,<2.0.0
        """,
    )
    registry(registry_dir, "left", "version 1.0.0\n  dep shared >=1.0.0,<2.0.0")
    registry(registry_dir, "right", "version 1.0.0\n  dep shared >=3.0.0,<4.0.0")
    registry(registry_dir, "shared", "version 1.5.0\nversion 3.2.0")
    lock = tmp_path / "lock.json"
    lock.write_bytes(b"previous-lock\n")
    report = tmp_path / "report.json"

    completed = invoke(workspace, registry_dir, lock, report)

    assert completed.returncode == 2
    assert lock.read_bytes() == b"previous-lock\n"
    assert load(report) == {
        "conflicts": [
            {
                "package": "shared",
                "constraints": [">=1.0.0,<2.0.0", ">=3.0.0,<4.0.0"],
                "reason": "no matching version",
            }
        ]
    }


def test_feature_conflict_discovered_after_reprocessing_selected_package(tmp_path: Path) -> None:
    """A feature added later can introduce dependencies that invalidate the graph."""
    registry_dir = tmp_path / "registry"
    workspace = write(
        tmp_path / "workspace.txt",
        """
        root shell shell >=1.0.0,<2.0.0 features=plugins
        root pin shared =1.0.0
        """,
    )
    registry(
        registry_dir,
        "shell",
        """
        version 1.0.0
          dep base >=1.0.0,<2.0.0
          feature plugins shared >=2.0.0,<3.0.0
        """,
    )
    registry(registry_dir, "base", "version 1.0.0")
    registry(registry_dir, "shared", "version 1.0.0\nversion 2.0.0")
    lock = tmp_path / "lock.json"
    lock.write_text("old")
    report = tmp_path / "report.json"

    completed = invoke(workspace, registry_dir, lock, report)

    assert completed.returncode == 2
    assert lock.read_text() == "old"
    assert load(report)["conflicts"][0]["package"] == "shared"


def test_repeated_success_is_byte_identical_and_dependencies_are_sorted(tmp_path: Path) -> None:
    """Lockfile bytes are deterministic across repeated successful runs."""
    registry_dir = tmp_path / "registry"
    workspace = write(tmp_path / "workspace.txt", "root zeta zeta >=1.0.0,<2.0.0 features=extra")
    registry(
        registry_dir,
        "zeta",
        """
        version 1.0.0
          dep beta >=1.0.0,<2.0.0
          dep alpha >=1.0.0,<2.0.0
          feature extra gamma >=1.0.0,<2.0.0
        """,
    )
    registry(registry_dir, "alpha", "version 1.0.0")
    registry(registry_dir, "beta", "version 1.0.0")
    registry(registry_dir, "gamma", "version 1.0.0")
    lock = tmp_path / "lock.json"
    report = tmp_path / "report.json"

    first = invoke(workspace, registry_dir, lock, report)
    first_bytes = lock.read_bytes()
    second = invoke(workspace, registry_dir, lock, report)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert lock.read_bytes() == first_bytes
    zeta = next(pkg for pkg in load(lock)["packages"] if pkg["name"] == "zeta")
    assert [dep["name"] for dep in zeta["dependencies"]] == ["alpha", "beta", "gamma"]
    assert first_bytes.endswith(b"\n")


def test_version_reselection_drops_dependencies_from_no_longer_selected_version(
    tmp_path: Path,
) -> None:
    """When constraints force a different version, deps from the old version are no longer active."""
    registry_dir = tmp_path / "registry"
    workspace = write(
        tmp_path / "workspace.txt",
        """
        root app app >=1.0.0,<3.0.0 features=tls
        root policy policy =1.0.0
        """,
    )
    registry(
        registry_dir,
        "app",
        """
        version 1.5.0
          feature tls crypto >=1.0.0,<2.0.0
        version 2.4.0
          feature tls crypto >=2.0.0,<3.0.0
        """,
    )
    registry(registry_dir, "policy", "version 1.0.0\n  dep app >=1.0.0,<2.0.0")
    registry(registry_dir, "crypto", "version 1.8.0\nversion 2.5.0")
    lock = tmp_path / "lock.json"
    report = tmp_path / "report.json"

    completed = invoke(workspace, registry_dir, lock, report)

    assert completed.returncode == 0, completed.stderr
    packages = {pkg["name"]: pkg for pkg in load(lock)["packages"]}
    assert packages["app"]["version"] == "1.5.0"
    assert packages["crypto"]["version"] == "1.8.0"
    assert packages["app"]["dependencies"] == [{"name": "crypto", "version": "1.8.0"}]
    assert "2.5.0" not in lock.read_text()


def test_alias_feature_union_can_change_the_selected_dependency_version(tmp_path: Path) -> None:
    """Feature requests from separate aliases are merged before dependency selection settles."""
    registry_dir = tmp_path / "registry"
    workspace = write(
        tmp_path / "workspace.txt",
        """
        root ui-a widget >=1.0.0,<2.0.0 features=sqlite
        root ui-b widget >=1.0.0,<2.0.0 features=postgres
        """,
    )
    registry(
        registry_dir,
        "widget",
        """
        version 1.0.0
          feature sqlite db >=1.0.0,<2.0.0
          feature postgres db >=2.0.0,<3.0.0
        version 1.1.0
          feature sqlite db >=2.0.0,<3.0.0
          feature postgres db >=2.0.0,<3.0.0
        """,
    )
    registry(registry_dir, "db", "version 1.9.0\nversion 2.1.0")
    lock = tmp_path / "lock.json"
    report = tmp_path / "report.json"

    completed = invoke(workspace, registry_dir, lock, report)

    assert completed.returncode == 0, completed.stderr
    packages = {pkg["name"]: pkg for pkg in load(lock)["packages"]}
    assert packages["widget"]["features"] == ["postgres", "sqlite"]
    assert packages["widget"]["version"] == "1.1.0"
    assert packages["db"]["version"] == "2.1.0"


def test_multiple_conflicts_are_reported_in_stable_package_order(tmp_path: Path) -> None:
    """Independent unsatisfied packages appear in a deterministic conflict report."""
    registry_dir = tmp_path / "registry"
    workspace = write(
        tmp_path / "workspace.txt",
        """
        root alpha alpha >=1.0.0,<2.0.0
        root beta beta >=1.0.0,<2.0.0
        """,
    )
    registry(registry_dir, "alpha", "version 1.0.0\n  dep shared_b >=3.0.0,<4.0.0")
    registry(registry_dir, "beta", "version 1.0.0\n  dep shared_a >=5.0.0,<6.0.0")
    registry(registry_dir, "shared_a", "version 1.0.0\nversion 2.0.0")
    registry(registry_dir, "shared_b", "version 1.0.0\nversion 2.0.0")
    lock = tmp_path / "lock.json"
    lock.write_text("previous")
    report = tmp_path / "report.json"

    completed = invoke(workspace, registry_dir, lock, report)

    assert completed.returncode == 2
    assert lock.read_text() == "previous"
    assert load(report) == {
        "conflicts": [
            {
                "package": "shared_a",
                "constraints": [">=5.0.0,<6.0.0"],
                "reason": "no matching version",
            },
            {
                "package": "shared_b",
                "constraints": [">=3.0.0,<4.0.0"],
                "reason": "no matching version",
            },
        ]
    }


def test_missing_package_and_bad_inputs_are_usage_failures_without_lock_changes(tmp_path: Path) -> None:
    """Missing packages, relative paths, and malformed records exit 2 without changing lock."""
    registry_dir = tmp_path / "registry"
    workspace = write(tmp_path / "workspace.txt", "root missing missing >=1.0.0,<2.0.0")
    registry_dir.mkdir()
    lock = tmp_path / "lock.json"
    lock.write_text("keep")
    report = tmp_path / "report.json"

    missing = invoke(workspace, registry_dir, lock, report)
    relative = subprocess.run(
        [
            BIN,
            "--workspace",
            "workspace.txt",
            "--registry",
            str(registry_dir.resolve()),
            "--lock",
            str(lock.resolve()),
            "--report",
            str(report.resolve()),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    bad_workspace = write(tmp_path / "bad-workspace.txt", "root only-two-fields")
    malformed = invoke(bad_workspace, registry_dir, lock, report)

    assert missing.returncode == 2
    assert relative.returncode == 2
    assert malformed.returncode == 2
    assert lock.read_text() == "keep"


def test_output_failure_is_exit_one_and_preserves_existing_lock(tmp_path: Path) -> None:
    """Non-resolution output errors exit 1 and do not clobber the lock."""
    registry_dir = tmp_path / "registry"
    workspace = write(tmp_path / "workspace.txt", "root app app >=1.0.0,<2.0.0")
    registry(registry_dir, "app", "version 1.0.0")
    lock = tmp_path / "lock.json"
    lock.write_text("old-lock")
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("block")
    report = blocked / "report.json"

    completed = invoke(workspace, registry_dir, lock, report)

    assert completed.returncode == 1
    assert lock.read_text() == "old-lock"
    assert blocked.read_text() == "block"


def test_success_from_absent_lock_creates_parent_directories(tmp_path: Path) -> None:
    """A successful run may create missing lock and report parent directories."""
    registry_dir = tmp_path / "registry"
    workspace = write(tmp_path / "workspace.txt", "root app app =1.0.0")
    registry(registry_dir, "app", "version 1.0.0")
    lock = tmp_path / "nested/locks/lock.json"
    report = tmp_path / "nested/reports/report.json"

    completed = invoke(workspace, registry_dir, lock, report)

    assert completed.returncode == 0, completed.stderr
    assert load(lock)["packages"][0]["name"] == "app"
    assert load(report) == {"conflicts": []}
