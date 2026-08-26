"""Seventy high-interaction cases for the offline CMake/vcpkg binary-cache release."""

from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

import pytest


APP = Path("/app")
DIST = APP / "dist"
MATRIX = APP / "config" / "release_matrix.csv"
COMPONENTS = APP / "config" / "components.csv"
LOCKS = APP / "config" / "locks.csv"
EDGES = APP / "config" / "dependency_edges.csv"
SMOKE = APP / "data" / "smoke_specs"
NORMALIZED_MTIME = 1767225600

PREVIEW_ORDER = [
    "profile",
    "target",
    "channel",
    "feature_set",
    "max_runtime_kb",
    "allow_dev",
    "components",
    "dependency_edges",
    "license_summary",
    "owners",
    "policy_checks",
    "warnings",
    "totals",
]
TOTALS_ORDER = [
    "component_count",
    "direct_lock_count",
    "runtime_kb",
    "critical_count",
    "license_count",
    "dev_component_count",
    "edge_count",
    "policy_pass",
    "risk_score",
]
WORKSPACE_NAMES = ["releasekit-cli", "releasekit-core", "releasekit-table"]
COMPONENT_ORDER = [
    "name",
    "version",
    "kind",
    "license",
    "critical",
    "size_kb",
    "checksum",
    "source",
    "direct",
]
BUNDLE_ENTRY_ORDER = [
    "profile",
    "channel",
    "target",
    "archive",
    "archive_sha256",
    "binary_sha256",
    "policy_sha256",
    "audit_preview_sha256",
    "component_count",
    "runtime_kb",
    "edge_count",
    "risk_score",
]


def run_release() -> None:
    env = os.environ.copy()
    env["CARGO_NET_OFFLINE"] = "true"
    subprocess.run(
        ["bash", "/app/scripts/release.sh"], cwd=APP, env=env, check=True, timeout=300
    )
    assert_complete_release_contract()


@pytest.fixture(scope="session")
def release_dist() -> Path:
    run_release()
    return DIST


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bundle_dir(profile: str, dist: Path = DIST) -> Path:
    return dist / "bundles" / f"releasekit-{profile}"


def manifest(dist: Path = DIST) -> dict:
    return json.loads((dist / "release-manifest.json").read_text())


def preview(profile: str, dist: Path = DIST) -> dict:
    return json.loads(
        (bundle_dir(profile, dist) / "share" / "audit-preview.json").read_text()
    )


def assert_single_lf(path: Path) -> None:
    raw = path.read_bytes()
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")


def assert_checksum_index(dist: Path = DIST) -> None:
    rows = (dist / "checksums.sha256").read_text().splitlines()
    expected = sorted(
        path.relative_to(dist).as_posix()
        for path in dist.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    )
    observed = [row.split(maxsplit=1)[1] for row in rows]
    assert observed == expected
    for row in rows:
        digest, relative = row.split(maxsplit=1)
        assert digest == sha256(dist / relative)


def dist_snapshot(dist: Path = DIST) -> dict[str, str]:
    return {
        path.relative_to(dist).as_posix(): sha256(path)
        for path in dist.rglob("*")
        if path.is_file()
    }


def csv_bytes(
    headers: list[str], rows: list[list[object]], newline: str = "\n"
) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator=newline)
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue().encode()


def filtered_csv_bytes(path: Path, keep) -> bytes:
    """Preserve source records exactly; task inputs never quote record endings."""
    lines = path.read_bytes().splitlines(keepends=True)
    records: list[tuple[dict[str, str], bytes]] = []
    header: list[str] | None = None
    header_raw = b""
    for raw in lines:
        body = raw.rstrip(b"\r\n")
        if not body:
            continue
        values = next(csv.reader([body.decode()]))
        if header is None:
            header = values
            header_raw = raw
        else:
            records.append((dict(zip(header, values, strict=True)), raw))
    assert header is not None
    return header_raw + b"".join(raw for row, raw in records if keep(row))


def assert_complete_release_contract() -> None:
    """Cross-check the complete release surface after every successful rebuild."""
    matrix_rows = read_csv(MATRIX)
    component_rows = read_csv(COMPONENTS)
    lock_rows = read_csv(LOCKS)
    effective_components = {row["component"]: row for row in component_rows}
    data = manifest()

    assert list(data) == ["format_version", "package", "workspace", "bundles"]
    assert data["format_version"] == 1
    assert [row["name"] for row in data["workspace"]] == WORKSPACE_NAMES
    assert all(
        list(row) == ["name", "version", "license", "dependencies"]
        for row in data["workspace"]
    )
    assert [row["profile"] for row in data["bundles"]] == [
        row["profile"] for row in matrix_rows
    ]
    assert all(list(row) == BUNDLE_ENTRY_ORDER for row in data["bundles"])
    assert_single_lf(DIST / "release-manifest.json")

    archives = {row["archive"] for row in data["bundles"]}
    assert {path.name for path in DIST.iterdir() if path.is_file()} == {
        "release-manifest.json",
        "checksums.sha256",
        *archives,
    }
    assert {path.name for path in DIST.iterdir() if path.is_dir()} == {"bundles"}
    assert {path.name for path in (DIST / "bundles").iterdir()} == {
        f"releasekit-{row['profile']}" for row in matrix_rows
    }

    manifest_by_profile = {row["profile"]: row for row in data["bundles"]}
    for matrix_row in matrix_rows:
        profile = matrix_row["profile"]
        root = bundle_dir(profile)
        expected_files = {
            "bin/releasekit",
            "share/release_matrix.csv",
            "share/components.csv",
            "share/locks.csv",
            "share/dependencies.csv",
            "share/policy.json",
            "share/run-smoke.sh",
            "share/audit-preview.json",
            f"share/smoke_specs/{profile}.csv",
            "LICENSES.txt",
            "VERSION",
        }
        present = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
        assert present == expected_files
        assert (
            root / "share" / "release_matrix.csv"
        ).read_bytes() == MATRIX.read_bytes()
        assert (root / "share" / "locks.csv").read_bytes() == filtered_csv_bytes(
            LOCKS, lambda row: row["profile"] == profile
        )
        selected_names = {
            row["component"] for row in lock_rows if row["profile"] == profile
        } & effective_components.keys()
        assert (root / "share" / "components.csv").read_bytes() == filtered_csv_bytes(
            COMPONENTS, lambda row: row["component"] in selected_names
        )
        assert (root / "share" / "dependencies.csv").read_bytes() == filtered_csv_bytes(
            EDGES, lambda row: row["profile"] in {"*", profile}
        )
        assert (root / "share" / "smoke_specs" / f"{profile}.csv").read_bytes() == (
            SMOKE / f"{profile}.csv"
        ).read_bytes()

        policy_path = root / "share" / "policy.json"
        policy = json.loads(policy_path.read_text())
        assert list(policy) == [
            "profile",
            "channel",
            "target",
            "feature_set",
            "max_runtime_kb",
            "allow_dev",
            "blocked_license",
        ]
        assert policy == {
            "profile": profile,
            "channel": matrix_row["channel"],
            "target": matrix_row["target"],
            "feature_set": matrix_row["feature_set"],
            "max_runtime_kb": int(matrix_row["max_runtime_kb"]),
            "allow_dev": matrix_row["allow_dev"] in {"true", "yes", "1"},
            "blocked_license": matrix_row["blocked_license"],
        }
        assert_single_lf(policy_path)

        audit_path = root / "share" / "audit-preview.json"
        audit = json.loads(audit_path.read_text())
        assert list(audit) == PREVIEW_ORDER
        assert list(audit["totals"]) == TOTALS_ORDER
        assert all(
            list(component) == COMPONENT_ORDER for component in audit["components"]
        )
        assert audit["dependency_edges"] == sorted(audit["dependency_edges"])
        assert audit["warnings"] == sorted(set(audit["warnings"]))
        assert audit["license_summary"] == sorted(set(audit["license_summary"]))
        assert audit["owners"] == sorted(set(audit["owners"]))
        assert_single_lf(audit_path)

        licenses = sorted(
            {effective_components[name]["license"] for name in selected_names}
        )
        expected_licenses = (
            b"" if not licenses else ("\n".join(licenses) + "\n").encode()
        )
        assert (root / "LICENSES.txt").read_bytes() == expected_licenses
        assert (root / "VERSION").read_bytes() == (
            data["package"]["version"] + "\n"
        ).encode()
        assert (root / "bin" / "releasekit").read_bytes().startswith(b"\x7fELF")
        assert (root / "share" / "run-smoke.sh").read_bytes().startswith(b"#!/bin/sh\n")

        entry = manifest_by_profile[profile]
        assert entry["channel"] == matrix_row["channel"]
        assert entry["target"] == matrix_row["target"]
        assert entry["archive_sha256"] == sha256(DIST / entry["archive"])
        assert entry["binary_sha256"] == sha256(root / "bin" / "releasekit")
        assert entry["policy_sha256"] == sha256(policy_path)
        assert entry["audit_preview_sha256"] == sha256(audit_path)
        for key in ["component_count", "runtime_kb", "edge_count", "risk_score"]:
            assert entry[key] == audit["totals"][key]

        root_name = f"releasekit-{profile}"
        with tarfile.open(DIST / entry["archive"], "r:gz") as archive:
            members = archive.getmembers()
            assert members[0].isdir() and members[0].name == root_name
            assert [member.name for member in members] == sorted(
                member.name for member in members
            )
            assert all(
                (member.uid, member.gid, member.mtime) == (0, 0, NORMALIZED_MTIME)
                for member in members
            )
            archived_files = {
                member.name[len(root_name) :].lstrip("/"): archive.extractfile(
                    member
                ).read()
                for member in members
                if member.isfile()
            }
            assert archived_files == {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            for member in members:
                relative = member.name[len(root_name) :].lstrip("/")
                expected_mode = (
                    0o755
                    if member.isdir()
                    or relative in {"bin/releasekit", "share/run-smoke.sh"}
                    else 0o644
                )
                assert member.mode & 0o777 == expected_mode

    assert_checksum_index()
    assert_single_lf(DIST / "checksums.sha256")


@contextmanager
def patched_app_files(updates: dict[Path, str | bytes]):
    originals: dict[Path, bytes] = {}
    created: list[Path] = []
    for path in updates:
        if path.exists():
            originals[path] = path.read_bytes()
        else:
            created.append(path)
    try:
        for path, content in updates.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(
                content if isinstance(content, bytes) else content.encode()
            )
        run_release()
        yield DIST
    finally:
        for path, content in originals.items():
            path.write_bytes(content)
        for path in created:
            if path.exists():
                path.unlink()
        run_release()


@contextmanager
def hidden_build_sources(suffix: str):
    pairs = [
        (APP / "target", APP / f"target.hidden-{suffix}"),
        (DIST, APP / f"dist.hidden-{suffix}"),
        *[
            (path, path.with_name(f"{path.name}.hidden-{suffix}"))
            for path in (MATRIX, COMPONENTS, LOCKS, EDGES)
        ],
    ]
    moved: list[tuple[Path, Path]] = []
    try:
        for source, destination in pairs:
            source.rename(destination)
            moved.append((source, destination))
        yield
    finally:
        for source, destination in reversed(moved):
            destination.rename(source)


def run_custom_audit(
    release_dist: Path,
    tmp_path: Path,
    profile: str,
    matrix_text: str,
    components_text: str,
    locks_text: str,
    edges_text: str,
    extra_args: list[str] | None = None,
) -> tuple[dict, bytes, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {}
    for name, text in {
        "matrix": matrix_text,
        "components": components_text,
        "locks": locks_text,
        "edges": edges_text,
    }.items():
        path = tmp_path / f"{name}.csv"
        path.write_bytes(text.encode())
        files[name] = path
    out = tmp_path / "nested" / "audit.json"
    command = [
        str(bundle_dir("edge", release_dist) / "bin" / "releasekit"),
        "audit",
        "--profile",
        profile,
        "--matrix",
        str(files["matrix"]),
        "--components",
        str(files["components"]),
        "--locks",
        str(files["locks"]),
        "--edges",
        str(files["edges"]),
        "--out",
        str(out),
    ]
    if extra_args:
        command.extend(extra_args)
    subprocess.run(command, check=True)
    raw = out.read_bytes()
    return json.loads(raw), raw, out


def test_baseline_contract_cross_checks_all_artifacts(
    release_dist: Path,
) -> None:
    """Verify baseline contract cross checks all artifacts."""
    data = manifest(release_dist)
    assert list(data) == ["format_version", "package", "workspace", "bundles"]
    assert data["format_version"] == 1
    assert data["package"] == {
        "name": "releasekit-cli",
        "version": "0.7.0",
        "target": "x86_64-unknown-linux-gnu",
    }
    assert [row["name"] for row in data["workspace"]] == WORKSPACE_NAMES
    assert [row["profile"] for row in data["bundles"]] == [
        "edge",
        "fleet",
        "audit",
        "sandbox",
    ]
    assert_single_lf(release_dist / "release-manifest.json")
    assert_checksum_index(release_dist)
    for entry in data["bundles"]:
        root = bundle_dir(entry["profile"], release_dist)
        required = {
            "bin/releasekit",
            "share/release_matrix.csv",
            "share/components.csv",
            "share/locks.csv",
            "share/dependencies.csv",
            "share/policy.json",
            "share/run-smoke.sh",
            "share/audit-preview.json",
            f"share/smoke_specs/{entry['profile']}.csv",
            "LICENSES.txt",
            "VERSION",
        }
        present = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
        assert present == required
        audit = preview(entry["profile"], release_dist)
        assert list(audit) == PREVIEW_ORDER
        assert list(audit["totals"]) == TOTALS_ORDER
        assert entry["component_count"] == audit["totals"]["component_count"]
        assert entry["risk_score"] == audit["totals"]["risk_score"]
        assert entry["archive_sha256"] == sha256(release_dist / entry["archive"])
        assert_single_lf(root / "share" / "policy.json")
        assert_single_lf(root / "share" / "audit-preview.json")


def test_final_catalog_row_controls_every_derived_axis(
    release_dist: Path,
) -> None:
    """Verify final catalog row controls every derived axis."""
    matrix = MATRIX.read_text() + "benitoite,qa,linux-x86_64,core,30,false,GPL-3.0\n"
    components = COMPONENTS.read_text() + (
        "beni-tool,1.0.0,MIT,doc,no,1,linux-x86_64,old-owner\n"
        "beni-tool,2.0.0,GPL-3.0,dev,TRUE,40,linux-arm64,final-owner\n"
    )
    locks = LOCKS.read_text() + "benitoite,beni-tool,2.0.0,sha-final,cache/final.pkg\n"
    with patched_app_files(
        {
            MATRIX: matrix,
            COMPONENTS: components,
            LOCKS: locks,
            SMOKE / "benitoite.csv": "profile,expected\nbenitoite,ok\n",
        }
    ):
        root = bundle_dir("benitoite")
        audit = preview("benitoite")
        assert [
            row["version"]
            for row in read_csv(root / "share" / "components.csv")
            if row["component"] == "beni-tool"
        ] == ["1.0.0", "2.0.0"]
        assert audit["components"] == [
            {
                "name": "beni-tool",
                "version": "2.0.0",
                "kind": "dev",
                "license": "GPL-3.0",
                "critical": True,
                "size_kb": 40,
                "checksum": "sha-final",
                "source": "cache/final.pkg",
                "direct": True,
            }
        ]
        assert audit["owners"] == ["final-owner"]
        assert audit["license_summary"] == ["GPL-3.0"]
        assert (root / "LICENSES.txt").read_bytes() == b"GPL-3.0\n"
        assert audit["warnings"] == [
            "blocked_license:beni-tool:GPL-3.0",
            "dev_dependency:beni-tool",
            "platform:beni-tool:linux-x86_64",
            "runtime_size:40:30",
        ]
        assert audit["totals"]["risk_score"] == 145


def test_lock_history_ghosts_and_required_edges_compose(
    release_dist: Path,
) -> None:
    """Verify lock history ghosts and required edges compose."""
    matrix = MATRIX.read_text() + "chrysoberyl,qa,linux-x86_64,core,999,true,NOPE\n"
    locks = LOCKS.read_text() + (
        "chrysoberyl,triplet-core,1.0.0,good,cache/good.pkg\n"
        "chrysoberyl,triplet-core,9.9.9,bad,cache/final.pkg\n"
        "chrysoberyl,ghost-cache,1.0.0,g1,cache/g1.pkg\n"
        "chrysoberyl,ghost-cache,2.0.0,g2,cache/g2.pkg\n"
    )
    with patched_app_files(
        {
            MATRIX: matrix,
            LOCKS: locks,
            SMOKE / "chrysoberyl.csv": "profile,expected\nchrysoberyl,ok\n",
        }
    ):
        root = bundle_dir("chrysoberyl")
        audit = preview("chrysoberyl")
        assert len(read_csv(root / "share" / "locks.csv")) == 4
        assert audit["components"][0]["checksum"] == "bad"
        assert audit["totals"]["direct_lock_count"] == 1
        assert audit["warnings"] == [
            "missing_component:ghost-cache",
            "missing_required_edge:triplet-core->manifest-portfile",
            "missing_required_edge:triplet-core->source-mirror",
            "version_mismatch:triplet-core:9.9.9:1.0.0",
        ]
        assert audit["policy_checks"][2] == "locked_versions:fail"
        assert audit["totals"]["risk_score"] == 129


def test_global_profile_and_exact_duplicate_edges_keep_multiplicity(
    release_dist: Path,
) -> None:
    """Verify global profile and exact duplicate edges keep multiplicity."""
    matrix = MATRIX.read_text() + "diaspore,qa,linux-x86_64,core,100,true,NOPE\n"
    components = (
        COMPONENTS.read_text()
        + "dia-a,1,MIT,runtime,no,10,linux-x86_64,t\ndia-b,1,MIT,runtime,no,10,linux-x86_64,t\n"
    )
    locks = LOCKS.read_text() + "diaspore,dia-a,1,a,a\ndiaspore,dia-b,1,b,b\n"
    edges = EDGES.read_text() + (
        "*,dia-a,dia-b,requires,runtime,no\n"
        "diaspore,dia-a,dia-b,requires,runtime,no\n"
        "diaspore,dia-a,dia-b,requires,runtime,no\n"
    )
    with patched_app_files(
        {
            MATRIX: matrix,
            COMPONENTS: components,
            LOCKS: locks,
            EDGES: edges,
            SMOKE / "diaspore.csv": "profile,expected\ndiaspore,ok\n",
        }
    ):
        audit = preview("diaspore")
        assert audit["dependency_edges"] == ["dia-a->dia-b:requires"] * 3
        assert audit["totals"]["edge_count"] == 3
        assert audit["totals"]["risk_score"] == 6
        assert [
            row["parent"]
            for row in read_csv(bundle_dir("diaspore") / "share" / "dependencies.csv")
            if row["parent"] == "dia-a"
        ] == ["dia-a"] * 3


def test_parallel_rows_balance_indegree_before_tail(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify parallel rows balance indegree before tail."""
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "eudialyte",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\neudialyte,qa,linux-x86_64,core+gpu,100,true,NOPE\n",
        "component,version,license,kind,critical,size_kb,platforms,owner\neu-a,1,MIT,runtime,no,1,linux-x86_64,t\neu-b,1,MIT,runtime,no,1,linux-x86_64,t\neu-c,1,MIT,runtime,no,1,linux-x86_64,t\n",
        "profile,component,version,checksum,source\neudialyte,eu-a,1,a,a\neudialyte,eu-b,1,b,b\neudialyte,eu-c,1,c,c\n",
        "profile,parent,child,relation,scope,optional\neudialyte,eu-a,eu-b,embeds,runtime,no\neudialyte,eu-a,eu-b,requires,feature:gpu,no\neudialyte,eu-a,eu-b,requires,runtime,no\neudialyte,eu-b,eu-c,requires,runtime,no\n",
    )
    assert audit["warnings"] == []
    assert [row["name"] for row in audit["components"]] == ["eu-a", "eu-b", "eu-c"]
    assert audit["dependency_edges"] == [
        "eu-a->eu-b:embeds",
        "eu-a->eu-b:requires",
        "eu-a->eu-b:requires",
        "eu-b->eu-c:requires",
    ]


def test_condensation_dag_separates_two_cycles_self_loop_and_descendants(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify condensation dag separates two cycles self loop and descendants."""
    names = ["fa-a", "fa-b", "fa-c", "fa-d", "fa-e", "fa-f", "fa-g", "fa-root"]
    components = (
        "component,version,license,kind,critical,size_kb,platforms,owner\n"
        + "".join(f"{name},1,MIT,runtime,no,1,linux-x86_64,t\n" for name in names)
    )
    locks = "profile,component,version,checksum,source\n" + "".join(
        f"fayalite,{name},1,{name},{name}\n" for name in names
    )
    edges = (
        "profile,parent,child,relation,scope,optional\n"
        "fayalite,fa-root,fa-a,r,runtime,no\nfayalite,fa-root,fa-c,r,runtime,no\n"
        "fayalite,fa-root,fa-g,r,runtime,no\n"
        "fayalite,fa-a,fa-b,r,runtime,no\nfayalite,fa-b,fa-a,r,runtime,no\n"
        "fayalite,fa-c,fa-d,r,runtime,no\nfayalite,fa-d,fa-c,r,runtime,no\n"
        "fayalite,fa-b,fa-e,r,runtime,no\nfayalite,fa-e,fa-f,r,runtime,no\n"
        "fayalite,fa-g,fa-g,self,runtime,no\n"
    )
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "fayalite",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\nfayalite,qa,linux-x86_64,core,100,true,NOPE\n",
        components,
        locks,
        edges,
    )
    assert [row["name"] for row in audit["components"]] == [
        "fa-root",
        "fa-a",
        "fa-b",
        "fa-c",
        "fa-d",
        "fa-e",
        "fa-f",
        "fa-g",
    ]
    assert audit["warnings"] == [
        "dependency_cycle:fa-a|fa-b",
        "dependency_cycle:fa-c|fa-d",
        "dependency_cycle:fa-g",
    ]
    assert audit["policy_checks"][2] == "locked_versions:ok"
    assert audit["totals"]["edge_count"] == 10
    assert audit["totals"]["risk_score"] == 113


def test_cycle_does_not_absorb_acyclic_tail_in_condensation_order(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify cycle does not absorb acyclic tail in condensation order."""
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "grandidierite",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\ngrandidierite,qa,linux-x86_64,core,100,true,NOPE\n",
        "component,version,license,kind,critical,size_kb,platforms,owner\ng-a,1,MIT,runtime,no,1,linux-x86_64,t\ng-b,1,MIT,runtime,no,1,linux-x86_64,t\ng-c,1,MIT,runtime,no,1,linux-x86_64,t\ng-root-a,1,MIT,runtime,no,1,linux-x86_64,t\ng-root-z,1,MIT,runtime,no,1,linux-x86_64,t\n",
        "profile,component,version,checksum,source\ngrandidierite,g-a,1,a,a\ngrandidierite,g-b,1,b,b\ngrandidierite,g-c,1,c,c\ngrandidierite,g-root-a,1,ra,ra\ngrandidierite,g-root-z,1,rz,rz\n",
        "profile,parent,child,relation,scope,optional\ngrandidierite,g-root-a,g-a,r,runtime,no\ngrandidierite,g-root-z,g-b,r,runtime,no\ngrandidierite,g-a,g-b,r,runtime,no\ngrandidierite,g-b,g-a,r,runtime,no\ngrandidierite,g-b,g-c,r,runtime,no\n",
    )
    assert [row["name"] for row in audit["components"]] == [
        "g-root-a",
        "g-root-z",
        "g-a",
        "g-b",
        "g-c",
    ]
    assert audit["warnings"] == ["dependency_cycle:g-a|g-b"]


def test_exact_feature_scopes_silence_inactive_missing_children(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify exact feature scopes silence inactive missing children."""
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "hackmanite",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\nhackmanite,canary,linux-x86_64,core+gpu,100,true,NOPE\n",
        "component,version,license,kind,critical,size_kb,platforms,owner\nh-a,1,MIT,runtime,no,1,linux-x86_64,t\nh-b,1,MIT,runtime,no,1,linux-x86_64,t\n",
        "profile,component,version,checksum,source\nhackmanite,h-a,1,a,a\nhackmanite,h-b,1,b,b\n",
        "profile,parent,child,relation,scope,optional\nhackmanite,h-a,h-b,active,feature:gpu,no\nhackmanite,h-a,ghost-prefix,r,feature:gp,no\nhackmanite,h-a,ghost-negated,r,!feature:gpu,no\nhackmanite,h-a,ghost-channel,r,channel:stable,no\nhackmanite,h-a,ghost-optional,r,feature:gpu,yes\n",
    )
    assert audit["dependency_edges"] == ["h-a->h-b:active"]
    assert audit["warnings"] == []


def test_nested_cfg_all_any_not_drives_edges_and_warnings(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify nested cfg all any not drives edges and warnings."""
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "jeremejevite",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\njeremejevite,canary,linux-arm64,core+signed,100,true,NOPE\n",
        "component,version,license,kind,critical,size_kb,platforms,owner\nj-a,1,MIT,runtime,no,1,linux-arm64,t\nj-b,1,MIT,runtime,no,1,linux-arm64,t\n",
        "profile,component,version,checksum,source\njeremejevite,j-a,1,a,a\njeremejevite,j-b,1,b,b\n",
        'profile,parent,child,relation,scope,optional\njeremejevite,j-a,j-b,active,"cfg:all(feature:signed,any(target:linux-x86_64,target:linux-arm64),not(channel:stable))",no\njeremejevite,j-a,ghost-active,r,"cfg:any(channel:stable,all(feature:signed,target:linux-arm64))",no\njeremejevite,j-a,ghost-inactive,r,"cfg:all(feature:signed,target:linux-x86_64)",no\n',
    )
    assert audit["dependency_edges"] == ["j-a->j-b:active"]
    assert audit["warnings"] == ["missing_required_edge:j-a->ghost-active"]
    assert audit["policy_checks"][2] == "locked_versions:fail"


def test_quoted_crlf_direct_audit_preserves_decoded_values(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify quoted crlf direct audit preserves decoded values."""
    audit, raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "kornerupine",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\r\nkornerupine,qa,linux-x86_64,core,100,true,NOPE\r\n",
        'component,version,license,kind,critical,size_kb,platforms,owner\r\nk-a,1,MIT,runtime,no,1,linux-x86_64,"Cache, ""Red"" Team"\r\nk-b,1,MIT,runtime,no,1,linux-x86_64,Plain\r\n',
        'profile,component,version,checksum,source\r\nkornerupine,k-a,1,a,"cache/a, ""signed"".blob"\r\nkornerupine,k-b,1,b,b.blob\r\n',
        'profile,parent,child,relation,scope,optional\r\nkornerupine,k-a,k-b,"exports,verified",runtime,no\r\n',
    )
    assert audit["owners"] == ['Cache, "Red" Team', "Plain"]
    assert audit["components"][0]["source"] == 'cache/a, "signed".blob'
    assert audit["dependency_edges"] == ["k-a->k-b:exports,verified"]
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")


def test_full_release_handles_quoted_metadata_and_cfg_commas(
    release_dist: Path,
) -> None:
    """Verify full release handles quoted metadata and cfg commas."""
    matrix = (
        MATRIX.read_text() + "larimar,canary,linux-x86_64,core+signed,100,true,NOPE\n"
    )
    components = COMPONENTS.read_text() + (
        'lari-a,1,MIT,runtime,no,10,linux-x86_64,"Build, ""Blue"""\n'
        "lari-b,1,BSD-3-Clause,runtime,no,10,linux-x86_64,Build\n"
    )
    locks = (
        LOCKS.read_text()
        + 'larimar,lari-a,1,a,"cache/a, ""signed"".blob"\nlarimar,lari-b,1,b,b.blob\n'
    )
    edges = (
        EDGES.read_text()
        + 'larimar,lari-a,lari-b,"exports,verified","cfg:all(feature:signed,any(channel:canary,target:linux-arm64),not(feature:debug))",no\n'
    )
    with patched_app_files(
        {
            MATRIX: matrix,
            COMPONENTS: components,
            LOCKS: locks,
            EDGES: edges,
            SMOKE / "larimar.csv": "profile,expected\nlarimar,ok\n",
        }
    ):
        root = bundle_dir("larimar")
        audit = preview("larimar")
        assert audit["owners"] == ["Build", 'Build, "Blue"']
        assert audit["components"][0]["source"] == 'cache/a, "signed".blob'
        assert audit["dependency_edges"] == ["lari-a->lari-b:exports,verified"]
        assert (
            len(
                [
                    row
                    for row in read_csv(root / "share" / "components.csv")
                    if row["component"].startswith("lari-")
                ]
            )
            == 2
        )
        assert_checksum_index()


def test_warning_stack_policy_order_and_risk_arithmetic(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify warning stack policy order and risk arithmetic."""
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "moldavite",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\nmoldavite,qa,linux-x86_64,core,10,false,GPL-3.0\n",
        "component,version,license,kind,critical,size_kb,platforms,owner\nm-tool,2,GPL-3.0,dev,yes,40,linux-arm64,t\n",
        "profile,component,version,checksum,source\nmoldavite,m-tool,1,m,m\nmoldavite,m-ghost,1,g,g\n",
        "profile,parent,child,relation,scope,optional\nmoldavite,m-tool,m-child,requires,runtime,no\n",
    )
    assert audit["warnings"] == [
        "blocked_license:m-tool:GPL-3.0",
        "dev_dependency:m-tool",
        "missing_component:m-ghost",
        "missing_required_edge:m-tool->m-child",
        "platform:m-tool:linux-x86_64",
        "runtime_size:40:10",
        "version_mismatch:m-tool:1:2",
    ]
    assert audit["policy_checks"] == [
        "blocked_license:fail",
        "dev_policy:fail",
        "locked_versions:fail",
        "platforms:fail",
        "runtime_size:fail:40/10",
    ]
    assert audit["totals"] == {
        "component_count": 1,
        "direct_lock_count": 1,
        "runtime_kb": 40,
        "critical_count": 1,
        "license_count": 1,
        "dev_component_count": 1,
        "edge_count": 0,
        "policy_pass": False,
        "risk_score": 238,
    }


def test_repeated_flags_select_final_inputs_and_single_lf(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify repeated flags select final inputs and single lf."""
    wrong = tmp_path / "wrong.csv"
    wrong.write_text(
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\nwrong,qa,none,none,1,false,MIT\n"
    )
    first_out = tmp_path / "first.json"
    final_out = tmp_path / "final" / "audit.json"
    matrix = tmp_path / "matrix.csv"
    components = tmp_path / "components.csv"
    locks = tmp_path / "locks.csv"
    edges = tmp_path / "edges.csv"
    matrix.write_text(
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\nnatrolite,qa,linux-x86_64,core,10,true,NOPE\n"
    )
    components.write_text(
        "component,version,license,kind,critical,size_kb,platforms,owner\nn-a,1,MIT,runtime,no,1,linux-x86_64,t\n"
    )
    locks.write_text("profile,component,version,checksum,source\nnatrolite,n-a,1,a,a\n")
    edges.write_text("profile,parent,child,relation,scope,optional\n")
    subprocess.run(
        [
            str(bundle_dir("edge", release_dist) / "bin" / "releasekit"),
            "audit",
            "--profile",
            "wrong",
            "--profile",
            "natrolite",
            "--matrix",
            str(wrong),
            "--matrix",
            str(matrix),
            "--components",
            str(COMPONENTS),
            "--components",
            str(components),
            "--locks",
            str(LOCKS),
            "--locks",
            str(locks),
            "--edges",
            str(EDGES),
            "--edges",
            str(edges),
            "--out",
            str(first_out),
            "--out",
            str(final_out),
        ],
        check=True,
    )
    assert not first_out.exists()
    assert list(json.loads(final_out.read_text())) == PREVIEW_ORDER
    assert list(json.loads(final_out.read_text())["totals"]) == TOTALS_ORDER
    assert_single_lf(final_out)


def test_middle_matrix_insert_is_verbatim_in_every_bundle_and_prunes_stale_tree(
    release_dist: Path,
) -> None:
    """Verify middle matrix insert is verbatim in every bundle and prunes stale tree."""
    stale_root = DIST / "releasekit-stale-root"
    stale_nested = DIST / "bundles" / "releasekit-stale-nested"
    stale_root.mkdir()
    stale_nested.mkdir()
    (stale_root / "old").write_text("old")
    (stale_nested / "old").write_text("old")
    source_lines = MATRIX.read_text().splitlines(keepends=True)
    inserted = "olivine-middle,qa,linux-x86_64,core,100,true,NOPE\n"
    matrix = "".join(source_lines[:2] + [inserted] + source_lines[2:])
    components = COMPONENTS.read_text() + "oli,1,MIT,runtime,no,1,linux-x86_64,t\n"
    locks = LOCKS.read_text() + "olivine-middle,oli,1,middle,cache/olivine.pkg\n"
    smoke_path = SMOKE / "olivine-middle.csv"
    with patched_app_files(
        {
            MATRIX: matrix,
            COMPONENTS: components,
            LOCKS: locks,
            smoke_path: "profile,expected\nolivine-middle,ok\n",
        }
    ):
        expected_profiles = [row["profile"] for row in read_csv(MATRIX)]
        assert [row["profile"] for row in manifest()["bundles"]] == expected_profiles
        assert {path.name for path in (DIST / "bundles").iterdir()} == {
            f"releasekit-{profile}" for profile in expected_profiles
        }
        live_matrix = MATRIX.read_bytes()
        assert live_matrix == matrix.encode()
        for profile in expected_profiles:
            assert (
                bundle_dir(profile) / "share" / "release_matrix.csv"
            ).read_bytes() == live_matrix
        assert not stale_root.exists() and not stale_nested.exists()
        assert_checksum_index()


def test_archive_reproducibility_ascii_modes_and_payload_equivalence(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify archive reproducibility ascii modes and payload equivalence."""
    before = {
        row["archive"]: sha256(release_dist / row["archive"])
        for row in manifest(release_dist)["bundles"]
    }
    run_release()
    after = {
        row["archive"]: sha256(DIST / row["archive"]) for row in manifest()["bundles"]
    }
    assert after == before
    for row in manifest()["bundles"]:
        profile = row["profile"]
        root_name = f"releasekit-{profile}"
        with tarfile.open(DIST / row["archive"], "r:gz") as archive:
            members = archive.getmembers()
            assert members and members[0].isdir()
            assert members[0].name == root_name
            assert [member.name for member in members] == sorted(
                member.name for member in members
            )
            for member in members:
                assert (member.uid, member.gid, member.mtime) == (
                    0,
                    0,
                    NORMALIZED_MTIME,
                )
                relative = member.name[len(root_name) :].lstrip("/")
                if member.isdir():
                    assert member.mode & 0o777 == 0o755
                elif relative in {"bin/releasekit", "share/run-smoke.sh"}:
                    assert member.mode & 0o777 == 0o755
                else:
                    assert member.mode & 0o777 == 0o644
            target = tmp_path / profile
            archive.extractall(target)
        extracted = target / root_name
        for source in bundle_dir(profile).rglob("*"):
            if source.is_file():
                assert (
                    extracted / source.relative_to(bundle_dir(profile))
                ).read_bytes() == source.read_bytes()


def test_smoke_relocation_with_spaces_uses_bundle_root_from_unrelated_cwd(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify smoke relocation with spaces uses bundle root from unrelated cwd."""
    relocated = tmp_path / "relocated edge bundle"
    shutil.copytree(bundle_dir("edge", release_dist), relocated)
    target = APP / "target"
    hidden_target = APP / "target.hidden-quartz"
    hidden_dist = APP / "dist.hidden-quartz"
    hidden_configs = [
        (path, path.with_name(f"{path.name}.hidden-quartz"))
        for path in (MATRIX, COMPONENTS, LOCKS, EDGES)
    ]
    unrelated_cwd = tmp_path / "unrelated working directory"
    unrelated_cwd.mkdir()
    target.rename(hidden_target)
    DIST.rename(hidden_dist)
    for source, hidden in hidden_configs:
        source.rename(hidden)
    try:
        script = relocated / "share" / "run-smoke.sh"
        subprocess.run(["sh", str(script)], cwd=unrelated_cwd, check=True)
        default_output = relocated / "audit-edge.json"
        expected = json.loads((relocated / "share" / "audit-preview.json").read_text())
        assert json.loads(default_output.read_text()) == expected
        assert_single_lf(default_output)

        explicit_output = (
            tmp_path / "outputs with spaces" / "deep" / "audit explicit.json"
        )
        subprocess.run(
            ["sh", str(script), str(explicit_output)], cwd=unrelated_cwd, check=True
        )
        assert json.loads(explicit_output.read_text()) == expected
        assert_single_lf(explicit_output)
    finally:
        for source, hidden in hidden_configs:
            hidden.rename(source)
        hidden_dist.rename(DIST)
        hidden_target.rename(target)


def test_checksum_index_tracks_deep_dynamic_payloads(
    release_dist: Path,
) -> None:
    """Verify checksum index tracks deep dynamic payloads."""
    matrix = MATRIX.read_text() + "rhodonite,qa,linux-x86_64,core,100,true,NOPE\n"
    components = COMPONENTS.read_text() + "rho,1,MIT,runtime,no,1,linux-x86_64,t\n"
    locks = LOCKS.read_text() + "rhodonite,rho,1,rho,cache/rho.blob\n"
    smoke = 'profile,expected,note\nrhodonite,ok,"payload, with quote ""and"" comma"\n'
    with patched_app_files(
        {
            MATRIX: matrix,
            COMPONENTS: components,
            LOCKS: locks,
            SMOKE / "rhodonite.csv": smoke,
        }
    ):
        assert_checksum_index()
        paths = [
            row.split(maxsplit=1)[1]
            for row in (DIST / "checksums.sha256").read_text().splitlines()
        ]
        assert paths == sorted(paths)
        assert "bundles/releasekit-rhodonite/share/smoke_specs/rhodonite.csv" in paths
        assert (
            bundle_dir("rhodonite") / "share" / "smoke_specs" / "rhodonite.csv"
        ).read_text() == smoke


def test_missing_only_profile_has_zero_license_and_exact_totals(
    release_dist: Path,
) -> None:
    """Verify missing only profile has zero license and exact totals."""
    matrix = MATRIX.read_text() + "serendibite,qa,linux-x86_64,core,100,true,NOPE\n"
    locks = LOCKS.read_text() + "serendibite,ghost-only,1,g,cache/g.blob\n"
    with patched_app_files(
        {
            MATRIX: matrix,
            LOCKS: locks,
            SMOKE / "serendibite.csv": "profile,expected\nserendibite,ok\n",
        }
    ):
        root = bundle_dir("serendibite")
        audit = preview("serendibite")
        assert audit["components"] == []
        assert audit["license_summary"] == [] and audit["owners"] == []
        assert audit["warnings"] == ["missing_component:ghost-only"]
        assert audit["totals"] == {
            "component_count": 0,
            "direct_lock_count": 0,
            "runtime_kb": 0,
            "critical_count": 0,
            "license_count": 0,
            "dev_component_count": 0,
            "edge_count": 0,
            "policy_pass": False,
            "risk_score": 31,
        }
        assert (root / "LICENSES.txt").read_bytes() == b""
        assert (root / "VERSION").read_bytes() == b"0.7.0\n"


def test_workspace_version_mutation_propagates_consistently(
    release_dist: Path,
) -> None:
    """Verify workspace version mutation propagates consistently."""
    cargo_toml = APP / "Cargo.toml"
    cargo_lock = APP / "Cargo.lock"
    with patched_app_files(
        {
            cargo_toml: cargo_toml.read_text().replace(
                'version = "0.7.0"', 'version = "0.7.9"'
            ),
            cargo_lock: cargo_lock.read_text().replace(
                'version = "0.7.0"', 'version = "0.7.9"'
            ),
        }
    ):
        data = manifest()
        assert data["package"]["version"] == "0.7.9"
        assert [row["version"] for row in data["workspace"]] == ["0.7.9"] * 3
        for row in data["bundles"]:
            root = bundle_dir(row["profile"])
            assert (root / "VERSION").read_bytes() == b"0.7.9\n"
            result = subprocess.run(
                [str(root / "bin" / "releasekit"), "--version"],
                text=True,
                capture_output=True,
                check=True,
            )
            assert result.stdout == "releasekit 0.7.9\n"
            assert row["binary_sha256"] == sha256(root / "bin" / "releasekit")
        assert_checksum_index()


def test_back_to_back_mutations_restore_base_hashes_and_state(
    release_dist: Path,
) -> None:
    """Verify back to back mutations restore base hashes and state."""
    base = dist_snapshot(release_dist)
    matrix = MATRIX.read_text() + "uvarovite,qa,linux-x86_64,core,100,true,NOPE\n"
    components = COMPONENTS.read_text() + "uva,1,MIT,runtime,no,1,linux-x86_64,t\n"
    locks = LOCKS.read_text() + "uvarovite,uva,1,u,u\n"
    with patched_app_files(
        {
            MATRIX: matrix,
            COMPONENTS: components,
            LOCKS: locks,
            SMOKE / "uvarovite.csv": "profile,expected\nuvarovite,ok\n",
        }
    ):
        assert bundle_dir("uvarovite").is_dir()
        assert any(row["profile"] == "uvarovite" for row in manifest()["bundles"])
        first_dynamic = dist_snapshot()
        run_release()
        assert dist_snapshot() == first_dynamic
    assert dist_snapshot() == base
    assert [row["profile"] for row in manifest()["bundles"]] == [
        "edge",
        "fleet",
        "audit",
        "sandbox",
    ]
    assert not bundle_dir("uvarovite").exists()
    assert_checksum_index()


def test_critical_aliases_doc_exclusion_and_runtime_equality(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify critical aliases doc exclusion and runtime equality."""
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "alabaster",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\nalabaster,qa,linux-x86_64,core,6,true,NOPE\n",
        "component,version,license,kind,critical,size_kb,platforms,owner\na-yes,1,MIT,runtime,YES,2,linux-x86_64,one\na-true,1,BSD-3-Clause,data,TrUe,3,linux-x86_64,two\na-one,1,Apache-2.0,doc,1,100,linux-x86_64,three\na-no,1,MPL-2.0,runtime,y,1,linux-x86_64,four\n",
        "profile,component,version,checksum,source\nalabaster,a-yes,1,y,y\nalabaster,a-true,1,t,t\nalabaster,a-one,1,o,o\nalabaster,a-no,1,n,n\n",
        "profile,parent,child,relation,scope,optional\n",
    )
    assert [row["critical"] for row in audit["components"]] == [False, True, True, True]
    assert audit["warnings"] == []
    assert audit["policy_checks"][-1] == "runtime_size:ok:6/6"
    assert audit["totals"] == {
        "component_count": 4,
        "direct_lock_count": 4,
        "runtime_kb": 6,
        "critical_count": 3,
        "license_count": 4,
        "dev_component_count": 0,
        "edge_count": 0,
        "policy_pass": True,
        "risk_score": 15,
    }


def test_simple_scope_truth_table_rejects_case_and_malformed_clauses(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify simple scope truth table rejects case and malformed clauses."""
    names = ["b-root", "b-a", "b-b", "b-c"]
    components = (
        "component,version,license,kind,critical,size_kb,platforms,owner\n"
        + "".join(f"{name},1,MIT,runtime,no,1,linux-arm64,t\n" for name in names)
    )
    locks = "profile,component,version,checksum,source\n" + "".join(
        f"brucite,{name},1,{name},{name}\n" for name in names
    )
    edges = (
        "profile,parent,child,relation,scope,optional\n"
        "brucite,b-root,b-a,alpha,feature:gpu&!channel:stable&target:linux-arm64,no\n"
        "brucite,b-root,b-b,beta,!feature:debug&channel:canary,no\n"
        "brucite,b-root,b-c,legacy,,no\n"
        "brucite,b-root,ghost-case,x,feature:GPU,no\n"
        "brucite,b-root,ghost-unknown,x,feature:gpu&bogus:value,no\n"
        "brucite,b-root,ghost-negated,x,!feature:gpu,no\n"
        "brucite,b-root,ghost-malformed,x,feature:gpu&&target:linux-arm64,no\n"
    )
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "brucite",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\nbrucite,canary,linux-arm64,core+gpu,10,true,NOPE\n",
        components,
        locks,
        edges,
    )
    assert [row["name"] for row in audit["components"]] == names
    assert audit["dependency_edges"] == [
        "b-root->b-a:alpha",
        "b-root->b-b:beta",
        "b-root->b-c:legacy",
    ]
    assert audit["warnings"] == []
    assert audit["totals"]["risk_score"] == 6


def test_deep_cfg_shortcuts_malformed_branches_and_required_warning(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify deep cfg shortcuts malformed branches and required warning."""
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "corundum",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\ncorundum,canary,linux-arm64,core+signed+fips,10,true,NOPE\n",
        "component,version,license,kind,critical,size_kb,platforms,owner\nc-root,1,MIT,runtime,no,1,linux-arm64,t\nc-a,1,MIT,runtime,no,1,linux-arm64,t\nc-b,1,MIT,runtime,no,1,linux-arm64,t\n",
        "profile,component,version,checksum,source\ncorundum,c-root,1,r,r\ncorundum,c-a,1,a,a\ncorundum,c-b,1,b,b\n",
        'profile,parent,child,relation,scope,optional\ncorundum,c-root,c-a,alpha,"cfg:all(feature:signed,not(any(channel:stable,feature:debug)),any(target:linux-x86_64,target:linux-arm64))",no\ncorundum,c-a,c-b,beta,"cfg:not(all(feature:debug,channel:stable))",no\ncorundum,c-root,ghost-active,x,"cfg:any(all(feature:fips,target:linux-arm64),channel:stable)",no\ncorundum,c-root,ghost-target,x,"cfg:all(feature:fips,target:linux-x86_64)",no\ncorundum,c-root,ghost-any,x,"cfg:any(feature:missing,channel:stable)",no\ncorundum,c-root,ghost-malformed,x,"cfg:all(feature:fips,)",no\n',
    )
    assert [row["name"] for row in audit["components"]] == ["c-root", "c-a", "c-b"]
    assert audit["dependency_edges"] == ["c-a->c-b:beta", "c-root->c-a:alpha"]
    assert audit["warnings"] == ["missing_required_edge:c-root->ghost-active"]
    assert audit["policy_checks"][2] == "locked_versions:fail"
    assert audit["totals"]["risk_score"] == 35


def test_condensation_diamond_cycles_self_loop_and_ready_ties(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify condensation diamond cycles self loop and ready ties."""
    names = ["d-r0", "d-r1", "d-a", "d-b", "d-c", "d-d", "d-e", "d-f", "d-g"]
    components = (
        "component,version,license,kind,critical,size_kb,platforms,owner\n"
        + "".join(f"{name},1,MIT,runtime,no,1,linux-x86_64,t\n" for name in names)
    )
    locks = "profile,component,version,checksum,source\n" + "".join(
        f"danburite,{name},1,{name},{name}\n" for name in names
    )
    pairs = [
        ("d-r0", "d-a"),
        ("d-r1", "d-c"),
        ("d-a", "d-b"),
        ("d-b", "d-a"),
        ("d-b", "d-c"),
        ("d-c", "d-d"),
        ("d-d", "d-e"),
        ("d-e", "d-d"),
        ("d-e", "d-g"),
        ("d-r0", "d-f"),
        ("d-f", "d-f"),
    ]
    edges = "profile,parent,child,relation,scope,optional\n" + "".join(
        f"danburite,{parent},{child},r,runtime,no\n" for parent, child in pairs
    )
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "danburite",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\ndanburite,qa,linux-x86_64,core,100,true,NOPE\n",
        components,
        locks,
        edges,
    )
    assert [row["name"] for row in audit["components"]] == [
        "d-r0",
        "d-a",
        "d-b",
        "d-f",
        "d-r1",
        "d-c",
        "d-d",
        "d-e",
        "d-g",
    ]
    assert audit["warnings"] == [
        "dependency_cycle:d-a|d-b",
        "dependency_cycle:d-d|d-e",
        "dependency_cycle:d-f",
    ]
    assert audit["totals"]["edge_count"] == 11
    assert audit["totals"]["risk_score"] == 115


def test_source_row_multiplicity_never_multiplies_topology_indegree(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify source row multiplicity never multiplies topology indegree."""
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "enstatite",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\nenstatite,qa,linux-x86_64,core,10,true,NOPE\n",
        "component,version,license,kind,critical,size_kb,platforms,owner\ne-p,1,MIT,runtime,no,1,linux-x86_64,t\ne-c,1,MIT,runtime,no,1,linux-x86_64,t\ne-t,1,MIT,runtime,no,1,linux-x86_64,t\n",
        "profile,component,version,checksum,source\nenstatite,e-p,1,p,p\nenstatite,e-c,1,c,c\nenstatite,e-t,1,t,t\n",
        "profile,parent,child,relation,scope,optional\n*,e-p,e-c,z,runtime,no\n*,e-p,e-c,z,runtime,no\nenstatite,e-p,e-c,z,runtime,no\nenstatite,e-p,e-c,a,runtime,no\nenstatite,e-p,e-c,a,feature:core,no\nenstatite,e-c,e-t,tail,runtime,no\nenstatite,e-t,e-p,inactive,feature:missing,no\n",
    )
    assert [row["name"] for row in audit["components"]] == ["e-p", "e-c", "e-t"]
    assert audit["dependency_edges"] == [
        "e-c->e-t:tail",
        "e-p->e-c:a",
        "e-p->e-c:a",
        "e-p->e-c:z",
        "e-p->e-c:z",
        "e-p->e-c:z",
    ]
    assert audit["warnings"] == []
    assert audit["totals"]["edge_count"] == 6
    assert audit["totals"]["risk_score"] == 12


def test_opal_duplicate_ghost_and_required_rows_dedupe_without_count_leak(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify opal duplicate ghost and required rows dedupe without count leak."""
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "fire-opal",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\nfire-opal,qa,linux-x86_64,core,10,true,NOPE\n",
        "component,version,license,kind,critical,size_kb,platforms,owner\nf-real,1,MIT,runtime,no,1,linux-x86_64,t\n",
        "profile,component,version,checksum,source\nfire-opal,f-ghost,1,g1,g1\nfire-opal,f-real,1,old,old\nfire-opal,f-ghost,2,g2,g2\nfire-opal,f-real,2,final,final\n",
        "profile,parent,child,relation,scope,optional\nfire-opal,f-real,f-ghost,requires,runtime,no\nfire-opal,f-real,f-ghost,requires,runtime,no\n",
    )
    assert audit["components"][0]["checksum"] == "final"
    assert audit["warnings"] == [
        "missing_component:f-ghost",
        "missing_required_edge:f-real->f-ghost",
        "version_mismatch:f-real:2:1",
    ]
    assert audit["totals"]["direct_lock_count"] == 1
    assert audit["totals"]["risk_score"] == 93


def test_csv_and_json_escaping_survive_quotes_tabs_and_backslashes(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify csv and json escaping survive quotes tabs and backslashes."""
    owner = 'Ops\\Blue "Night"\tUnit'
    source = 'cache\\a,"signed"\t.blob'
    relation = 'exports\\"quoted",tab\tvalue'
    channel = 'qa\\"night'
    audit, raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "greenockite",
        csv_bytes(
            [
                "profile",
                "channel",
                "target",
                "feature_set",
                "max_runtime_kb",
                "allow_dev",
                "blocked_license",
            ],
            [["greenockite", channel, "linux-x86_64", "core", 10, "true", "NOPE"]],
        ).decode(),
        csv_bytes(
            [
                "component",
                "version",
                "license",
                "kind",
                "critical",
                "size_kb",
                "platforms",
                "owner",
            ],
            [
                ["g-a", "1", "MIT", "runtime", "no", 1, "linux-x86_64", owner],
                ["g-b", "1", "MIT", "runtime", "no", 1, "linux-x86_64", "Plain"],
            ],
        ).decode(),
        csv_bytes(
            ["profile", "component", "version", "checksum", "source"],
            [
                ["greenockite", "g-a", "1", 'sum\\"a', source],
                ["greenockite", "g-b", "1", "b", "b"],
            ],
        ).decode(),
        csv_bytes(
            ["profile", "parent", "child", "relation", "scope", "optional"],
            [["greenockite", "g-a", "g-b", relation, "runtime", "no"]],
        ).decode(),
    )
    assert audit["channel"] == channel
    assert audit["components"][0]["source"] == source
    assert audit["owners"] == sorted([owner, "Plain"])
    assert audit["dependency_edges"] == [f"g-a->g-b:{relation}"]
    assert b"\\t" in raw and b"\\\\" in raw and b'\\"' in raw


def test_full_crlf_release_ignores_empty_records_and_preserves_survivors(
    release_dist: Path,
) -> None:
    """Verify full crlf release ignores empty records and preserves survivors."""
    matrix = b"profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\r\n\r\nhauyne,qa,linux-x86_64,core,10,true,NOPE\r\n"
    components = b"component,version,license,kind,critical,size_kb,platforms,owner\r\n\r\nh-root,1,MIT,runtime,no,1,linux-x86_64,t\r\nh-child,1,BSD-3-Clause,runtime,no,1,linux-x86_64,t\r\n"
    locks = b"profile,component,version,checksum,source\r\n\r\nhauyne,h-root,1,r,r\r\nhauyne,h-child,1,c,c\r\n"
    edges = b"profile,parent,child,relation,scope,optional\r\n\r\nhauyne,h-root,h-child,requires,runtime,no\r\n"
    with patched_app_files(
        {
            MATRIX: matrix,
            COMPONENTS: components,
            LOCKS: locks,
            EDGES: edges,
            SMOKE / "hauyne.csv": b"profile,expected\r\nhauyne,ok\r\n",
        }
    ):
        root = bundle_dir("hauyne")
        assert (root / "share" / "release_matrix.csv").read_bytes() == matrix
        assert b"\r\n" in (root / "share" / "components.csv").read_bytes()
        assert b"\r\n\r\n" not in (root / "share" / "components.csv").read_bytes()
        assert preview("hauyne")["dependency_edges"] == ["h-root->h-child:requires"]


def test_smoke_delta_changes_only_its_bundle_archive_and_indexes(
    release_dist: Path,
) -> None:
    """Verify smoke delta changes only its bundle archive and indexes."""
    before = dist_snapshot(release_dist)
    before_manifest = {row["profile"]: row for row in manifest(release_dist)["bundles"]}
    changed_smoke = (
        SMOKE / "edge.csv"
    ).read_bytes() + b"3,releasekit audit edge --deep,0\n"
    with patched_app_files({SMOKE / "edge.csv": changed_smoke}):
        after = dist_snapshot()
        changed = {path for path in before if before[path] != after[path]}
        assert changed == {
            "bundles/releasekit-edge/share/smoke_specs/edge.csv",
            "releasekit-edge-linux-x86_64.tar.gz",
            "release-manifest.json",
            "checksums.sha256",
        }
        current = {row["profile"]: row for row in manifest()["bundles"]}
        assert current["edge"] != before_manifest["edge"]
        for profile in ["fleet", "audit", "sandbox"]:
            assert current[profile] == before_manifest[profile]


def test_global_reverse_edge_rehashes_graph_layers_not_opaque_payloads(
    release_dist: Path,
) -> None:
    """Verify global reverse edge rehashes graph layers not opaque payloads."""
    before = dist_snapshot(release_dist)
    changed_edges = (
        EDGES.read_text() + "*,manifest-portfile,triplet-core,reverse,runtime,no\n"
    )
    with patched_app_files({EDGES: changed_edges}):
        after = dist_snapshot()
        changed = {path for path in before if before[path] != after[path]}
        expected = {"release-manifest.json", "checksums.sha256"}
        for profile in ["edge", "fleet", "audit", "sandbox"]:
            expected.update(
                {
                    f"bundles/releasekit-{profile}/share/dependencies.csv",
                    f"bundles/releasekit-{profile}/share/audit-preview.json",
                    f"releasekit-{profile}-linux-x86_64.tar.gz",
                }
            )
            assert (
                "dependency_cycle:manifest-portfile|triplet-core"
                in preview(profile)["warnings"]
            )
        assert changed == expected


def test_explicit_member_version_changes_workspace_not_package_version(
    release_dist: Path,
) -> None:
    """Verify explicit member version changes workspace not package version."""
    table_toml = APP / "crates" / "releasekit-table" / "Cargo.toml"
    cargo_lock = APP / "Cargo.lock"
    new_table = table_toml.read_text().replace(
        "version.workspace = true", 'version = "0.7.8"'
    )
    old_lock = 'name = "releasekit-table"\nversion = "0.7.0"'
    assert old_lock in cargo_lock.read_text()
    new_lock = cargo_lock.read_text().replace(
        old_lock, 'name = "releasekit-table"\nversion = "0.7.8"'
    )
    with patched_app_files({table_toml: new_table, cargo_lock: new_lock}):
        data = manifest()
        assert data["package"]["version"] == "0.7.0"
        assert [row["version"] for row in data["workspace"]] == [
            "0.7.0",
            "0.7.0",
            "0.7.8",
        ]
        for row in data["bundles"]:
            root = bundle_dir(row["profile"])
            assert (root / "VERSION").read_bytes() == b"0.7.0\n"
            result = subprocess.run(
                [str(root / "bin" / "releasekit"), "--version"],
                text=True,
                capture_output=True,
                check=True,
            )
            assert result.stdout == "releasekit 0.7.0\n"


def test_punctuated_profile_archive_relocates_and_defaults_from_foreign_cwd(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify punctuated profile archive relocates and defaults from foreign cwd."""
    profile = "moonstone.v2-beta"
    with patched_app_files(
        {
            MATRIX: MATRIX.read_text()
            + f"{profile},qa,linux-x86_64,core,10,true,NOPE\n",
            COMPONENTS: COMPONENTS.read_text()
            + "moonstone-core,1,MIT,runtime,no,1,linux-x86_64,t\n",
            LOCKS: LOCKS.read_text() + f"{profile},moonstone-core,1,m,m\n",
            SMOKE / f"{profile}.csv": f"profile,expected\n{profile},ok\n",
        }
    ):
        entry = next(row for row in manifest()["bundles"] if row["profile"] == profile)
        assert entry["archive"] == f"releasekit-{profile}-linux-x86_64.tar.gz"
        relocated = tmp_path / "foreign path" / f"releasekit-{profile}"
        shutil.copytree(bundle_dir(profile), relocated)
        with hidden_build_sources("moonstone"):
            subprocess.run(
                ["sh", str(relocated / "share" / "run-smoke.sh")],
                cwd=tmp_path,
                check=True,
            )
            output = relocated / f"audit-{profile}.json"
            assert json.loads(output.read_text()) == json.loads(
                (relocated / "share" / "audit-preview.json").read_text()
            )
            assert_single_lf(output)


def test_reordered_subset_prunes_outputs_then_restores_every_hash(
    release_dist: Path,
) -> None:
    """Verify reordered subset prunes outputs then restores every hash."""
    base = dist_snapshot(release_dist)
    rows = read_csv(MATRIX)
    by_profile = {row["profile"]: row for row in rows}
    header = list(rows[0])
    subset = csv_bytes(
        header,
        [[by_profile[name][key] for key in header] for name in ["sandbox", "edge"]],
    )
    with patched_app_files({MATRIX: subset}):
        assert [row["profile"] for row in manifest()["bundles"]] == ["sandbox", "edge"]
        assert {path.name for path in (DIST / "bundles").iterdir()} == {
            "releasekit-sandbox",
            "releasekit-edge",
        }
        assert not (DIST / "releasekit-fleet-linux-x86_64.tar.gz").exists()
        assert not (DIST / "releasekit-audit-linux-x86_64.tar.gz").exists()
    assert dist_snapshot() == base


def test_optional_alias_rows_count_only_with_both_selected_endpoints(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify optional alias rows count only with both selected endpoints."""
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "oligoclase",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\noligoclase,qa,linux-x86_64,core,10,true,NOPE\n",
        "component,version,license,kind,critical,size_kb,platforms,owner\no-p,1,MIT,runtime,no,1,linux-x86_64,t\no-c,1,MIT,runtime,no,1,linux-x86_64,t\n",
        "profile,component,version,checksum,source\noligoclase,o-p,1,p,p\noligoclase,o-c,1,c,c\n",
        "profile,parent,child,relation,scope,optional\noligoclase,o-p,o-c,yes,runtime,yes\noligoclase,o-p,o-c,true,runtime,true\noligoclase,o-p,o-c,one,runtime,1\noligoclase,o-p,ghost,yes,runtime,yes\noligoclase,o-p,ghost,true,runtime,true\noligoclase,o-p,ghost,one,runtime,1\n",
    )
    assert audit["dependency_edges"] == [
        "o-p->o-c:one",
        "o-p->o-c:true",
        "o-p->o-c:yes",
    ]
    assert audit["warnings"] == []
    assert audit["totals"]["edge_count"] == 3
    assert audit["totals"]["risk_score"] == 6


def test_all_warning_families_dedupe_while_multiplicity_drives_risk(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify all warning families dedupe while multiplicity drives risk."""
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "prehnite",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\nprehnite,qa,linux-x86_64,core,10,false,GPL-3.0\n",
        "component,version,license,kind,critical,size_kb,platforms,owner\np-tool,2,GPL-3.0,dev,yes,20,linux-arm64,t\n",
        "profile,component,version,checksum,source\nprehnite,p-ghost,1,g1,g1\nprehnite,p-tool,1,t1,t1\nprehnite,p-ghost,2,g2,g2\n",
        "profile,parent,child,relation,scope,optional\nprehnite,p-tool,p-tool,self,runtime,no\nprehnite,p-tool,p-tool,self,runtime,no\nprehnite,p-tool,p-absent,requires,runtime,no\nprehnite,p-tool,p-absent,requires,runtime,no\n",
    )
    assert audit["warnings"] == [
        "blocked_license:p-tool:GPL-3.0",
        "dependency_cycle:p-tool",
        "dev_dependency:p-tool",
        "missing_component:p-ghost",
        "missing_required_edge:p-tool->p-absent",
        "platform:p-tool:linux-x86_64",
        "runtime_size:20:10",
        "version_mismatch:p-tool:1:2",
    ]
    assert audit["policy_checks"] == [
        "blocked_license:fail",
        "dev_policy:fail",
        "locked_versions:fail",
        "platforms:fail",
        "runtime_size:fail:20/10",
    ]
    assert audit["totals"]["edge_count"] == 2
    assert audit["totals"]["risk_score"] == 273


def test_platform_failures_never_suppress_runtime_accounting_or_warning(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify platform failures never suppress runtime accounting or warning."""
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "quartzite",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\nquartzite,qa,linux-x86_64,core,10,true,NOPE\n",
        "component,version,license,kind,critical,size_kb,platforms,owner\nq-runtime,1,MIT,runtime,no,20,linux-arm64,t\nq-doc,1,MIT,doc,no,999,linux-arm64,t\n",
        "profile,component,version,checksum,source\nquartzite,q-runtime,1,r,r\nquartzite,q-doc,1,d,d\n",
        "profile,parent,child,relation,scope,optional\n",
    )
    assert audit["warnings"] == [
        "platform:q-doc:linux-x86_64",
        "platform:q-runtime:linux-x86_64",
        "runtime_size:20:10",
    ]
    assert audit["totals"]["runtime_kb"] == 20
    assert audit["policy_checks"][-2:] == ["platforms:fail", "runtime_size:fail:20/10"]
    assert audit["totals"]["risk_score"] == 106


def test_every_relocated_smoke_defaults_to_own_bundle_from_unrelated_cwd(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify every relocated smoke defaults to own bundle from unrelated cwd."""
    expected = {
        profile: preview(profile, release_dist)
        for profile in ["edge", "fleet", "audit", "sandbox"]
    }
    copies = {}
    for profile in expected:
        target = tmp_path / "relocated bundles" / f"releasekit-{profile}"
        shutil.copytree(bundle_dir(profile, release_dist), target)
        copies[profile] = target
    with hidden_build_sources("realgar"):
        for profile, root in copies.items():
            subprocess.run(
                ["sh", str(root / "share" / "run-smoke.sh")], cwd=tmp_path, check=True
            )
            output = root / f"audit-{profile}.json"
            assert json.loads(output.read_text()) == expected[profile]
            assert_single_lf(output)


def test_quoted_matrix_fields_drive_policy_preview_manifest_and_verbatim_copy(
    release_dist: Path,
) -> None:
    """Verify quoted matrix fields drive policy preview manifest and verbatim copy."""
    header = [
        "profile",
        "channel",
        "target",
        "feature_set",
        "max_runtime_kb",
        "allow_dev",
        "blocked_license",
    ]
    channel = 'qa,blue "night"'
    encoded = csv_bytes(
        header, [["spinel", channel, "linux-x86_64", "core+signed", 10, "true", "NOPE"]]
    )
    row = encoded.splitlines(keepends=True)[1]
    matrix = MATRIX.read_bytes() + row
    with patched_app_files(
        {
            MATRIX: matrix,
            COMPONENTS: COMPONENTS.read_text()
            + "spinel-core,1,MIT,runtime,no,1,linux-x86_64,t\n",
            LOCKS: LOCKS.read_text() + "spinel,spinel-core,1,s,s\n",
            SMOKE / "spinel.csv": "profile,expected\nspinel,ok\n",
        }
    ):
        root = bundle_dir("spinel")
        assert (root / "share" / "release_matrix.csv").read_bytes() == matrix
        assert (
            json.loads((root / "share" / "policy.json").read_text())["channel"]
            == channel
        )
        assert preview("spinel")["channel"] == channel
        entry = next(
            item for item in manifest()["bundles"] if item["profile"] == "spinel"
        )
        assert entry["channel"] == channel


def test_allow_dev_aliases_normalize_policy_and_suppress_dev_warning(
    release_dist: Path,
) -> None:
    """Verify allow dev aliases normalize policy and suppress dev warning."""
    matrix = MATRIX.read_text() + (
        "topaz-yes,qa,linux-x86_64,core,10,yes,NOPE\n"
        "topaz-one,qa,linux-x86_64,core,10,1,NOPE\n"
    )
    components = COMPONENTS.read_text() + "topaz-tool,1,MIT,dev,no,1,linux-x86_64,t\n"
    locks = LOCKS.read_text() + (
        "topaz-yes,topaz-tool,1,y,y\ntopaz-one,topaz-tool,1,o,o\n"
    )
    with patched_app_files(
        {
            MATRIX: matrix,
            COMPONENTS: components,
            LOCKS: locks,
            SMOKE / "topaz-yes.csv": "profile,expected\ntopaz-yes,ok\n",
            SMOKE / "topaz-one.csv": "profile,expected\ntopaz-one,ok\n",
        }
    ):
        for profile in ["topaz-yes", "topaz-one"]:
            policy = json.loads(
                (bundle_dir(profile) / "share" / "policy.json").read_text()
            )
            audit = preview(profile)
            assert policy["allow_dev"] is True
            assert audit["allow_dev"] is True
            assert audit["warnings"] == []
            assert audit["totals"]["dev_component_count"] == 1
            assert audit["totals"]["risk_score"] == 3


def test_wildcard_and_foreign_locks_never_select_components_for_profile(
    release_dist: Path, tmp_path: Path
) -> None:
    """Verify wildcard and foreign locks never select components for profile."""
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "willemite",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\nwillemite,qa,linux-x86_64,core,10,true,NOPE\n",
        "component,version,license,kind,critical,size_kb,platforms,owner\nw-exact,1,MIT,runtime,no,1,linux-x86_64,t\nw-star,1,MIT,runtime,no,1,linux-x86_64,t\nw-foreign,1,MIT,runtime,no,1,linux-x86_64,t\n",
        "profile,component,version,checksum,source\n*,w-star,1,s,s\nother,w-foreign,1,f,f\nwillemite,w-exact,1,e,e\n",
        "profile,parent,child,relation,scope,optional\nwillemite,w-exact,w-star,requires,runtime,no\n",
    )
    assert [row["name"] for row in audit["components"]] == ["w-exact"]
    assert audit["warnings"] == ["missing_required_edge:w-exact->w-star"]
    assert audit["totals"]["direct_lock_count"] == 1
    assert audit["policy_checks"][2] == "locked_versions:fail"


def test_deep_condensation_chain_is_stack_safe_and_keeps_only_the_terminal_scc_warning(
    release_dist: Path, tmp_path: Path
) -> None:
    """Process thousands of graph nodes without recursive traversal failure."""
    prefix = [f"deep-{index:04d}" for index in range(4096)]
    ring = [f"deep-ring-{index}" for index in range(3)]
    names = prefix + ring
    components = "component,version,license,kind,critical,size_kb,platforms,owner\n" + "".join(
        f"{name},1,MIT,runtime,no,0,linux-x86_64,graph\n" for name in names
    )
    locks = "profile,component,version,checksum,source\n" + "".join(
        f"deep-chain,{name},1,{index},{index}\n" for index, name in enumerate(reversed(names))
    )
    graph_rows = [
        f"deep-chain,{prefix[index]},{prefix[index + 1]},chain,runtime,no\n"
        for index in range(len(prefix) - 1)
    ]
    graph_rows.append(f"deep-chain,{prefix[-1]},{ring[0]},enter,runtime,no\n")
    graph_rows.extend(
        f"deep-chain,{ring[index]},{ring[(index + 1) % 3]},ring,runtime,no\n"
        for index in range(3)
    )
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "deep-chain",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\ndeep-chain,qa,linux-x86_64,core,100000,true,NOPE\n",
        components,
        locks,
        "profile,parent,child,relation,scope,optional\n" + "".join(graph_rows),
    )
    assert [row["name"] for row in audit["components"]] == prefix + sorted(ring)
    assert audit["warnings"] == [f"dependency_cycle:{'|'.join(sorted(ring))}"]
    assert audit["policy_checks"][2] == "locked_versions:ok"
    assert audit["totals"]["component_count"] == 4099
    assert audit["totals"]["edge_count"] == 4099
    assert audit["totals"]["risk_score"] == 8229


def test_twelve_cyclic_components_remain_separate_through_a_duplicate_condensation_chain(
    release_dist: Path, tmp_path: Path
) -> None:
    """Keep many SCC warnings separate while source rows retain multiplicity."""
    groups = [[f"scc-{group:02d}-{node}" for node in range(4)] for group in range(12)]
    names = [name for group in groups for name in group]
    components = "component,version,license,kind,critical,size_kb,platforms,owner\n" + "".join(
        f"{name},1,MIT,runtime,no,0,linux-x86_64,scc\n" for name in names
    )
    locks = "profile,component,version,checksum,source\n" + "".join(
        f"many-scc,{name},1,{index},{index}\n" for index, name in enumerate(reversed(names))
    )
    edges: list[tuple[str, str, str]] = []
    for group in groups:
        edges.extend((group[index], group[(index + 1) % 4], "ring") for index in range(4))
    for index in range(len(groups) - 1):
        row = (groups[index][-1], groups[index + 1][0], f"bridge-{index:02d}")
        edges.append(row)
        if index % 2 == 0:
            edges.append(row)
    edge_text = "profile,parent,child,relation,scope,optional\n" + "".join(
        f"many-scc,{parent},{child},{relation},runtime,no\n"
        for parent, child, relation in edges
    )
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "many-scc",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\nmany-scc,qa,linux-x86_64,core,1,true,NOPE\n",
        components,
        locks,
        edge_text,
    )
    assert [row["name"] for row in audit["components"]] == names
    assert audit["warnings"] == sorted(
        f"dependency_cycle:{'|'.join(group)}" for group in groups
    )
    assert audit["totals"]["edge_count"] == 65
    assert audit["totals"]["risk_score"] == 502


def test_sixty_four_level_cfg_scopes_activate_exact_branches_and_silence_malformed_tails(
    release_dist: Path, tmp_path: Path
) -> None:
    """Evaluate deeply nested scopes only when the complete expression is valid."""
    names = ["scope-root", *[f"scope-leaf-{index}" for index in range(8)]]
    components = "component,version,license,kind,critical,size_kb,platforms,owner\n" + "".join(
        f"{name},1,MIT,runtime,no,1,linux-x86_64,scope\n" for name in names
    )
    locks = "profile,component,version,checksum,source\n" + "".join(
        f"deep-scope,{name},1,{name},{name}\n" for name in reversed(names)
    )
    rows = []
    for index in range(8):
        depth = 8 * (index + 1)
        expression = "cfg:" + "not(" * depth + "feature:signed" + ")" * depth
        rows.append(["deep-scope", "scope-root", f"scope-leaf-{index}", f"depth-{depth}", expression, "no"])
    odd = "cfg:" + "not(" * 63 + "feature:signed" + ")" * 63
    rows.append(["deep-scope", "scope-root", "missing-odd", "inactive", odd, "no"])
    malformed = "cfg:" + "not(" * 64 + "feature:signed" + ")" * 64 + ")"
    rows.append(["deep-scope", "scope-root", "missing-malformed", "inactive", malformed, "no"])
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "deep-scope",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\ndeep-scope,qa,linux-x86_64,core+signed,20,true,NOPE\n",
        components,
        locks,
        csv_bytes(["profile", "parent", "child", "relation", "scope", "optional"], rows).decode(),
    )
    assert [row["name"] for row in audit["components"]] == names
    assert audit["warnings"] == []
    assert audit["totals"]["edge_count"] == 8
    assert audit["totals"]["risk_score"] == 16


def test_three_explicit_member_versions_resolve_independently_and_cli_owns_bundle_version(
    release_dist: Path,
) -> None:
    """Resolve explicit versions per crate instead of copying one workspace value."""
    versions = {
        "releasekit-cli": "0.8.0",
        "releasekit-core": "0.8.1",
        "releasekit-table": "0.8.2",
    }
    updates: dict[Path, str] = {}
    lock_text = (APP / "Cargo.lock").read_text()
    for crate, version in versions.items():
        manifest_path = APP / "crates" / crate / "Cargo.toml"
        updates[manifest_path] = manifest_path.read_text().replace(
            "version.workspace = true", f'version = "{version}"'
        )
        lock_text = lock_text.replace(
            f'name = "{crate}"\nversion = "0.7.0"',
            f'name = "{crate}"\nversion = "{version}"',
        )
    updates[APP / "Cargo.lock"] = lock_text
    with patched_app_files(updates):
        data = manifest()
        assert data["package"]["version"] == "0.8.0"
        assert [row["version"] for row in data["workspace"]] == [
            "0.8.0",
            "0.8.1",
            "0.8.2",
        ]
        for entry in data["bundles"]:
            root = bundle_dir(entry["profile"])
            assert (root / "VERSION").read_bytes() == b"0.8.0\n"
            result = subprocess.run(
                [str(root / "bin" / "releasekit"), "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            assert result.stdout == "releasekit 0.8.0\n"


def test_workspace_inheritance_and_explicit_table_override_coexist_after_root_version_change(
    release_dist: Path,
) -> None:
    """Apply workspace inheritance and a member override in the same locked build."""
    root_manifest = APP / "Cargo.toml"
    table_manifest = APP / "crates" / "releasekit-table" / "Cargo.toml"
    cargo_lock = APP / "Cargo.lock"
    new_root = root_manifest.read_text().replace('version = "0.7.0"', 'version = "1.1.0"', 1)
    new_table = table_manifest.read_text().replace(
        "version.workspace = true", 'version = "0.9.9"'
    )
    new_lock = cargo_lock.read_text()
    for crate in ["releasekit-cli", "releasekit-core"]:
        new_lock = new_lock.replace(
            f'name = "{crate}"\nversion = "0.7.0"',
            f'name = "{crate}"\nversion = "1.1.0"',
        )
    new_lock = new_lock.replace(
        'name = "releasekit-table"\nversion = "0.7.0"',
        'name = "releasekit-table"\nversion = "0.9.9"',
    )
    with patched_app_files(
        {root_manifest: new_root, table_manifest: new_table, cargo_lock: new_lock}
    ):
        data = manifest()
        assert data["package"]["version"] == "1.1.0"
        assert [row["version"] for row in data["workspace"]] == [
            "1.1.0",
            "1.1.0",
            "0.9.9",
        ]
        assert all(
            (bundle_dir(row["profile"]) / "VERSION").read_bytes() == b"1.1.0\n"
            for row in data["bundles"]
        )


def test_quoted_crlf_release_combines_duplicate_replay_cycle_and_every_policy_failure(
    release_dist: Path,
) -> None:
    """Stack RFC CSV, final-row replay, SCCs, and all policy axes in one release."""
    matrix = csv_bytes(
        ["profile", "channel", "target", "feature_set", "max_runtime_kb", "allow_dev", "blocked_license"],
        [["quoted-stack", 'qa, "signed"', "linux-x86_64", "core+signed", 10, "false", "GPL-3.0"]],
        "\r\n",
    )
    components = csv_bytes(
        ["component", "version", "license", "kind", "critical", "size_kb", "platforms", "owner"],
        [
            ["stack-a", "1", "MIT", "runtime", "no", 1, "linux-x86_64", "old"],
            ["stack-a", "2", "GPL-3.0", "dev", "TRUE", 11, "linux-arm64", 'Final, "Ops"'],
            ["stack-b", "1", "MIT", "doc", "no", 999, "linux-x86_64", "docs"],
        ],
        "\r\n",
    ).replace(b"\r\n", b"\r\n\r\n", 1)
    locks = csv_bytes(
        ["profile", "component", "version", "checksum", "source"],
        [
            ["quoted-stack", "stack-a", "2", "old", "old"],
            ["quoted-stack", "stack-a", "9", "final", 'cache, "signed"'],
            ["quoted-stack", "stack-b", "1", "b", "b"],
        ],
        "\r\n",
    )
    scope = "cfg:all(feature:signed,not(channel:stable))"
    edges = csv_bytes(
        ["profile", "parent", "child", "relation", "scope", "optional"],
        [
            ["quoted-stack", "stack-a", "stack-b", "forward", scope, "no"],
            ["quoted-stack", "stack-b", "stack-a", "reverse", scope, "no"],
            ["quoted-stack", "stack-a", "missing", "required", scope, "no"],
        ],
        "\r\n",
    )
    with patched_app_files(
        {
            MATRIX: matrix,
            COMPONENTS: components,
            LOCKS: locks,
            EDGES: edges,
            SMOKE / "quoted-stack.csv": b"profile,expected\r\nquoted-stack,ok\r\n",
        }
    ):
        audit = preview("quoted-stack")
        assert audit["channel"] == 'qa, "signed"'
        assert audit["components"][0]["checksum"] == "final"
        assert audit["warnings"] == [
            "blocked_license:stack-a:GPL-3.0",
            "dependency_cycle:stack-a|stack-b",
            "dev_dependency:stack-a",
            "missing_required_edge:stack-a->missing",
            "platform:stack-a:linux-x86_64",
            "runtime_size:11:10",
            "version_mismatch:stack-a:9:2",
        ]
        assert audit["policy_checks"] == [
            "blocked_license:fail",
            "dev_policy:fail",
            "locked_versions:fail",
            "platforms:fail",
            "runtime_size:fail:11/10",
        ]
        assert audit["totals"]["risk_score"] == 242


def test_global_edges_project_differently_for_two_profiles_without_cross_profile_leakage(
    release_dist: Path,
) -> None:
    """Project one global graph over two exact-profile selected node sets."""
    matrix = csv_bytes(
        ["profile", "channel", "target", "feature_set", "max_runtime_kb", "allow_dev", "blocked_license"],
        [
            ["projection-a", "qa", "linux-x86_64", "core", 10, "true", "NOPE"],
            ["projection-b", "qa", "linux-x86_64", "core", 10, "true", "NOPE"],
        ],
    )
    components = csv_bytes(
        ["component", "version", "license", "kind", "critical", "size_kb", "platforms", "owner"],
        [[name, "1", "MIT", "runtime", "no", 1, "linux-x86_64", "projection"] for name in ["proj-a", "proj-b", "proj-c"]],
    )
    locks = csv_bytes(
        ["profile", "component", "version", "checksum", "source"],
        [
            ["projection-a", "proj-a", "1", "a", "a"],
            ["projection-a", "proj-b", "1", "b", "b"],
            ["projection-b", "proj-b", "1", "b", "b"],
            ["projection-b", "proj-c", "1", "c", "c"],
            ["*", "proj-a", "1", "star", "star"],
        ],
    )
    edges = csv_bytes(
        ["profile", "parent", "child", "relation", "scope", "optional"],
        [
            ["*", "proj-a", "proj-b", "global-ab", "runtime", "no"],
            ["*", "proj-b", "proj-c", "global-bc", "runtime", "no"],
            ["projection-b", "proj-c", "proj-b", "local-cb", "runtime", "no"],
        ],
    )
    with patched_app_files(
        {
            MATRIX: matrix,
            COMPONENTS: components,
            LOCKS: locks,
            EDGES: edges,
            SMOKE / "projection-a.csv": "profile,expected\nprojection-a,ok\n",
            SMOKE / "projection-b.csv": "profile,expected\nprojection-b,ok\n",
        }
    ):
        first = preview("projection-a")
        second = preview("projection-b")
        assert first["dependency_edges"] == ["proj-a->proj-b:global-ab"]
        assert first["warnings"] == ["missing_required_edge:proj-b->proj-c"]
        assert first["policy_checks"][2] == "locked_versions:fail"
        assert second["dependency_edges"] == [
            "proj-b->proj-c:global-bc",
            "proj-c->proj-b:local-cb",
        ]
        assert second["warnings"] == ["dependency_cycle:proj-b|proj-c"]
        assert second["policy_checks"][2] == "locked_versions:ok"


def test_one_thousand_duplicate_source_rows_count_in_audit_but_form_one_topology_arc(
    release_dist: Path, tmp_path: Path
) -> None:
    """Separate observable source multiplicity from the unique graph projection."""
    repeated = "multiplicity,multi-a,multi-b,requires,runtime,no\n" * 1000
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "multiplicity",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\nmultiplicity,qa,linux-x86_64,core,10,true,NOPE\n",
        "component,version,license,kind,critical,size_kb,platforms,owner\nmulti-a,1,MIT,runtime,no,1,linux-x86_64,m\nmulti-b,1,MIT,runtime,no,1,linux-x86_64,m\n",
        "profile,component,version,checksum,source\nmultiplicity,multi-b,1,b,b\nmultiplicity,multi-a,1,a,a\n",
        "profile,parent,child,relation,scope,optional\n" + repeated,
    )
    assert [row["name"] for row in audit["components"]] == ["multi-a", "multi-b"]
    assert audit["dependency_edges"] == ["multi-a->multi-b:requires"] * 1000
    assert audit["warnings"] == []
    assert audit["totals"]["edge_count"] == 1000
    assert audit["totals"]["risk_score"] == 2000


def test_large_duplicate_warning_sources_dedupe_reasons_while_active_self_rows_drive_risk(
    release_dist: Path, tmp_path: Path
) -> None:
    """Deduplicate warning reasons independently from active edge source rows."""
    ghost_locks = "".join(
        f"warning-scale,ghost,{index},g{index},g{index}\n" for index in range(100)
    )
    required = "warning-scale,warn-tool,missing,requires,runtime,no\n" * 100
    self_rows = "warning-scale,warn-tool,warn-tool,self,runtime,no\n" * 100
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "warning-scale",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\nwarning-scale,qa,linux-x86_64,core,10,false,GPL-3.0\n",
        "component,version,license,kind,critical,size_kb,platforms,owner\nwarn-tool,2,GPL-3.0,dev,yes,20,linux-arm64,w\n",
        "profile,component,version,checksum,source\nwarning-scale,warn-tool,2,old,old\nwarning-scale,warn-tool,9,final,final\n" + ghost_locks,
        "profile,parent,child,relation,scope,optional\n" + required + self_rows,
    )
    assert audit["warnings"] == [
        "blocked_license:warn-tool:GPL-3.0",
        "dependency_cycle:warn-tool",
        "dev_dependency:warn-tool",
        "missing_component:ghost",
        "missing_required_edge:warn-tool->missing",
        "platform:warn-tool:linux-x86_64",
        "runtime_size:20:10",
        "version_mismatch:warn-tool:9:2",
    ]
    assert audit["totals"]["direct_lock_count"] == 1
    assert audit["totals"]["edge_count"] == 100
    assert audit["totals"]["risk_score"] == 469


def test_final_catalog_mutation_rebuilds_all_selected_graph_views_then_restores_bytes(
    release_dist: Path,
) -> None:
    """Recompute every selected bundle from the live final catalog row."""
    baseline = dist_snapshot(release_dist)
    profiles = [f"catalog-view-{index}" for index in range(4)]
    matrix = csv_bytes(
        ["profile", "channel", "target", "feature_set", "max_runtime_kb", "allow_dev", "blocked_license"],
        [[name, "qa", "linux-x86_64", "core", 100, "true", "NOPE"] for name in profiles],
    )
    initial_components = csv_bytes(
        ["component", "version", "license", "kind", "critical", "size_kb", "platforms", "owner"],
        [
            ["catalog-common", "1", "MIT", "runtime", "no", 1, "linux-x86_64", "old"],
            ["catalog-common", "2", "BSD-3-Clause", "runtime", "yes", 2, "linux-x86_64", "current"],
        ],
    )
    locks = csv_bytes(
        ["profile", "component", "version", "checksum", "source"],
        [[name, "catalog-common", "2", name, name] for name in profiles],
    )
    updates: dict[Path, str | bytes] = {
        MATRIX: matrix,
        COMPONENTS: initial_components,
        LOCKS: locks,
        EDGES: "profile,parent,child,relation,scope,optional\n",
    }
    updates.update(
        {
            SMOKE / f"{name}.csv": f"profile,expected\n{name},ok\n"
            for name in profiles
        }
    )
    with patched_app_files(updates):
        before = dist_snapshot()
        final_row = csv_bytes(
            ["component", "version", "license", "kind", "critical", "size_kb", "platforms", "owner"],
            [["catalog-common", "2", "MPL-2.0", "doc", "no", 999, "linux-x86_64", "final"]],
        ).splitlines(keepends=True)[1]
        COMPONENTS.write_bytes(initial_components + final_row)
        run_release()
        after = dist_snapshot()
        for name in profiles:
            root = bundle_dir(name)
            data = preview(name)
            assert data["owners"] == ["final"]
            assert data["license_summary"] == ["MPL-2.0"]
            assert data["totals"]["runtime_kb"] == 0
            assert data["totals"]["critical_count"] == 0
            assert (root / "LICENSES.txt").read_bytes() == b"MPL-2.0\n"
            assert before[f"releasekit-{name}-linux-x86_64.tar.gz"] != after[
                f"releasekit-{name}-linux-x86_64.tar.gz"
            ]
            assert before[f"bundles/releasekit-{name}/bin/releasekit"] == after[
                f"bundles/releasekit-{name}/bin/releasekit"
            ]
            assert before[f"bundles/releasekit-{name}/share/policy.json"] == after[
                f"bundles/releasekit-{name}/share/policy.json"
            ]
    assert dist_snapshot() == baseline


def test_manifest_host_target_stays_separate_from_twenty_four_matrix_triplets(
    release_dist: Path,
) -> None:
    """Keep the Rust host in package metadata while every bundle uses its matrix target."""
    profiles = [f"triplet-{index:02d}" for index in range(24)]
    targets = [f"x-vcpkg-triplet-{index:02d}" for index in range(24)]
    matrix = csv_bytes(
        [
            "profile",
            "channel",
            "target",
            "feature_set",
            "max_runtime_kb",
            "allow_dev",
            "blocked_license",
        ],
        [
            [profile, "stable", target, "core", 1, "true", "GPL"]
            for profile, target in zip(profiles, targets, strict=True)
        ],
    )
    components = csv_bytes(
        [
            "component",
            "version",
            "license",
            "kind",
            "critical",
            "size_kb",
            "platforms",
            "owner",
        ],
        [
            [
                f"triplet-component-{index:02d}",
                "1",
                "MIT",
                "runtime",
                "no",
                1,
                target,
                "triplets",
            ]
            for index, target in enumerate(targets)
        ],
    )
    locks = csv_bytes(
        ["profile", "component", "version", "checksum", "source"],
        [
            [
                profile,
                f"triplet-component-{index:02d}",
                "1",
                f"sha-{index:02d}",
                f"cache/{index:02d}",
            ]
            for index, profile in enumerate(profiles)
        ],
    )
    updates: dict[Path, str | bytes] = {
        MATRIX: matrix,
        COMPONENTS: components,
        LOCKS: locks,
        EDGES: "profile,parent,child,relation,scope,optional\n",
    }
    updates.update(
        {
            SMOKE / f"{profile}.csv": f"profile,expected\n{profile},ok\n"
            for profile in profiles
        }
    )
    with patched_app_files(updates):
        host = next(
            line.split(":", 1)[1].strip()
            for line in subprocess.run(
                ["/usr/local/cargo/bin/rustc", "-vV"],
                text=True,
                capture_output=True,
                check=True,
            ).stdout.splitlines()
            if line.startswith("host:")
        )
        data = manifest()
        assert data["package"]["target"] == host
        assert [entry["target"] for entry in data["bundles"]] == targets
        for profile, target in zip(profiles, targets, strict=True):
            assert preview(profile)["target"] == target
            assert json.loads(
                (bundle_dir(profile) / "share" / "policy.json").read_text()
            )["target"] == target


def test_compiled_elf_payload_is_identical_in_target_bundles_and_archives(
    release_dist: Path,
) -> None:
    """Require one actual Cargo-built ELF payload throughout every release layer."""
    built = APP / "target" / "release" / "releasekit"
    built_bytes = built.read_bytes()
    assert built_bytes.startswith(b"\x7fELF")
    for entry in manifest(release_dist)["bundles"]:
        profile = entry["profile"]
        binary = bundle_dir(profile, release_dist) / "bin" / "releasekit"
        assert binary.read_bytes() == built_bytes
        assert binary.stat().st_mode & 0o777 == 0o755
        assert entry["binary_sha256"] == sha256(built)
        with tarfile.open(release_dist / entry["archive"], "r:gz") as archive:
            member = archive.extractfile(
                f"releasekit-{profile}/bin/releasekit"
            )
            assert member is not None
            assert member.read() == built_bytes


def test_two_thousand_forty_eight_way_fanout_fanin_keeps_ready_ties_and_row_counts(
    release_dist: Path, tmp_path: Path
) -> None:
    """Order a very wide DAG while parallel rows remain visible but not structural."""
    middle = [f"fan-mid-{index:04d}" for index in range(2048)]
    names = ["fan-root", *middle, "fan-sink"]
    components = (
        "component,version,license,kind,critical,size_kb,platforms,owner\n"
        + "".join(
            f"{name},1,MIT,runtime,no,0,linux-x86_64,fan\n" for name in names
        )
    )
    locks = (
        "profile,component,version,checksum,source\n"
        + "".join(
            f"wide-fan,{name},1,{index},{index}\n"
            for index, name in enumerate(reversed(names))
        )
    )
    edges: list[list[object]] = []
    for index, name in enumerate(middle):
        edges.append(["wide-fan", "fan-root", name, "opens", "runtime", "no"])
        edges.append(["wide-fan", name, "fan-sink", "closes", "runtime", "no"])
        if index % 4 == 0:
            edges.append(["*", "fan-root", name, "hydrates", "all", "false"])
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "wide-fan",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\n"
        "wide-fan,stable,linux-x86_64,core,0,true,GPL\n",
        components,
        locks,
        csv_bytes(
            ["profile", "parent", "child", "relation", "scope", "optional"],
            edges,
        ).decode(),
    )
    edge_count = 4096 + 512
    assert [row["name"] for row in audit["components"]] == names
    assert audit["warnings"] == []
    assert audit["totals"]["component_count"] == len(names)
    assert audit["totals"]["edge_count"] == edge_count
    assert audit["totals"]["risk_score"] == edge_count * 2


def test_fifty_cycle_condensation_mesh_keeps_every_scc_warning_separate(
    release_dist: Path, tmp_path: Path
) -> None:
    """Order a linked SCC mesh without combining neighboring cycles or descendants."""
    groups = [[f"mesh-{index:02d}-{letter}" for letter in "abc"] for index in range(50)]
    names = [name for group in groups for name in group]
    components = (
        "component,version,license,kind,critical,size_kb,platforms,owner\n"
        + "".join(
            f"{name},1,MIT,runtime,no,0,linux-x86_64,mesh\n" for name in names
        )
    )
    locks = (
        "profile,component,version,checksum,source\n"
        + "".join(
            f"cycle-mesh,{name},1,{index},{index}\n"
            for index, name in enumerate(reversed(names))
        )
    )
    edges: list[list[object]] = []
    for group in groups:
        for index in range(3):
            edges.append(
                [
                    "cycle-mesh",
                    group[index],
                    group[(index + 1) % 3],
                    "ring",
                    "runtime",
                    "no",
                ]
            )
    for index in range(49):
        edges.append(
            [
                "cycle-mesh",
                groups[index][-1],
                groups[index + 1][0],
                "next",
                "runtime",
                "no",
            ]
        )
    for index in range(48):
        edges.append(
            [
                "*",
                groups[index][0],
                groups[index + 2][0],
                "skip",
                "all",
                "no",
            ]
        )
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "cycle-mesh",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\n"
        "cycle-mesh,stable,linux-x86_64,core,0,true,GPL\n",
        components,
        locks,
        csv_bytes(
            ["profile", "parent", "child", "relation", "scope", "optional"],
            edges,
        ).decode(),
    )
    warnings = sorted(f"dependency_cycle:{'|'.join(group)}" for group in groups)
    assert [row["name"] for row in audit["components"]] == names
    assert audit["warnings"] == warnings
    assert audit["totals"]["edge_count"] == 247
    assert audit["totals"]["risk_score"] == len(warnings) * 31 + 247 * 2


def test_thirty_two_profile_scope_cross_product_matches_simple_and_nested_logic(
    release_dist: Path, tmp_path: Path
) -> None:
    """Evaluate feature, target, and channel predicates over a full 32-row matrix."""
    matrix_rows: list[list[object]] = []
    lock_rows: list[list[object]] = []
    cases: list[tuple[str, set[str], str, str]] = []
    index = 0
    for mask in range(8):
        features = {
            token
            for bit, token in enumerate(("a", "b", "c"))
            if mask & (1 << bit)
        }
        for target in ("linux-x86_64", "linux-arm64"):
            for channel in ("stable", "preview"):
                profile = f"scope-grid-{index:02d}"
                matrix_rows.append(
                    [
                        profile,
                        channel,
                        target,
                        "+".join(sorted(features)),
                        2,
                        "true",
                        "GPL",
                    ]
                )
                lock_rows.extend(
                    [
                        [profile, "grid-parent", "1", f"{profile}-p", "p"],
                        [profile, "grid-child", "1", f"{profile}-c", "c"],
                    ]
                )
                cases.append((profile, features, target, channel))
                index += 1
    specs = [
        ("always", "runtime"),
        ("has-a", "feature:a"),
        ("not-a", "!feature:a"),
        ("has-c", "feature:c"),
        ("x86", "target:linux-x86_64"),
        ("arm", "target:linux-arm64"),
        ("stable", "channel:stable"),
        ("preview", "channel:preview"),
        ("triple", "feature:b&target:linux-arm64&channel:preview"),
        ("any", "cfg:any(feature:c,channel:preview)"),
        (
            "all",
            "cfg:all(any(feature:a,feature:b),not(channel:stable))",
        ),
        ("nested-not", "cfg:not(all(feature:a,target:linux-x86_64))"),
        ("bad-empty", "cfg:any(feature:a,)"),
        ("bad-tail", "cfg:not(feature:a))"),
    ]
    matrix_text = csv_bytes(
        [
            "profile",
            "channel",
            "target",
            "feature_set",
            "max_runtime_kb",
            "allow_dev",
            "blocked_license",
        ],
        matrix_rows,
    ).decode()
    locks_text = csv_bytes(
        ["profile", "component", "version", "checksum", "source"], lock_rows
    ).decode()
    edges_text = csv_bytes(
        ["profile", "parent", "child", "relation", "scope", "optional"],
        [["*", "grid-parent", "grid-child", relation, scope, "no"] for relation, scope in specs],
    ).decode()
    components_text = (
        "component,version,license,kind,critical,size_kb,platforms,owner\n"
        "grid-parent,1,MIT,runtime,no,1,linux-x86_64|linux-arm64,grid\n"
        "grid-child,1,MIT,runtime,no,1,linux-x86_64|linux-arm64,grid\n"
    )
    for profile, features, target, channel in cases:
        audit, _raw, _out = run_custom_audit(
            release_dist,
            tmp_path,
            profile,
            matrix_text,
            components_text,
            locks_text,
            edges_text,
        )
        expected = {"always"}
        expected.add("has-a" if "a" in features else "not-a")
        if "c" in features:
            expected.add("has-c")
        expected.add("x86" if target == "linux-x86_64" else "arm")
        expected.add("stable" if channel == "stable" else "preview")
        if "b" in features and target == "linux-arm64" and channel == "preview":
            expected.add("triple")
        if "c" in features or channel == "preview":
            expected.add("any")
        if features & {"a", "b"} and channel != "stable":
            expected.add("all")
        if not ("a" in features and target == "linux-x86_64"):
            expected.add("nested-not")
        assert audit["dependency_edges"] == sorted(
            f"grid-parent->grid-child:{relation}" for relation in expected
        )
        assert audit["warnings"] == []
        assert audit["totals"]["edge_count"] == len(expected)


def test_five_thousand_source_rows_remain_observable_over_one_topology_arc(
    release_dist: Path, tmp_path: Path
) -> None:
    """Preserve a very large edge history without inflating structural indegree."""
    rows = [
        [
            "*" if index % 3 == 0 else "five-thousand",
            "many-parent",
            "many-child",
            f"relation-{index % 11}",
            "runtime",
            "no",
        ]
        for index in range(5000)
    ]
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "five-thousand",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\n"
        "five-thousand,stable,linux-x86_64,core,2,true,GPL\n",
        "component,version,license,kind,critical,size_kb,platforms,owner\n"
        "many-parent,1,MIT,runtime,no,1,linux-x86_64,many\n"
        "many-child,1,MIT,runtime,no,1,linux-x86_64,many\n",
        "profile,component,version,checksum,source\n"
        "five-thousand,many-child,1,c,c\n"
        "five-thousand,many-parent,1,p,p\n",
        csv_bytes(
            ["profile", "parent", "child", "relation", "scope", "optional"],
            rows,
        ).decode(),
    )
    assert [row["name"] for row in audit["components"]] == [
        "many-parent",
        "many-child",
    ]
    assert len(audit["dependency_edges"]) == 5000
    assert audit["dependency_edges"] == sorted(audit["dependency_edges"])
    assert audit["warnings"] == []
    assert audit["totals"]["edge_count"] == 5000
    assert audit["totals"]["risk_score"] == 10000


def test_two_hundred_component_policy_stack_preserves_all_accounting_axes(
    release_dist: Path, tmp_path: Path
) -> None:
    """Accumulate every policy family over a large selected component set."""
    count = 200
    component_rows: list[list[object]] = []
    lock_rows: list[list[object]] = []
    edge_rows: list[list[object]] = []
    warnings: list[str] = []
    runtime = 0
    dev_count = 0
    critical_count = 0
    for index in range(count):
        name = f"policy-scale-{index:03d}"
        kind = "dev" if index % 5 == 0 else "doc" if index % 7 == 0 else "runtime"
        critical = index % 4 == 0
        license_id = "GPL-3.0" if index % 6 == 0 else "MIT"
        platforms = "linux-arm64" if index % 8 == 0 else "linux-x86_64"
        version = "0" if index % 9 == 0 else "1"
        size = index + 1
        component_rows.append(
            [
                name,
                "1",
                license_id,
                kind,
                "yes" if critical else "no",
                size,
                platforms,
                f"owner-{index % 17}",
            ]
        )
        lock_rows.append(
            ["policy-scale", name, version, f"sha-{index}", f"cache/{index}"]
        )
        if kind != "doc":
            runtime += size
        if kind == "dev":
            dev_count += 1
            warnings.append(f"dev_dependency:{name}")
        if critical:
            critical_count += 1
        if license_id == "GPL-3.0":
            warnings.append(f"blocked_license:{name}:GPL-3.0")
        if platforms == "linux-arm64":
            warnings.append(f"platform:{name}:linux-x86_64")
        if version != "1":
            warnings.append(f"version_mismatch:{name}:{version}:1")
        if index:
            edge_rows.append(
                [
                    "policy-scale",
                    f"policy-scale-{index - 1:03d}",
                    name,
                    "requires",
                    "runtime",
                    "no",
                ]
            )
        if index % 16 == 0:
            edge_rows.append(
                [
                    "policy-scale",
                    name,
                    f"missing-{index:03d}",
                    "required",
                    "runtime",
                    "no",
                ]
            )
            warnings.append(f"missing_required_edge:{name}->missing-{index:03d}")
    limit = runtime - 1
    warnings.append(f"runtime_size:{runtime}:{limit}")
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "policy-scale",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\n"
        f"policy-scale,stable,linux-x86_64,core,{limit},false,GPL-3.0\n",
        csv_bytes(
            [
                "component",
                "version",
                "license",
                "kind",
                "critical",
                "size_kb",
                "platforms",
                "owner",
            ],
            component_rows,
        ).decode(),
        csv_bytes(
            ["profile", "component", "version", "checksum", "source"], lock_rows
        ).decode(),
        csv_bytes(
            ["profile", "parent", "child", "relation", "scope", "optional"],
            edge_rows,
        ).decode(),
    )
    expected_warnings = sorted(set(warnings))
    assert audit["warnings"] == expected_warnings
    assert audit["policy_checks"] == [
        "blocked_license:fail",
        "dev_policy:fail",
        "locked_versions:fail",
        "platforms:fail",
        f"runtime_size:fail:{runtime}/{limit}",
    ]
    assert audit["totals"]["runtime_kb"] == runtime
    assert audit["totals"]["dev_component_count"] == dev_count
    assert audit["totals"]["critical_count"] == critical_count
    assert audit["totals"]["edge_count"] == count - 1
    assert audit["totals"]["risk_score"] == (
        len(expected_warnings) * 31
        + dev_count * 3
        + critical_count * 5
        + (count - 1) * 2
        + 13
    )


def test_hundred_component_catalog_and_lock_histories_preserve_evidence_not_stale_values(
    release_dist: Path,
) -> None:
    """Replay eight hundred source rows while only final generations drive output."""
    profile = "history-release"
    component_rows: list[list[object]] = []
    lock_rows: list[list[object]] = []
    edge_rows: list[list[object]] = []
    for index in range(100):
        name = f"history-component-{index:03d}"
        component_rows.extend(
            [
                [name, "0", "GPL-3.0", "doc", "yes", 9999, "linux-arm64", "old"],
                [name, "1", "MPL-2.0", "dev", "yes", 8888, "linux-arm64", "middle"],
                [
                    name,
                    f"2.{index}",
                    "MIT" if index % 2 == 0 else "BSD-3-Clause",
                    "runtime",
                    "no",
                    1,
                    "linux-x86_64",
                    f"owner-{index % 9}",
                ],
            ]
        )
        lock_rows.extend(
            [
                [profile, name, "0", f"a-{index}", "old/a"],
                [profile, name, "1", f"b-{index}", "old/b"],
                [profile, name, "8", f"c-{index}", "old/c"],
                [profile, name, "9", f"d-{index}", "old/d"],
                [profile, name, f"2.{index}", f"final-{index}", f"cache/{index}"],
            ]
        )
        if index:
            edge_rows.append(
                [
                    profile,
                    f"history-component-{index - 1:03d}",
                    name,
                    "requires",
                    "runtime",
                    "no",
                ]
            )
    for index in range(25):
        lock_rows.extend(
            [
                [profile, f"ghost-history-{index:02d}", "1", "old", "old"],
                [profile, f"ghost-history-{index:02d}", "2", "final", "final"],
            ]
        )
    with patched_app_files(
        {
            MATRIX: csv_bytes(
                [
                    "profile",
                    "channel",
                    "target",
                    "feature_set",
                    "max_runtime_kb",
                    "allow_dev",
                    "blocked_license",
                ],
                [[profile, "stable", "linux-x86_64", "core", 100, "true", "GPL-3.0"]],
            ),
            COMPONENTS: csv_bytes(
                [
                    "component",
                    "version",
                    "license",
                    "kind",
                    "critical",
                    "size_kb",
                    "platforms",
                    "owner",
                ],
                component_rows,
            ),
            LOCKS: csv_bytes(
                ["profile", "component", "version", "checksum", "source"],
                lock_rows,
            ),
            EDGES: csv_bytes(
                ["profile", "parent", "child", "relation", "scope", "optional"],
                edge_rows,
            ),
            SMOKE / f"{profile}.csv": f"profile,expected\n{profile},ok\n",
        }
    ):
        root = bundle_dir(profile)
        audit = preview(profile)
        assert len(read_csv(root / "share" / "components.csv")) == 300
        assert len(read_csv(root / "share" / "locks.csv")) == 550
        assert [row["name"] for row in audit["components"]] == [
            f"history-component-{index:03d}" for index in range(100)
        ]
        assert [row["checksum"] for row in audit["components"]] == [
            f"final-{index}" for index in range(100)
        ]
        assert audit["warnings"] == [
            f"missing_component:ghost-history-{index:02d}" for index in range(25)
        ]
        assert audit["totals"]["direct_lock_count"] == 100
        assert audit["totals"]["runtime_kb"] == 100
        assert audit["totals"]["edge_count"] == 99
        assert audit["totals"]["risk_score"] == 25 * 31 + 99 * 2
        assert (root / "LICENSES.txt").read_bytes() == b"BSD-3-Clause\nMIT\n"


def test_large_crlf_inputs_ignore_blank_records_and_preserve_every_surviving_source_row(
    release_dist: Path,
) -> None:
    """Filter hundreds of CRLF records without creating rows from blank lines."""
    profile = "crlf-scale"
    names = [f"crlf-component-{index:03d}" for index in range(250)]
    component_bytes = csv_bytes(
        [
            "component",
            "version",
            "license",
            "kind",
            "critical",
            "size_kb",
            "platforms",
            "owner",
        ],
        [
            [name, "1", "MIT", "runtime", "no", 1, "linux-x86_64", "crlf"]
            for name in names
        ],
        "\r\n",
    )
    selected = names[::3]
    lock_bytes = csv_bytes(
        ["profile", "component", "version", "checksum", "source"],
        [[profile, name, "1", name, f"cache/{name}"] for name in selected],
        "\r\n",
    )
    edge_bytes = csv_bytes(
        ["profile", "parent", "child", "relation", "scope", "optional"],
        [
            [profile, selected[index], selected[index + 1], "requires", "runtime", "no"]
            for index in range(len(selected) - 1)
        ],
        "\r\n",
    )

    def add_blank_records(data: bytes, interval: int) -> bytes:
        lines = data.splitlines(keepends=True)
        return b"".join(
            line + (b"\r\n" if index % interval == 0 else b"")
            for index, line in enumerate(lines)
        )

    matrix = add_blank_records(
        csv_bytes(
            [
                "profile",
                "channel",
                "target",
                "feature_set",
                "max_runtime_kb",
                "allow_dev",
                "blocked_license",
            ],
            [[profile, "stable", "linux-x86_64", "core", len(selected), "true", "GPL"]],
            "\r\n",
        ),
        1,
    )
    with patched_app_files(
        {
            MATRIX: matrix,
            COMPONENTS: add_blank_records(component_bytes, 4),
            LOCKS: add_blank_records(lock_bytes, 3),
            EDGES: add_blank_records(edge_bytes, 5),
            SMOKE / f"{profile}.csv": f"profile,expected\r\n{profile},ok\r\n",
        }
    ):
        root = bundle_dir(profile)
        audit = preview(profile)
        assert len(read_csv(root / "share" / "components.csv")) == len(selected)
        assert len(read_csv(root / "share" / "locks.csv")) == len(selected)
        assert len(read_csv(root / "share" / "dependencies.csv")) == len(selected) - 1
        assert [row["name"] for row in audit["components"]] == selected
        assert audit["warnings"] == []
        assert audit["totals"]["runtime_kb"] == len(selected)
        assert audit["totals"]["edge_count"] == len(selected) - 1
        for relative in [
            "share/release_matrix.csv",
            "share/components.csv",
            "share/locks.csv",
            "share/dependencies.csv",
        ]:
            assert b"\r\n" in (root / relative).read_bytes()


def test_restrictive_umask_cannot_change_unpacked_or_archived_release_modes(
    release_dist: Path,
) -> None:
    """Normalize every mode and gzip header even when the caller uses umask 077."""
    env = os.environ.copy()
    env["CARGO_NET_OFFLINE"] = "true"
    subprocess.run(
        ["bash", "-c", "umask 077; /app/scripts/release.sh"],
        cwd=APP,
        env=env,
        check=True,
        timeout=300,
    )
    assert_complete_release_contract()
    for entry in manifest()["bundles"]:
        root = bundle_dir(entry["profile"])
        for path in [root, *root.rglob("*")]:
            relative = path.relative_to(root).as_posix() if path != root else ""
            expected = (
                0o755
                if path.is_dir()
                or relative in {"bin/releasekit", "share/run-smoke.sh"}
                else 0o644
            )
            assert path.stat().st_mode & 0o777 == expected
        raw = (DIST / entry["archive"]).read_bytes()
        assert raw[:3] == b"\x1f\x8b\x08"
        assert raw[3] == 0
        assert raw[4:8] == b"\0\0\0\0"


def test_twenty_four_concurrent_relocated_smoke_runs_never_share_build_state(
    release_dist: Path, tmp_path: Path
) -> None:
    """Run copied bundles concurrently with default and nested explicit outputs."""
    profiles = [entry["profile"] for entry in manifest(release_dist)["bundles"]]
    expected = {profile: preview(profile, release_dist) for profile in profiles}
    jobs: list[tuple[str, Path, Path, bool]] = []
    for index in range(24):
        profile = profiles[index % len(profiles)]
        root = tmp_path / "concurrent relocated caches" / f"copy-{index:02d}" / (
            f"releasekit-{profile}"
        )
        shutil.copytree(bundle_dir(profile, release_dist), root)
        default = index % 2 == 0
        output = (
            root / f"audit-{profile}.json"
            if default
            else root / "nested results" / f"result {index:02d}.json"
        )
        jobs.append((profile, root, output, default))

    def invoke(job: tuple[str, Path, Path, bool]) -> tuple[str, Path]:
        profile, root, output, default = job
        command = ["sh", str(root / "share" / "run-smoke.sh")]
        if not default:
            command.append(str(output))
        subprocess.run(command, cwd=tmp_path, check=True, timeout=120)
        return profile, output

    with hidden_build_sources("concurrent-vcpkg"):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(invoke, jobs))
    for profile, output in results:
        assert json.loads(output.read_text()) == expected[profile]
        assert_single_lf(output)


def test_twenty_repeated_cli_flag_sets_choose_only_the_final_complete_input_set(
    release_dist: Path, tmp_path: Path
) -> None:
    """Ignore many earlier named values and create only the last requested output."""
    headers = {
        "matrix": [
            "profile",
            "channel",
            "target",
            "feature_set",
            "max_runtime_kb",
            "allow_dev",
            "blocked_license",
        ],
        "components": [
            "component",
            "version",
            "license",
            "kind",
            "critical",
            "size_kb",
            "platforms",
            "owner",
        ],
        "locks": ["profile", "component", "version", "checksum", "source"],
        "edges": ["profile", "parent", "child", "relation", "scope", "optional"],
    }
    decoys: list[dict[str, Path]] = []
    outputs: list[Path] = []
    for index in range(20):
        root = tmp_path / f"decoy-{index:02d}"
        root.mkdir(parents=True)
        files = {}
        for name, keys in headers.items():
            path = root / f"{name}.csv"
            path.write_text(",".join(keys) + "\n")
            files[name] = path
        decoys.append(files)
        outputs.append(root / "wrong.json")
    final = tmp_path / "final"
    final.mkdir()
    final_files = {
        "matrix": final / "matrix.csv",
        "components": final / "components.csv",
        "locks": final / "locks.csv",
        "edges": final / "edges.csv",
    }
    final_files["matrix"].write_text(
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\n"
        "flag-final,stable,linux-x86_64,core,2,true,GPL\n"
    )
    final_files["components"].write_text(
        "component,version,license,kind,critical,size_kb,platforms,owner\n"
        "flag-a,1,MIT,runtime,no,1,linux-x86_64,flags\n"
        "flag-b,1,MIT,runtime,no,1,linux-x86_64,flags\n"
    )
    final_files["locks"].write_text(
        "profile,component,version,checksum,source\n"
        "flag-final,flag-b,1,b,b\n"
        "flag-final,flag-a,1,a,a\n"
    )
    final_files["edges"].write_text(
        "profile,parent,child,relation,scope,optional\n"
        "flag-final,flag-a,flag-b,requires,runtime,no\n"
    )
    final_out = final / "deep" / "audit.json"
    command = [str(bundle_dir("edge", release_dist) / "bin" / "releasekit"), "audit"]
    for index, files in enumerate(decoys):
        command.extend(
            [
                "--profile",
                f"wrong-{index}",
                "--matrix",
                str(files["matrix"]),
                "--components",
                str(files["components"]),
                "--locks",
                str(files["locks"]),
                "--edges",
                str(files["edges"]),
                "--out",
                str(outputs[index]),
            ]
        )
    command.extend(
        [
            "--profile",
            "flag-final",
            "--matrix",
            str(final_files["matrix"]),
            "--components",
            str(final_files["components"]),
            "--locks",
            str(final_files["locks"]),
            "--edges",
            str(final_files["edges"]),
            "--out",
            str(final_out),
        ]
    )
    subprocess.run(command, check=True)
    audit = json.loads(final_out.read_text())
    assert [row["name"] for row in audit["components"]] == ["flag-a", "flag-b"]
    assert audit["dependency_edges"] == ["flag-a->flag-b:requires"]
    assert all(not path.exists() for path in outputs)
    assert_single_lf(final_out)


def test_unicode_and_dense_escaping_round_trip_through_full_release_and_archive(
    release_dist: Path,
) -> None:
    """Carry Unicode, quotes, commas, tabs, and backslashes through every text layer."""
    profile = "unicode-cache"
    channel = 'préview, "蓝"\\night\tone'
    version = '1, "β"\\branch\tv'
    checksum = 'sha,"雪"\\tail\tend'
    source = 'cache path/路径,"x"\\y\tblob'
    owner = 'équipe,"蓝"\\ops\tone'
    with patched_app_files(
        {
            MATRIX: csv_bytes(
                [
                    "profile",
                    "channel",
                    "target",
                    "feature_set",
                    "max_runtime_kb",
                    "allow_dev",
                    "blocked_license",
                ],
                [[profile, channel, "linux-x86_64", "core", 1, "true", "GPL"]],
            ),
            COMPONENTS: csv_bytes(
                [
                    "component",
                    "version",
                    "license",
                    "kind",
                    "critical",
                    "size_kb",
                    "platforms",
                    "owner",
                ],
                [["unicode-port", version, "MIT", "runtime", "no", 1, "linux-x86_64", owner]],
            ),
            LOCKS: csv_bytes(
                ["profile", "component", "version", "checksum", "source"],
                [[profile, "unicode-port", version, checksum, source]],
            ),
            EDGES: "profile,parent,child,relation,scope,optional\n",
            SMOKE / f"{profile}.csv": f"profile,expected\n{profile},路径\n",
        }
    ):
        root = bundle_dir(profile)
        component = preview(profile)["components"][0]
        assert preview(profile)["channel"] == channel
        assert preview(profile)["owners"] == [owner]
        assert component["version"] == version
        assert component["checksum"] == checksum
        assert component["source"] == source
        assert json.loads((root / "share" / "policy.json").read_text())[
            "channel"
        ] == channel
        entry = manifest()["bundles"][0]
        with tarfile.open(DIST / entry["archive"], "r:gz") as archive:
            archived = archive.extractfile(
                f"releasekit-{profile}/share/audit-preview.json"
            )
            assert archived is not None
            assert json.loads(archived.read()) == preview(profile)


def test_shared_lock_mutation_invalidates_only_profiles_with_that_exact_lock(
    release_dist: Path,
) -> None:
    """Limit a lock checksum and source change to profiles that select that component."""
    profiles = [f"lock-view-{index:02d}" for index in range(12)]
    matrix = csv_bytes(
        [
            "profile",
            "channel",
            "target",
            "feature_set",
            "max_runtime_kb",
            "allow_dev",
            "blocked_license",
        ],
        [[profile, "stable", "linux-x86_64", "core", 2, "true", "GPL"] for profile in profiles],
    )
    components = csv_bytes(
        [
            "component",
            "version",
            "license",
            "kind",
            "critical",
            "size_kb",
            "platforms",
            "owner",
        ],
        [
            ["shared-lock", "1", "MIT", "runtime", "no", 1, "linux-x86_64", "shared"],
            *[
                [
                    f"unique-lock-{index:02d}",
                    "1",
                    "MIT",
                    "runtime",
                    "no",
                    1,
                    "linux-x86_64",
                    "unique",
                ]
                for index in range(12)
            ],
        ],
    )
    initial_rows: list[list[object]] = []
    changed_rows: list[list[object]] = []
    for index, profile in enumerate(profiles):
        unique = [profile, f"unique-lock-{index:02d}", "1", f"u-{index}", "unique"]
        initial_rows.append(unique)
        changed_rows.append(unique)
        if index % 2 == 0:
            initial_rows.append([profile, "shared-lock", "1", f"old-{index}", "old"])
            changed_rows.append([profile, "shared-lock", "1", f"new-{index}", "new"])
    initial_locks = csv_bytes(
        ["profile", "component", "version", "checksum", "source"], initial_rows
    )
    changed_locks = csv_bytes(
        ["profile", "component", "version", "checksum", "source"], changed_rows
    )
    updates: dict[Path, str | bytes] = {
        MATRIX: matrix,
        COMPONENTS: components,
        LOCKS: initial_locks,
        EDGES: "profile,parent,child,relation,scope,optional\n",
    }
    updates.update(
        {
            SMOKE / f"{profile}.csv": f"profile,expected\n{profile},ok\n"
            for profile in profiles
        }
    )
    with patched_app_files(updates):
        before = dist_snapshot()
        LOCKS.write_bytes(changed_locks)
        run_release()
        after = dist_snapshot()
        changed = {
            path
            for path in before.keys() | after.keys()
            if before.get(path) != after.get(path)
        }
        expected = {"release-manifest.json", "checksums.sha256"}
        for index, profile in enumerate(profiles):
            if index % 2 == 0:
                expected.update(
                    {
                        f"bundles/releasekit-{profile}/share/locks.csv",
                        f"bundles/releasekit-{profile}/share/audit-preview.json",
                        f"releasekit-{profile}-linux-x86_64.tar.gz",
                    }
                )
                shared = next(
                    row for row in preview(profile)["components"] if row["name"] == "shared-lock"
                )
                assert shared["checksum"] == f"new-{index}"
                assert shared["source"] == "new"
        assert changed == expected


def test_final_catalog_change_invalidates_only_twelve_profile_subset_consumers(
    release_dist: Path,
) -> None:
    """Rebuild only profiles selecting a changed final catalog component."""
    profiles = [f"catalog-subset-{index:02d}" for index in range(12)]
    matrix = csv_bytes(
        [
            "profile",
            "channel",
            "target",
            "feature_set",
            "max_runtime_kb",
            "allow_dev",
            "blocked_license",
        ],
        [[profile, "stable", "linux-x86_64", "core", 2, "true", "GPL"] for profile in profiles],
    )
    initial_components = csv_bytes(
        [
            "component",
            "version",
            "license",
            "kind",
            "critical",
            "size_kb",
            "platforms",
            "owner",
        ],
        [
            ["catalog-shared", "1", "MIT", "runtime", "yes", 1, "linux-x86_64", "old"],
            *[
                [
                    f"catalog-unique-{index:02d}",
                    "1",
                    "MIT",
                    "runtime",
                    "no",
                    1,
                    "linux-x86_64",
                    "unique",
                ]
                for index in range(12)
            ],
        ],
    )
    locks: list[list[object]] = []
    for index, profile in enumerate(profiles):
        locks.append([profile, f"catalog-unique-{index:02d}", "1", "u", "u"])
        if index % 3 == 0:
            locks.append([profile, "catalog-shared", "1", "s", "s"])
    updates: dict[Path, str | bytes] = {
        MATRIX: matrix,
        COMPONENTS: initial_components,
        LOCKS: csv_bytes(
            ["profile", "component", "version", "checksum", "source"], locks
        ),
        EDGES: "profile,parent,child,relation,scope,optional\n",
    }
    updates.update(
        {
            SMOKE / f"{profile}.csv": f"profile,expected\n{profile},ok\n"
            for profile in profiles
        }
    )
    with patched_app_files(updates):
        before = dist_snapshot()
        final_row = csv_bytes(
            [
                "component",
                "version",
                "license",
                "kind",
                "critical",
                "size_kb",
                "platforms",
                "owner",
            ],
            [["catalog-shared", "1", "MPL-2.0", "doc", "no", 999, "linux-x86_64", "final"]],
        ).splitlines(keepends=True)[1]
        COMPONENTS.write_bytes(initial_components + final_row)
        run_release()
        after = dist_snapshot()
        changed = {
            path
            for path in before.keys() | after.keys()
            if before.get(path) != after.get(path)
        }
        expected = {"release-manifest.json", "checksums.sha256"}
        for index, profile in enumerate(profiles):
            if index % 3 == 0:
                expected.update(
                    {
                        f"bundles/releasekit-{profile}/share/components.csv",
                        f"bundles/releasekit-{profile}/share/audit-preview.json",
                        f"bundles/releasekit-{profile}/LICENSES.txt",
                        f"releasekit-{profile}-linux-x86_64.tar.gz",
                    }
                )
                audit = preview(profile)
                assert "MPL-2.0" in audit["license_summary"]
                assert audit["totals"]["critical_count"] == 0
        assert changed == expected


def test_global_reverse_edge_invalidates_every_graph_layer_across_sixteen_profiles(
    release_dist: Path,
) -> None:
    """Apply one global edge row to every selected graph without changing payload layers."""
    profiles = [f"graph-view-{index:02d}" for index in range(16)]
    updates: dict[Path, str | bytes] = {
        MATRIX: csv_bytes(
            [
                "profile",
                "channel",
                "target",
                "feature_set",
                "max_runtime_kb",
                "allow_dev",
                "blocked_license",
            ],
            [[profile, "stable", "linux-x86_64", "core", 2, "true", "GPL"] for profile in profiles],
        ),
        COMPONENTS: csv_bytes(
            [
                "component",
                "version",
                "license",
                "kind",
                "critical",
                "size_kb",
                "platforms",
                "owner",
            ],
            [
                ["graph-a", "1", "MIT", "runtime", "no", 1, "linux-x86_64", "graph"],
                ["graph-b", "1", "MIT", "runtime", "no", 1, "linux-x86_64", "graph"],
            ],
        ),
        LOCKS: csv_bytes(
            ["profile", "component", "version", "checksum", "source"],
            [
                row
                for profile in profiles
                for row in (
                    [profile, "graph-a", "1", "a", "a"],
                    [profile, "graph-b", "1", "b", "b"],
                )
            ],
        ),
        EDGES: (
            "profile,parent,child,relation,scope,optional\n"
            "*,graph-a,graph-b,forward,runtime,no\n"
        ),
    }
    updates.update(
        {
            SMOKE / f"{profile}.csv": f"profile,expected\n{profile},ok\n"
            for profile in profiles
        }
    )
    with patched_app_files(updates):
        before = dist_snapshot()
        EDGES.write_text(
            EDGES.read_text() + "*,graph-b,graph-a,reverse,runtime,no\n"
        )
        run_release()
        after = dist_snapshot()
        changed = {
            path
            for path in before.keys() | after.keys()
            if before.get(path) != after.get(path)
        }
        expected = {"release-manifest.json", "checksums.sha256"}
        for profile in profiles:
            expected.update(
                {
                    f"bundles/releasekit-{profile}/share/dependencies.csv",
                    f"bundles/releasekit-{profile}/share/audit-preview.json",
                    f"releasekit-{profile}-linux-x86_64.tar.gz",
                }
            )
            assert preview(profile)["warnings"] == [
                "dependency_cycle:graph-a|graph-b"
            ]
        assert changed == expected


def test_one_of_twenty_matrix_rows_changes_all_matrix_layers_but_one_policy_view(
    release_dist: Path,
) -> None:
    """Separate whole-matrix archive invalidation from one profile's policy change."""
    profiles = [f"matrix-view-{index:02d}" for index in range(20)]
    rows = [
        [profile, "stable", "linux-x86_64", "core", 1, "true", "GPL"]
        for profile in profiles
    ]
    updates: dict[Path, str | bytes] = {
        MATRIX: csv_bytes(
            [
                "profile",
                "channel",
                "target",
                "feature_set",
                "max_runtime_kb",
                "allow_dev",
                "blocked_license",
            ],
            rows,
        ),
        COMPONENTS: csv_bytes(
            [
                "component",
                "version",
                "license",
                "kind",
                "critical",
                "size_kb",
                "platforms",
                "owner",
            ],
            [
                [
                    f"matrix-component-{index:02d}",
                    "1",
                    "MIT",
                    "runtime",
                    "no",
                    1,
                    "linux-x86_64",
                    "matrix",
                ]
                for index in range(20)
            ],
        ),
        LOCKS: csv_bytes(
            ["profile", "component", "version", "checksum", "source"],
            [
                [profile, f"matrix-component-{index:02d}", "1", "m", "m"]
                for index, profile in enumerate(profiles)
            ],
        ),
        EDGES: "profile,parent,child,relation,scope,optional\n",
    }
    updates.update(
        {
            SMOKE / f"{profile}.csv": f"profile,expected\n{profile},ok\n"
            for profile in profiles
        }
    )
    with patched_app_files(updates):
        before = dist_snapshot()
        rows[7][1] = 'preview, "blue"'
        MATRIX.write_bytes(
            csv_bytes(
                [
                    "profile",
                    "channel",
                    "target",
                    "feature_set",
                    "max_runtime_kb",
                    "allow_dev",
                    "blocked_license",
                ],
                rows,
            )
        )
        run_release()
        after = dist_snapshot()
        changed = {
            path
            for path in before.keys() | after.keys()
            if before.get(path) != after.get(path)
        }
        expected = {"release-manifest.json", "checksums.sha256"}
        for profile in profiles:
            expected.update(
                {
                    f"bundles/releasekit-{profile}/share/release_matrix.csv",
                    f"releasekit-{profile}-linux-x86_64.tar.gz",
                }
            )
        selected = profiles[7]
        expected.update(
            {
                f"bundles/releasekit-{selected}/share/policy.json",
                f"bundles/releasekit-{selected}/share/audit-preview.json",
            }
        )
        assert preview(selected)["channel"] == 'preview, "blue"'
        assert changed == expected


def test_release_removes_eight_hundred_nested_stale_cache_artifacts_before_build(
    release_dist: Path,
) -> None:
    """Delete a large stale bundle forest and reconstruct only current profiles."""
    stale = DIST / "bundles" / "releasekit-retired" / "share" / "cache"
    for index in range(800):
        path = stale / f"bucket-{index % 23:02d}" / f"stale-{index:04d}.bin"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"stale-{index}".encode())
    (DIST / "releasekit-retired-linux-x86_64.tar.gz").write_bytes(b"stale")
    (DIST / "obsolete-manifest.json").write_text("{}\n")
    run_release()
    assert not (DIST / "bundles" / "releasekit-retired").exists()
    assert not (DIST / "releasekit-retired-linux-x86_64.tar.gz").exists()
    assert not (DIST / "obsolete-manifest.json").exists()
    assert all(
        "retired" not in row and "obsolete" not in row
        for row in (DIST / "checksums.sha256").read_text().splitlines()
    )


def test_coordinated_workspace_matrix_catalog_lock_graph_and_smoke_restore_all_bytes(
    release_dist: Path,
) -> None:
    """Mutate every build layer, prove repeatability, and restore the exact baseline."""
    baseline = dist_snapshot(release_dist)
    root_manifest = APP / "Cargo.toml"
    cargo_lock = APP / "Cargo.lock"
    new_root = root_manifest.read_text().replace(
        'version = "0.7.0"', 'version = "1.4.2"', 1
    )
    new_lock = cargo_lock.read_text()
    for crate in WORKSPACE_NAMES:
        new_lock = new_lock.replace(
            f'name = "{crate}"\nversion = "0.7.0"',
            f'name = "{crate}"\nversion = "1.4.2"',
        )
    profile = "coordinated-restore"
    updates: dict[Path, str | bytes] = {
        root_manifest: new_root,
        cargo_lock: new_lock,
        MATRIX: MATRIX.read_text()
        + f"{profile},preview,linux-x86_64,core+signed,50,true,GPL-3.0\n",
        COMPONENTS: COMPONENTS.read_text()
        + "restore-a,3,MIT,runtime,yes,10,linux-x86_64,restore\n"
        + "restore-b,3,BSD-3-Clause,runtime,no,20,linux-x86_64,restore\n",
        LOCKS: LOCKS.read_text()
        + f"{profile},restore-b,3,b,b\n"
        + f"{profile},restore-a,3,a,a\n",
        EDGES: EDGES.read_text()
        + f"{profile},restore-a,restore-b,requires,feature:signed,no\n",
        SMOKE / f"{profile}.csv": f"profile,expected\n{profile},restore-b\n",
    }
    with patched_app_files(updates):
        first = dist_snapshot()
        data = manifest()
        assert data["package"]["version"] == "1.4.2"
        assert [row["version"] for row in data["workspace"]] == ["1.4.2"] * 3
        assert (bundle_dir(profile) / "VERSION").read_bytes() == b"1.4.2\n"
        assert preview(profile)["dependency_edges"] == [
            "restore-a->restore-b:requires"
        ]
        run_release()
        assert dist_snapshot() == first
    assert dist_snapshot() == baseline


def test_two_thousand_lock_rows_partition_exact_wildcard_foreign_and_ghost_evidence(
    release_dist: Path, tmp_path: Path
) -> None:
    """Select exact locks only from a large mixed lock population."""
    names = [f"partition-port-{index:03d}" for index in range(300)]
    components = csv_bytes(
        [
            "component",
            "version",
            "license",
            "kind",
            "critical",
            "size_kb",
            "platforms",
            "owner",
        ],
        [
            [name, "1", "MIT", "runtime", "no", 1, "linux-x86_64", "partition"]
            for name in names
        ],
    ).decode()
    selected = names[::3]
    lock_rows: list[list[object]] = []
    for index, name in enumerate(names):
        if index % 3 == 0:
            lock_rows.append(["lock-partition", name, "1", f"exact-{index}", "exact"])
        else:
            lock_rows.append(["*", name, "1", f"wild-{index}", "wild"])
        lock_rows.append(["foreign-a", name, "1", f"fa-{index}", "foreign"])
        lock_rows.append(["foreign-b", name, "1", f"fb-{index}", "foreign"])
        lock_rows.append(["foreign-c", name, "1", f"fc-{index}", "foreign"])
        lock_rows.append(["foreign-d", name, "1", f"fd-{index}", "foreign"])
    for index in range(250):
        lock_rows.extend(
            [
                ["lock-partition", f"ghost-partition-{index:02d}", "1", "old", "old"],
                ["lock-partition", f"ghost-partition-{index:02d}", "2", "final", "final"],
            ]
        )
    edge_rows: list[list[object]] = []
    for index in range(len(selected) - 1):
        edge_rows.append(
            [
                "lock-partition",
                selected[index],
                selected[index + 1],
                "requires",
                "runtime",
                "no",
            ]
        )
    for index in range(0, 300, 3):
        if index + 1 < len(names):
            edge_rows.append(
                ["*", names[index], names[index + 1], "optional", "runtime", "yes"]
            )
            edge_rows.append(
                ["foreign-a", names[index + 1], names[index], "foreign", "runtime", "no"]
            )
    audit, _raw, _out = run_custom_audit(
        release_dist,
        tmp_path,
        "lock-partition",
        "profile,channel,target,feature_set,max_runtime_kb,allow_dev,blocked_license\n"
        "lock-partition,stable,linux-x86_64,core,100,true,GPL\n",
        components,
        csv_bytes(
            ["profile", "component", "version", "checksum", "source"], lock_rows
        ).decode(),
        csv_bytes(
            ["profile", "parent", "child", "relation", "scope", "optional"],
            edge_rows,
        ).decode(),
    )
    assert [row["name"] for row in audit["components"]] == selected
    assert audit["warnings"] == sorted(
        f"missing_component:ghost-partition-{index:02d}" for index in range(250)
    )
    assert audit["totals"]["component_count"] == 100
    assert audit["totals"]["direct_lock_count"] == 100
    assert audit["totals"]["runtime_kb"] == 100
    assert audit["totals"]["edge_count"] == 99
    assert audit["totals"]["risk_score"] == 250 * 31 + 99 * 2
