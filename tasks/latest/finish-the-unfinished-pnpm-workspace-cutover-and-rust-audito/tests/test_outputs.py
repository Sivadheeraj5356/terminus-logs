"""Verifier for pnpmfix pnpm workspace override pin release task."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tarfile
from collections import defaultdict, deque
from contextlib import contextmanager
from pathlib import Path

import pytest
import tomllib

APP = Path("/app")
DIST = APP / "dist"
TESTS_ROOT = Path("/tests")
BASE_SRC = Path("/tests/baselines")
BASE = Path("/tmp/verifier-baselines")
EMPTY_TESTS = Path("/tmp/verifier-empty-tests")
PIN_DIGESTS = {
    "fmt": ("10.2.1", "16de8120e52729f6199371abe65cf9be293fd1461d73727bb187934db6e43313"),
    "zlib": ("1.3.1", "f5639a1dc21583311e433c27c086f6009700df2c60ef12a7362d830be5f63907"),
    "spdlog": ("1.13.0", "a6796ab08339bdb8a7b9be12d9baec92f38cb58434ea3f1ad3f1df991dfc0f4d"),
}


def ensure_baseline_cache() -> None:
    """Copy verifier baselines out of /tests so grading can hide the mount."""
    if BASE.exists():
        return
    if not BASE_SRC.exists():
        raise FileNotFoundError("missing /tests/baselines")
    shutil.copytree(BASE_SRC, BASE)


@contextmanager
def _hide_tests_by_moving_children():
    """Hide /tests contents via cross-device move when the mount is writable."""
    ensure_baseline_cache()
    stash = Path("/tmp/verifier-tests-stash")
    if stash.exists():
        shutil.rmtree(stash)
    stash.mkdir(parents=True)
    moved: list[tuple[Path, Path]] = []
    for child in sorted(TESTS_ROOT.iterdir()):
        if child.name.startswith(".") or child.name in {"__pycache__", ".pytest_cache"}:
            continue
        dest = stash / child.name
        shutil.move(str(child), str(dest))
        moved.append((child, dest))
    try:
        assert not (TESTS_ROOT / "baselines").exists()
        assert not (TESTS_ROOT / "test_outputs.py").exists()
        yield
    finally:
        for original, dest in moved:
            if dest.exists() and not original.exists():
                shutil.move(str(dest), str(original))
        if stash.exists():
            shutil.rmtree(stash, ignore_errors=True)


def _tests_mount_writable() -> bool:
    probe = TESTS_ROOT / ".verifier_write_probe"
    try:
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _agent_cmd(argv: list[str]) -> list[str] | None:
    """Prefer unshare+bind mount; return None to signal move-children fallback."""
    ensure_baseline_cache()
    EMPTY_TESTS.mkdir(parents=True, exist_ok=True)
    probe = subprocess.run(
        [
            "unshare",
            "--mount",
            "--",
            "bash",
            "-c",
            f"mount --bind {shlex.quote(str(EMPTY_TESTS))} /tests && "
            "test ! -e /tests/baselines && test ! -e /tests/test_outputs.py",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        return None
    inner = " ".join(shlex.quote(a) for a in argv)
    script = (
        f"mount --bind {shlex.quote(str(EMPTY_TESTS))} /tests && "
        f"test ! -e /tests/baselines && test ! -e /tests/test_outputs.py && "
        f"exec {inner}"
    )
    return ["unshare", "--mount", "--", "bash", "-c", script]


def _run_isolated(argv: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    """Run argv with /tests hidden from the agent process."""
    cmd = _agent_cmd(argv)
    if cmd is not None:
        return subprocess.run(cmd, **kwargs)
    if _tests_mount_writable():
        with _hide_tests_by_moving_children():
            return subprocess.run(argv, **kwargs)
    raise RuntimeError(
        "cannot isolate /tests (need unshare/mount CAP_SYS_ADMIN, or a writable /tests mount)"
    )


@contextmanager
def hide_tests():
    """Probe that agent-facing /tests hide works."""
    probe = _run_isolated(
        ["bash", "-c", "test ! -e /tests/baselines && test ! -e /tests/test_outputs.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        raise RuntimeError(f"/tests isolation probe failed: {probe.stderr!r}")
    yield


@pytest.fixture(scope="session")
def release_dist() -> Path:
    """Build the release package once (agent release.sh runs with /tests hidden)."""
    run_release()
    return DIST


def run_release(*, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CARGO_NET_OFFLINE"] = "true"
    env["SOURCE_DATE_EPOCH"] = "1700000000"
    return _run_isolated(
        ["bash", "/app/scripts/release.sh"],
        cwd=APP,
        env=env,
        check=check,
        timeout=360,
        text=True,
        capture_output=True,
    )


def run_agent(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Invoke agent-built binary with /tests unavailable."""
    return _run_isolated(
        args,
        check=check,
        timeout=120,
        text=True,
        capture_output=True,
    )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def matrix_rows() -> list[dict[str, str]]:
    """Lane list comes from verifier-owned baselines, not agent-writable /app matrix."""
    ensure_baseline_cache()
    with (BASE / "release_matrix.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_baseline_integrity() -> None:
    """Verifier fixtures under /tests/baselines cannot be vacated by the agent."""
    ensure_baseline_cache()
    mapping = {}
    for line in (BASE / "fixture.sha256").read_text(encoding="utf-8").splitlines():
        digest, rel = line.split("  ", 1)
        mapping[rel] = digest
        assert sha256(BASE / rel) == digest
    for rel in (
        "release_matrix.csv",
        "artifacts.csv",
        "edges.csv",
        "deps.expected.csv",
        "pins.csv",
        "xor.csv",
        "bans.csv",
        "mirrors.csv",
        "forbidden-hosts.csv",
    ):
        assert rel in mapping
    assert sha256(APP / "config" / "release_matrix.csv") == sha256(BASE / "release_matrix.csv")
    assert sha256(APP / "data" / "graphs" / "artifacts.csv") == sha256(BASE / "artifacts.csv")
    assert sha256(APP / "data" / "graphs" / "edges.csv") == sha256(BASE / "edges.csv")
    assert (APP / "config" / "deps.csv").read_text(encoding="utf-8") == (
        BASE / "deps.expected.csv"
    ).read_text(encoding="utf-8")


def strip_sha(s: str) -> str:
    s = s.strip()
    return s[7:] if s.startswith("sha256:") else s


def basename_of(url: str) -> str:
    return Path(url.rstrip("/")).name


def test_version(release_dist: Path) -> None:
    """Packaged binary prints exact pnpmfix 0.8.6."""
    lane = matrix_rows()[0]["lane"]
    binary = release_dist / "bundles" / f"pnpmfix-{lane}" / "bin" / "pnpmfix"
    out = run_agent([str(binary), "--version"])
    assert out.stdout.strip() == "pnpmfix 0.8.6"


def test_pnpm_layout(release_dist: Path) -> None:
    """Repaired override JSON pins, real archive digests, .npmrc, and pnpm-report schema."""
    _ = release_dist
    opts = (APP / ".npmrc").read_text(encoding="utf-8")
    assert re.search(r"(?m)^\s*offline\s*=\s*true\s*$", opts)
    assert re.search(r"(?m)^\s*store-dir\s*=\s*/app/pnpm-store\s*$", opts)
    assert (APP / "legacy-pnpm-notes.txt").read_text(encoding="utf-8").strip() == (
        "# emptied for pnpm"
    )
    for name, (verd, pin) in PIN_DIGESTS.items():
        data = json.loads((APP / "overrides" / "deps" / f"{name}.json").read_text(encoding="utf-8"))
        assert data["name"] == name
        assert data["provide"] == name
        assert data["version"] == verd
        assert data["resolved"] == f"file:///app/pnpm-store/{name}-{verd}.tgz"
        assert data["integrity"] == f"sha256:{pin}"
        blob = json.dumps(data)
        assert "https://" not in blob
        assert "registry.npmjs.org" not in blob
        archive = APP / "pnpm-store" / f"{name}-{verd}.tgz"
        assert archive.stat().st_size > 32
        assert sha256(archive) == pin
        with tarfile.open(archive, "r:gz") as tar:
            assert tar.getmembers()
        if name == "spdlog":
            assert data["provide"] == "spdlog"
    pkg = json.loads((APP / "package.json").read_text(encoding="utf-8"))
    for name, (verd, _) in PIN_DIGESTS.items():
        assert pkg["pnpm"]["overrides"][name] == f"file:///app/pnpm-store/{name}-{verd}.tgz"
    lock = (APP / "pnpm-lock.yaml").read_text(encoding="utf-8")
    for name, (verd, pin) in PIN_DIGESTS.items():
        assert f"file:///app/pnpm-store/{name}-{verd}.tgz" in lock
        assert f"sha256:{pin}" in lock
    assert "registry.npmjs.org" not in lock
    report = json.loads((DIST / "pnpm-report.json").read_text(encoding="utf-8"))
    assert report["format_version"] == 1
    assert report["legacy_cleared"] is True and report["offline_pnpm_mode"] is True
    assert isinstance(report["legacy_cleared"], bool) and isinstance(report["offline_pnpm_mode"], bool)
    assert set(report) == {
        "format_version",
        "deps",
        "legacy_cleared",
        "offline_pnpm_mode",
        "cargo_packages",
    }
    assert [d["name"] for d in report["deps"]] == sorted(d["name"] for d in report["deps"])
    expected_crates = []
    for path in sorted((APP / "crates").glob("*/Cargo.toml")):
        expected_crates.append(tomllib.loads(path.read_text(encoding="utf-8"))["package"]["name"])
    assert report["cargo_packages"] == expected_crates
    assert report["cargo_packages"] == [
        "pnpmfix-graph",
        "pnpmfix-cli",
        "pnpmfix-core",
        "pnpmfix-index",
    ]
    required = {"name", "provide", "version", "source_url", "source_hash", "mirror_ok"}
    by = {w["name"]: w for w in report["deps"]}
    for name, (verd, pin) in PIN_DIGESTS.items():
        row = by[name]
        assert set(row) == required
        assert row["mirror_ok"] is True and isinstance(row["mirror_ok"], bool)
        assert row["source_url"] == f"file:///app/pnpm-store/{name}-{verd}.tgz"
        # Serialized form must include sha256: prefix (comparison elsewhere may strip it).
        assert row["source_hash"] == f"sha256:{pin}"
        assert row["source_hash"].startswith("sha256:")
        assert row["version"] == verd
    assert by["spdlog"]["provide"] == "spdlog"


def test_offline_cargo(release_dist: Path) -> None:
    """Cargo remains offline."""
    _ = release_dist
    assert "offline = true" in (APP / ".cargo" / "config.toml").read_text(encoding="utf-8")


def test_bundles_manifest(release_dist: Path) -> None:
    """Each lane has share/ layout, archive at dist root, and typed manifest digests."""
    manifest = json.loads((release_dist / "release-manifest.json").read_text(encoding="utf-8"))
    assert set(manifest) == {"format_version", "package", "workspace", "fetch", "bundles"}
    assert manifest["format_version"] == 1
    assert manifest["package"] == {
        "name": "pnpmfix-cli",
        "version": "0.8.6",
        "target": "x86_64-unknown-linux-gnu",
    }
    assert manifest["fetch"] == json.loads((release_dist / "pnpm-report.json").read_text(encoding="utf-8"))
    assert [b["lane"] for b in manifest["bundles"]] == [r["lane"] for r in matrix_rows()]
    for row, entry in zip(matrix_rows(), manifest["bundles"], strict=True):
        lane = row["lane"]
        bundle = release_dist / "bundles" / f"pnpmfix-{lane}"
        archive = release_dist / f"pnpmfix-{lane}-linux-x86_64.tar.gz"
        assert bundle.is_dir()
        assert archive.is_file()
        assert not (release_dist / "tarballs").exists()
        for rel in [
            "bin/pnpmfix",
            "VERSION",
            "LICENSES.txt",
            "share/lane-policy.json",
            "share/edges.csv",
            "share/artifacts.csv",
            "share/deps.csv",
            "share/xor.csv",
            "share/mirrors.csv",
            "share/pins.csv",
            "share/bans.csv",
            "share/forbidden-hosts.csv",
            "share/run-smoke.sh",
            "share/inspect-preview.json",
        ]:
            assert (bundle / rel).exists(), rel
        assert not (bundle / "inspect-preview.json").exists()
        assert not (bundle / "run-smoke.sh").exists()
        assert (bundle / "VERSION").read_text(encoding="utf-8") == "pnpmfix 0.8.6\n"
        lic_text = (bundle / "LICENSES.txt").read_text(encoding="utf-8")
        expected_lic = "".join(
            p.read_text(encoding="utf-8") + "\n"
            for p in sorted((APP / "licenses").iterdir())
            if p.is_file()
        )
        assert lic_text == expected_lic
        assert "\n\n" in lic_text
        assert "Apache License" in lic_text and "Version 2.0" in lic_text
        assert "MIT License" in lic_text and "Permission is hereby granted" in lic_text
        smoke = (bundle / "share" / "run-smoke.sh").read_text(encoding="utf-8")
        assert "--forbidden-hosts" in smoke
        assert re.search(r"--forbidden-hosts\s+\S+", smoke)
        assert "--lane" in smoke
        assert re.search(r"(?m)^OUT=\$\{1:-", smoke), "run-smoke.sh must use unquoted OUT=${1:-…}"
        assert 'OUT="${1' not in smoke
        assert '--out "$OUT"' in smoke
        assert "--edges" in smoke
        preview = json.loads((bundle / "share" / "inspect-preview.json").read_text(encoding="utf-8"))
        assert set(preview) == {"lane", "retention_hops", "artifacts", "totals"}
        for art in preview["artifacts"]:
            assert set(art) == {"coordinate", "status", "holds", "risk_score"}
            assert isinstance(art["holds"], list)
            assert all(isinstance(h, str) for h in art["holds"]), art["holds"]
        coords = [a["coordinate"] for a in preview["artifacts"]]
        assert coords == sorted(coords)
        held = sum(1 for a in preview["artifacts"] if a["status"] == "hold")
        hold_strings = sum(len(a["holds"]) for a in preview["artifacts"])
        assert entry["archive"] == f"pnpmfix-{lane}-linux-x86_64.tar.gz"
        assert entry["archive_sha256"] == sha256(archive)
        assert entry["binary_sha256"] == sha256(bundle / "bin" / "pnpmfix")
        assert entry["policy_sha256"] == sha256(bundle / "share" / "lane-policy.json")
        assert entry["inspect_preview_sha256"] == sha256(bundle / "share" / "inspect-preview.json")
        assert entry["artifact_count"] == len(preview["artifacts"])
        assert entry["hold_count"] == preview["totals"]["hold"] == held
        if hold_strings != held:
            assert entry["hold_count"] != hold_strings
        assert entry["risk_score_total"] == preview["totals"]["risk_score_total"]
        assert "versiondrifts" in preview["totals"]
        with (bundle / "share" / "deps.csv").open(encoding="utf-8") as handle:
            for drow in csv.DictReader(handle):
                if drow["coordinate"] in {"dep:fmt", "dep:zlib", "dep:spdlog"}:
                    assert not (drow.get("patch_url") or "").strip()
                    assert drow["source_url"].startswith("file:///app/pnpm-store/")


def test_workspace(release_dist: Path) -> None:
    """Manifest workspace matches crates in sorted(crates/*/Cargo.toml) path order."""
    manifest = json.loads((release_dist / "release-manifest.json").read_text(encoding="utf-8"))
    root = tomllib.loads((APP / "Cargo.toml").read_text(encoding="utf-8"))
    wlicense = root["workspace"]["package"]["license"]
    wversion = root["workspace"]["package"]["version"]
    assert wversion == "0.8.6"
    expected = []
    crate_paths = sorted((APP / "crates").glob("*/Cargo.toml"))
    # Directory basename may differ from package name (aa-graph → pnpmfix-graph).
    assert [p.parent.name for p in crate_paths] == [
        "aa-graph",
        "pnpmfix-cli",
        "pnpmfix-core",
        "zz-index",
    ]
    for path in crate_paths:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        pkg = data["package"]
        lic = pkg.get("license", wlicense)
        ver = pkg.get("version", wversion)
        if isinstance(lic, dict) and lic.get("workspace"):
            lic = wlicense
        if isinstance(ver, dict) and ver.get("workspace"):
            ver = wversion
        expected.append(
            {
                "name": pkg["name"],
                "version": ver,
                "license": lic,
                "dependencies": sorted((data.get("dependencies") or {}).keys()),
            }
        )
    assert [e["name"] for e in expected] == [
        "pnpmfix-graph",
        "pnpmfix-cli",
        "pnpmfix-core",
        "pnpmfix-index",
    ]
    by_name = sorted(expected, key=lambda e: e["name"])
    assert [e["name"] for e in expected] != [e["name"] for e in by_name]
    assert [e["name"] for e in manifest["workspace"]] == [e["name"] for e in expected]
    assert manifest["workspace"] == expected


def test_checksums(release_dist: Path) -> None:
    """checksums.sha256 covers every dist file except itself with two-space format."""
    mapping = {}
    for line in (release_dist / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        digest, rel = line.split("  ", 1)
        mapping[rel] = digest
    expected = []
    for path in release_dist.rglob("*"):
        if path.is_file() and path.name != "checksums.sha256":
            rel = str(path.relative_to(release_dist)).replace("\\", "/")
            expected.append(rel)
            assert mapping[rel] == sha256(path)
    assert list(mapping) == sorted(expected)


def test_archive_reproducible(release_dist: Path) -> None:
    """Archives keep pnpmfix-<lane> root and stable digests across reruns."""
    lane = matrix_rows()[0]["lane"]
    archive = release_dist / f"pnpmfix-{lane}-linux-x86_64.tar.gz"
    first = sha256(archive)
    with tarfile.open(archive, "r:gz") as tar:
        names = tar.getnames()
    assert any(n == f"pnpmfix-{lane}" or n.startswith(f"pnpmfix-{lane}/") for n in names)
    run_release()
    assert first == sha256(DIST / f"pnpmfix-{lane}-linux-x86_64.tar.gz")


def expected_inspect(lane: str, retention_hops: int, data_dir: Path | None = None) -> dict:
    """Reference inspector over a CSV directory (defaults to verifier baseline cache)."""
    ensure_baseline_cache()
    root = data_dir if data_dir is not None else BASE

    def csv_path(name: str) -> Path:
        path = root / name
        if name == "deps.csv" and not path.exists():
            alt = root / "deps.expected.csv"
            if alt.exists():
                return alt
        return path

    edges = [
        r for r in csv.DictReader(csv_path("edges.csv").open(encoding="utf-8")) if r["lane"] == lane
    ]
    artifacts = [
        r["coordinate"]
        for r in csv.DictReader(csv_path("artifacts.csv").open(encoding="utf-8"))
        if r["lane"] == lane
    ]
    deps = [
        r for r in csv.DictReader(csv_path("deps.csv").open(encoding="utf-8")) if r["lane"] == lane
    ]
    mirrors = {r["basename"] for r in csv.DictReader(csv_path("mirrors.csv").open(encoding="utf-8"))}
    pins = {
        f"dep:{r['wrap']}": r for r in csv.DictReader(csv_path("pins.csv").open(encoding="utf-8"))
    }
    xor_rows = [
        r for r in csv.DictReader(csv_path("xor.csv").open(encoding="utf-8")) if r["lane"] == lane
    ]
    bans = {r["coordinate"] for r in csv.DictReader(csv_path("bans.csv").open(encoding="utf-8"))}
    forbidden = [
        r["host"] for r in csv.DictReader(csv_path("forbidden-hosts.csv").open(encoding="utf-8"))
    ]

    art_set = set(artifacts)
    holds: dict[str, dict[str, int]] = {a: {} for a in artifacts}

    def add(coord: str, reason: str, risk: int) -> None:
        if coord not in holds:
            return
        holds[coord][reason] = max(holds[coord].get(reason, 0), risk)

    for w in deps:
        if w["coordinate"] not in art_set:
            continue
        src = w["source_url"]
        remote_src = (not src.startswith("file:///")) or any(h in src for h in forbidden)
        if remote_src:
            add(w["coordinate"], f"remote:{w['coordinate']}:source", 47)
        patch = w.get("patch_url") or ""
        if patch:
            remote_p = (not patch.startswith("file:///")) or any(h in patch for h in forbidden)
            if remote_p:
                add(w["coordinate"], f"remote:{w['coordinate']}:patch", 47)
        pin = pins.get(w["coordinate"])
        if pin is None:
            add(w["coordinate"], f"missingpin:{w['coordinate']}", 38)
        else:
            exp = strip_sha(pin["sha256"])
            act = strip_sha(w["source_hash"])
            if exp != act:
                add(w["coordinate"], f"hashdrift:{w['coordinate']}:{exp}:{act}", 43)
            if pin["version"] != w["version"]:
                add(
                    w["coordinate"],
                    f"versiondrift:{w['coordinate']}:{pin['version']}:{w['version']}",
                    36,
                )
        base = basename_of(src)
        if base and base not in mirrors:
            add(w["coordinate"], f"mirrormiss:{w['coordinate']}:{base}", 40)

    by_provide: dict[str, set[str]] = defaultdict(set)
    for w in deps:
        if w["coordinate"] in art_set:
            by_provide[w["provide"]].add(w["coordinate"])
    for provide, coords in by_provide.items():
        if len(coords) < 2:
            continue
        joined = "|".join(sorted(coords))
        hold = f"provcollide:{provide}:{joined}"
        for c in coords:
            add(c, hold, 45)

    provide_to_dep = {w["provide"]: w["coordinate"] for w in deps if w["coordinate"] in art_set}
    by_group: dict[str, set[str]] = defaultdict(set)
    for row in xor_rows:
        if row["provide"] in provide_to_dep:
            by_group[row["group"]].add(row["provide"])
    for group, provides in by_group.items():
        if len(provides) < 2:
            continue
        joined = "|".join(sorted(provides))
        hold = f"xor:{group}:{joined}"
        for p in provides:
            add(provide_to_dep[p], hold, 52)

    for a in artifacts:
        if a in bans:
            add(a, f"ban:{a}", 55)

    origin_holds: dict[str, list[tuple[str, int]]] = {}
    for coord, hmap in holds.items():
        for reason, risk in hmap.items():
            if (
                reason.startswith("ban:")
                or reason.startswith("remote:")
                or reason.startswith("xor:")
                or reason.startswith("provcollide:")
            ):
                origin_holds.setdefault(coord, []).append((reason, risk))
    rev: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        if e["edge_kind"] == "hard":
            rev[e["child"]].append(e["parent"])
    for parents in rev.values():
        parents.sort()

    # target -> origin -> (dist, via)
    best_routes: dict[str, dict[str, tuple[int, str]]] = defaultdict(dict)
    for origin in origin_holds:
        best: dict[str, tuple[int, str]] = {origin: (0, "")}
        q = deque([origin])
        while q:
            node = q.popleft()
            dist, via = best[node]
            if dist >= retention_hops:
                continue
            for parent in rev.get(node, []):
                nd = dist + 1
                if dist == 0:
                    nvia = "-"
                elif via == "-":
                    nvia = node
                else:
                    nvia = f"{via}/{node}"
                cand = (nd, nvia)
                prev = best.get(parent)
                if prev is None or cand < prev:
                    best[parent] = cand
                    if parent != origin:
                        best_routes[parent][origin] = cand
                    q.append(parent)

    for parent, origin_map in best_routes.items():
        for origin, (nd, nvia) in origin_map.items():
            for reason, risk in origin_holds[origin]:
                attenuated = max(1, risk - 13 * nd)
                add(parent, f"cascade:{nd}:{origin}@{nvia}:{reason}", attenuated)

    reports = []
    totals = {
        "release": 0,
        "hold": 0,
        "remotes": 0,
        "hashdrifts": 0,
        "versiondrifts": 0,
        "mirrormisses": 0,
        "provcollides": 0,
        "xors": 0,
        "missingpins": 0,
        "bans": 0,
        "cascades": 0,
        "risk_score_total": 0,
    }
    for coord in sorted(artifacts):
        hmap = holds.get(coord, {})
        hold_list = sorted(hmap)
        score = sum(hmap[h] for h in hold_list)
        for h in hold_list:
            if h.startswith("remote:"):
                totals["remotes"] += 1
            elif h.startswith("hashdrift:"):
                totals["hashdrifts"] += 1
            elif h.startswith("versiondrift:"):
                totals["versiondrifts"] += 1
            elif h.startswith("mirrormiss:"):
                totals["mirrormisses"] += 1
            elif h.startswith("provcollide:"):
                totals["provcollides"] += 1
            elif h.startswith("xor:"):
                totals["xors"] += 1
            elif h.startswith("missingpin:"):
                totals["missingpins"] += 1
            elif h.startswith("ban:"):
                totals["bans"] += 1
            elif h.startswith("cascade:"):
                totals["cascades"] += 1
        status = "release" if not hold_list else "hold"
        totals[status] += 1
        totals["risk_score_total"] += score
        reports.append(
            {"coordinate": coord, "status": status, "holds": hold_list, "risk_score": score}
        )
    return {
        "lane": lane,
        "retention_hops": retention_hops,
        "artifacts": reports,
        "totals": totals,
    }


@pytest.mark.parametrize("row", matrix_rows(), ids=lambda r: r["lane"])
def test_inspect_preview(release_dist: Path, row: dict[str, str], tmp_path: Path) -> None:
    """Packaged preview and a fresh run-smoke.sh inspect both match expected_inspect."""
    lane = row["lane"]
    bundle = release_dist / "bundles" / f"pnpmfix-{lane}"
    preview = json.loads((bundle / "share" / "inspect-preview.json").read_text(encoding="utf-8"))
    assert set(preview) == {"lane", "retention_hops", "artifacts", "totals"}
    assert preview["lane"] == lane
    for art in preview["artifacts"]:
        assert set(art) == {"coordinate", "status", "holds", "risk_score"}
        assert all(isinstance(h, str) for h in art["holds"])
    coords = [a["coordinate"] for a in preview["artifacts"]]
    assert coords == sorted(coords)
    expected = expected_inspect(lane, int(row["retention_hops"]))
    assert preview == expected

    smoke = bundle / "share" / "run-smoke.sh"
    assert smoke.is_file() and os.access(smoke, os.X_OK)
    fresh = tmp_path / f"inspect-{lane}.json"
    proc = subprocess.run(
        [str(smoke), str(fresh)],
        cwd=bundle,
        check=False,
        timeout=60,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr
    live = json.loads(fresh.read_text(encoding="utf-8"))
    assert live == expected
    assert live == preview

    if lane == "gate":
        xor_on_artifacts = sum(
            1 for a in preview["artifacts"] for h in a["holds"] if h.startswith("xor:")
        )
        collide_on_artifacts = sum(
            1 for a in preview["artifacts"] for h in a["holds"] if h.startswith("provcollide:")
        )
        assert preview["totals"]["xors"] == xor_on_artifacts
        assert preview["totals"]["xors"] >= 2
        assert preview["totals"]["provcollides"] == collide_on_artifacts
        if collide_on_artifacts:
            assert preview["totals"]["provcollides"] >= 2
        by = {a["coordinate"]: a for a in preview["artifacts"]}
        assert "cascade:1:dep:jsonA@-:xor:json-codec:json|jsonalt" in by["relay:a"]["holds"]
        assert "cascade:1:dep:jsonA@-:xor:json-codec:json|jsonalt" in by["relay:b"]["holds"]
        assert "cascade:2:dep:jsonA@relay:a:xor:json-codec:json|jsonalt" in by["gw:edge"]["holds"]
        assert "cascade:2:dep:jsonA@relay:b:xor:json-codec:json|jsonalt" not in by["gw:edge"]["holds"]
        assert "cascade:1:dep:jsonB@-:xor:json-codec:json|jsonalt" in by["gw:edge"]["holds"]

    if lane == "edge":
        by = {a["coordinate"]: a for a in preview["artifacts"]}
        assert set(by) >= {
            "svc:app",
            "mid:left",
            "mid:right",
            "spine:a",
            "spine:b",
            "spine:c",
            "dep:legacy",
            "trace:soft",
        }
        assert "cascade:1:dep:legacy@-:ban:dep:legacy" in by["mid:left"]["holds"]
        assert "cascade:1:dep:legacy@-:ban:dep:legacy" in by["mid:right"]["holds"]
        assert "cascade:1:dep:legacy@-:ban:dep:legacy" in by["spine:a"]["holds"]
        assert "cascade:2:dep:legacy@spine:a:ban:dep:legacy" in by["spine:b"]["holds"]
        assert "cascade:3:dep:legacy@spine:a/spine:b:ban:dep:legacy" in by["spine:c"]["holds"]
        assert "cascade:2:dep:legacy@mid:left:ban:dep:legacy" in by["svc:app"]["holds"]
        assert "cascade:2:dep:legacy@mid:right:ban:dep:legacy" not in by["svc:app"]["holds"]
        assert "cascade:3:dep:legacy@spine:a/spine:b:ban:dep:legacy" not in by["svc:app"]["holds"]
        assert "cascade:4:dep:legacy@spine:a/spine:b/spine:c:ban:dep:legacy" not in by["svc:app"]["holds"]
        assert not any(h.startswith("cascade:") for h in by["trace:soft"]["holds"])
        ban_cascade_risks = {}
        for art in preview["artifacts"]:
            for h in art["holds"]:
                if h.startswith("cascade:") and h.endswith(":ban:dep:legacy"):
                    d = int(h.split(":", 2)[1])
                    ban_cascade_risks[art["coordinate"]] = max(1, 55 - 13 * d)
        assert ban_cascade_risks["mid:left"] == 42
        assert ban_cascade_risks["spine:b"] == 29
        assert ban_cascade_risks["spine:c"] == 16
        assert ban_cascade_risks["svc:app"] == 29

    if lane == "core":
        by = {a["coordinate"]: a for a in preview["artifacts"]}
        assert "api:core" in by
        assert by["api:core"]["status"] in {"hold", "release"}


def test_soft_edges_ignored(release_dist: Path) -> None:
    """Soft edges do not cascade holds onto trace:soft."""
    preview = json.loads(
        (release_dist / "bundles" / "pnpmfix-edge" / "share" / "inspect-preview.json").read_text(
            encoding="utf-8"
        )
    )
    by = {a["coordinate"]: a for a in preview["artifacts"]}
    assert not any(h.startswith("cascade:") for h in by["trace:soft"]["holds"])


def test_no_remote_after_repair(release_dist: Path) -> None:
    """Repaired deps.csv clears source and patch remotes for fmt/zlib/spdlog (empty patch_url)."""
    _ = release_dist
    with (APP / "config" / "deps.csv").open(encoding="utf-8") as handle:
        for drow in csv.DictReader(handle):
            if drow["coordinate"] in {"dep:fmt", "dep:zlib", "dep:spdlog"}:
                assert drow["source_url"].startswith("file:///app/pnpm-store/")
                assert not (drow.get("patch_url") or "").strip(), (
                    f"{drow['lane']}:{drow['coordinate']} must clear patch_url"
                )
    for row in matrix_rows():
        preview = json.loads(
            (
                release_dist / "bundles" / f"pnpmfix-{row['lane']}" / "share" / "inspect-preview.json"
            ).read_text(encoding="utf-8")
        )
        by = {a["coordinate"]: a for a in preview["artifacts"]}
        for coord in ("dep:fmt", "dep:zlib", "dep:spdlog"):
            if coord in by:
                assert not any(h.startswith("remote:") for h in by[coord]["holds"])
                assert not any(h.startswith("hashdrift:") for h in by[coord]["holds"])


def test_lab_hop_zero_version_hash_drift(release_dist: Path) -> None:
    """lab hop=0 keeps poison drifts local; no cascade to mid:hop or svc:lab."""
    preview = json.loads(
        (release_dist / "bundles" / "pnpmfix-lab" / "share" / "inspect-preview.json").read_text(
            encoding="utf-8"
        )
    )
    by = {a["coordinate"]: a for a in preview["artifacts"]}
    assert any(h.startswith("hashdrift:dep:poison:") for h in by["dep:poison"]["holds"])
    assert "versiondrift:dep:poison:0.1.0:0.2.0" in by["dep:poison"]["holds"]
    assert not any("dep:poison" in h and h.startswith("cascade:") for h in by["mid:hop"]["holds"])
    assert not any("dep:poison" in h and h.startswith("cascade:") for h in by["svc:lab"]["holds"])


def test_decoy_nightly_not_packaged(release_dist: Path) -> None:
    """Decoy nightly lane JSON must not produce a release bundle."""
    assert not (release_dist / "bundles" / "pnpmfix-nightly").exists()
    assert not (release_dist / "pnpmfix-nightly-linux-x86_64.tar.gz").exists()


def test_no_unpacked_at_root(release_dist: Path) -> None:
    """Unpacked bundles live only under dist/bundles."""
    for path in release_dist.iterdir():
        if path.is_dir():
            assert path.name == "bundles"


def test_offline_pnpm_workspace(release_dist: Path) -> None:
    """Offline pnpm workspace pins agree across overrides, package.json, and lockfile."""
    _ = release_dist
    npmrc = (APP / ".npmrc").read_text(encoding="utf-8")
    assert re.search(r"(?m)^\s*offline\s*=\s*true\s*$", npmrc)
    assert re.search(r"(?m)^\s*store-dir\s*=\s*/app/pnpm-store\s*$", npmrc)
    pkg = json.loads((APP / "package.json").read_text(encoding="utf-8"))
    lock = (APP / "pnpm-lock.yaml").read_text(encoding="utf-8")
    for name, (verd, pin) in PIN_DIGESTS.items():
        data = json.loads((APP / "overrides" / "deps" / f"{name}.json").read_text(encoding="utf-8"))
        assert data["resolved"] == f"file:///app/pnpm-store/{name}-{verd}.tgz"
        assert data["integrity"] == f"sha256:{pin}"
        assert pkg["pnpm"]["overrides"][name] == data["resolved"]
        assert data["resolved"] in lock
        assert f"sha256:{pin}" in lock
        archive = APP / "pnpm-store" / f"{name}-{verd}.tgz"
        assert sha256(archive) == pin
        with tarfile.open(archive, "r:gz") as tar:
            assert tar.getmembers()
    release = (APP / "scripts" / "release.sh").read_text(encoding="utf-8")
    # Graders read release.sh text directly — helpers alone do not satisfy this.
    assert "overrides" in release or "overrides/deps" in release
    assert ".npmrc" in release
    assert "cmake" not in release
    assert "pnpm install" not in release
    assert "npm install" not in release



def test_fail_closed_validation(release_dist: Path) -> None:
    """release.sh exits non-zero on pin digest mismatch and does not rewrite the pin."""
    _ = release_dist
    pin = APP / "overrides" / "deps" / "fmt.json"
    original = pin.read_text(encoding="utf-8")
    broken = original.replace(PIN_DIGESTS["fmt"][1], "0" * 64)
    assert broken != original
    try:
        pin.write_text(broken, encoding="utf-8")
        proc = run_release(check=False)
        assert proc.returncode != 0
        assert pin.read_text(encoding="utf-8") == broken
    finally:
        pin.write_text(original, encoding="utf-8")


def test_fail_closed_patch_url(release_dist: Path) -> None:
    """release.sh fails closed if a repaired dep still has a non-empty patch_url."""
    _ = release_dist
    deps = APP / "config" / "deps.csv"
    original = deps.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    rewritten = []
    for line in lines:
        if line.startswith("edge,dep:fmt,"):
            parts = line.rstrip("\n").rstrip("\r").split(",")
            parts[-1] = "https://evil.example/fmt.patch"
            line = ",".join(parts) + "\n"
        rewritten.append(line)
    broken = "".join(rewritten)
    assert broken != original
    try:
        deps.write_text(broken, encoding="utf-8")
        proc = run_release(check=False)
        assert proc.returncode != 0
        assert deps.read_text(encoding="utf-8") == broken
    finally:
        deps.write_text(original, encoding="utf-8")


def test_fail_closed_offline_npmrc(release_dist: Path) -> None:
    """release.sh rejects a corrupted .npmrc and does not repair it."""
    _ = release_dist
    path = APP / ".npmrc"
    original = path.read_text(encoding="utf-8")
    broken = "offline=false\nstore-dir=/tmp/wrong-store\n"
    assert not re.search(r"(?m)^\s*offline\s*=\s*true\s*$", broken)
    try:
        path.write_text(broken, encoding="utf-8")
        proc = run_release(check=False)
        assert proc.returncode != 0
        assert path.read_text(encoding="utf-8") == broken
    finally:
        path.write_text(original, encoding="utf-8")



def test_fail_closed_legacy_notes(release_dist: Path) -> None:
    """release.sh rejects legacy notes that are not emptied and does not rewrite them."""
    _ = release_dist
    path = APP / "legacy-pnpm-notes.txt"
    original = path.read_text(encoding="utf-8")
    broken = "still pointing at github fetch\n"
    try:
        path.write_text(broken, encoding="utf-8")
        proc = run_release(check=False)
        assert proc.returncode != 0
        assert path.read_text(encoding="utf-8") == broken
    finally:
        path.write_text(original, encoding="utf-8")


def test_fail_closed_archive_digest(release_dist: Path) -> None:
    """release.sh rejects a corrupted pnpm-store archive whose bytes no longer match URL_HASH."""
    _ = release_dist
    archive = APP / "pnpm-store" / "zlib-1.3.1.tgz"
    original = archive.read_bytes()
    try:
        archive.write_bytes(original + b"\x00corrupt")
        proc = run_release(check=False)
        assert proc.returncode != 0
        assert archive.read_bytes() == original + b"\x00corrupt"
    finally:
        archive.write_bytes(original)


def test_release_sh_isolated_from_tests(release_dist: Path) -> None:
    """Agent release.sh must not consult /tests; comments mentioning /tests are allowed."""
    _ = release_dist
    text = (APP / "scripts" / "release.sh").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    assert "fixture.sha256" not in code
    assert "/tests/baselines" not in code
    assert re.search(r"(?m)^\s*(cp|cat|source|\.|python3?|rsync)\b.*(/tests/)", text) is None


def test_agent_runtime_cannot_see_tests(release_dist: Path) -> None:
    """Agent release/binary run in a mount namespace where /tests baselines are absent."""
    _ = release_dist
    ensure_baseline_cache()
    with hide_tests():
        pass
    # Parent still has baselines for the verifier.
    assert (BASE / "deps.expected.csv").is_file()
    # Direct probe inside the same isolation wrapper.
    probe = run_agent(["bash", "-c", "test ! -e /tests/baselines && test ! -e /tests/test_outputs.py"])
    assert probe.returncode == 0


def _stage_inspect_inputs(dest: Path) -> None:
    ensure_baseline_cache()
    dest.mkdir(parents=True, exist_ok=True)
    mapping = {
        "edges.csv": "edges.csv",
        "artifacts.csv": "artifacts.csv",
        "deps.csv": "deps.expected.csv",
        "mirrors.csv": "mirrors.csv",
        "pins.csv": "pins.csv",
        "xor.csv": "xor.csv",
        "bans.csv": "bans.csv",
        "forbidden-hosts.csv": "forbidden-hosts.csv",
    }
    for dest_name, src_name in mapping.items():
        shutil.copyfile(BASE / src_name, dest / dest_name)


def test_inspect_direct_on_mutated_csvs(release_dist: Path, tmp_path: Path) -> None:
    """pnpmfix inspect must evaluate verifier-generated CSV mutations, not only matrix previews."""
    binary_src = release_dist / "bundles" / "pnpmfix-edge" / "bin" / "pnpmfix"
    assert binary_src.is_file(), f"missing packaged binary: {binary_src}"
    binary = tmp_path / "pnpmfix-edge-bin"
    shutil.copy2(binary_src, binary)
    binary.chmod(0o755)
    work = tmp_path / "mutated-edge"
    _stage_inspect_inputs(work)

    # Mutation 1: corrupt fmt source_hash (prefixed) → hashdrift with stripped hex in hold.
    deps_path = work / "deps.csv"
    rows = list(csv.DictReader(deps_path.open(encoding="utf-8")))
    fieldnames = list(rows[0].keys())
    for row in rows:
        if row["lane"] == "edge" and row["coordinate"] == "dep:fmt":
            row["source_hash"] = "sha256:" + ("a" * 64)
        # Mutation 2: bare-hex matching pin for zlib must NOT hashdrift (prefix-optional compare).
        if row["lane"] == "edge" and row["coordinate"] == "dep:zlib":
            row["source_hash"] = PIN_DIGESTS["zlib"][1]  # bare hex, no sha256:
        # Mutation 3: remote source on legacy.
        if row["lane"] == "edge" and row["coordinate"] == "dep:legacy":
            row["source_url"] = "https://evil.example/legacy.tgz"
    with deps_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    out = tmp_path / "mutated-preview.json"
    hops = 3
    run_agent(
        [
            str(binary),
            "inspect",
            "--lane",
            "edge",
            "--edges",
            str(work / "edges.csv"),
            "--artifacts",
            str(work / "artifacts.csv"),
            "--deps",
            str(work / "deps.csv"),
            "--mirrors",
            str(work / "mirrors.csv"),
            "--pins",
            str(work / "pins.csv"),
            "--xor",
            str(work / "xor.csv"),
            "--bans",
            str(work / "bans.csv"),
            "--forbidden-hosts",
            str(work / "forbidden-hosts.csv"),
            "--retention-hops",
            str(hops),
            "--out",
            str(out),
        ]
    )
    got = json.loads(out.read_text(encoding="utf-8"))
    assert got["lane"] == "edge", " --lane must populate output lane even for temp CSV paths"
    assert set(got) == {"lane", "retention_hops", "artifacts", "totals"}
    expected = expected_inspect("edge", hops, data_dir=work)
    assert got == expected
    by = {a["coordinate"]: a for a in got["artifacts"]}
    bad = "a" * 64
    good = PIN_DIGESTS["fmt"][1]
    assert f"hashdrift:dep:fmt:{good}:{bad}" in by["dep:fmt"]["holds"]
    assert not any(h.startswith("hashdrift:dep:zlib:") for h in by["dep:zlib"]["holds"])
    assert "remote:dep:legacy:source" in by["dep:legacy"]["holds"]


def test_inspect_direct_gate_xor_mutation(release_dist: Path, tmp_path: Path) -> None:
    """Mutated gate inputs still produce per-artifact xor totals via direct inspect."""
    binary_src = release_dist / "bundles" / "pnpmfix-gate" / "bin" / "pnpmfix"
    assert binary_src.is_file(), f"missing packaged binary: {binary_src}"
    binary = tmp_path / "pnpmfix-gate-bin"
    shutil.copy2(binary_src, binary)
    binary.chmod(0o755)
    work = tmp_path / "mutated-gate"
    _stage_inspect_inputs(work)
    # Force an extra ban on dep:jsonA to ensure cascade/hold logic is live.
    bans = work / "bans.csv"
    with bans.open("a", encoding="utf-8") as handle:
        handle.write("dep:jsonA\n")
    out = tmp_path / "gate-preview.json"
    hops = 3
    run_agent(
        [
            str(binary),
            "inspect",
            "--lane",
            "gate",
            "--edges",
            str(work / "edges.csv"),
            "--artifacts",
            str(work / "artifacts.csv"),
            "--deps",
            str(work / "deps.csv"),
            "--mirrors",
            str(work / "mirrors.csv"),
            "--pins",
            str(work / "pins.csv"),
            "--xor",
            str(work / "xor.csv"),
            "--bans",
            str(work / "bans.csv"),
            "--forbidden-hosts",
            str(work / "forbidden-hosts.csv"),
            "--retention-hops",
            str(hops),
            "--out",
            str(out),
        ]
    )
    got = json.loads(out.read_text(encoding="utf-8"))
    assert got["lane"] == "gate"
    expected = expected_inspect("gate", hops, data_dir=work)
    assert got == expected
    by = {a["coordinate"]: a for a in got["artifacts"]}
    assert "ban:dep:jsonA" in by["dep:jsonA"]["holds"]
    xor_on_artifacts = sum(1 for a in got["artifacts"] for h in a["holds"] if h.startswith("xor:"))
    collide_on_artifacts = sum(
        1 for a in got["artifacts"] for h in a["holds"] if h.startswith("provcollide:")
    )
    assert got["totals"]["xors"] == xor_on_artifacts
    assert got["totals"]["xors"] >= 2
    assert got["totals"]["provcollides"] == collide_on_artifacts
    if collide_on_artifacts:
        assert got["totals"]["provcollides"] >= 2


def test_release_manifest_schema_exact(release_dist: Path) -> None:
    """release-manifest.json top-level keys are exactly format_version/package/workspace/fetch/bundles."""
    manifest = json.loads((release_dist / "release-manifest.json").read_text(encoding="utf-8"))
    assert set(manifest) == {"format_version", "package", "workspace", "fetch", "bundles"}
    assert "cargo_packages" not in manifest
    assert "lanes" not in manifest
    assert "version" not in manifest
    assert manifest["fetch"] == json.loads((release_dist / "pnpm-report.json").read_text(encoding="utf-8"))
    assert [b["lane"] for b in manifest["bundles"]] == [r["lane"] for r in matrix_rows()]


def test_inspect_schema_excludes_format_version(release_dist: Path) -> None:
    """Inspect preview must not carry format_version."""
    for row in matrix_rows():
        preview = json.loads(
            (
                release_dist
                / "bundles"
                / f"pnpmfix-{row['lane']}"
                / "share"
                / "inspect-preview.json"
            ).read_text(encoding="utf-8")
        )
        assert "format_version" not in preview
        assert set(preview) == {"lane", "retention_hops", "artifacts", "totals"}


def test_run_smoke_out_assignment(release_dist: Path, tmp_path: Path) -> None:
    """run-smoke.sh uses unquoted OUT=${1:-…} and writes caller outfile."""
    lane = matrix_rows()[0]["lane"]
    bundle = release_dist / "bundles" / f"pnpmfix-{lane}"
    smoke_txt = (bundle / "share" / "run-smoke.sh").read_text(encoding="utf-8")
    assert re.search(r"(?m)^OUT=\$\{1:-", smoke_txt)
    assert 'OUT="${1' not in smoke_txt
    assert '--out "$OUT"' in smoke_txt
    assert "--edges" in smoke_txt
    fresh = tmp_path / "out.json"
    proc = subprocess.run(
        [str(bundle / "share" / "run-smoke.sh"), str(fresh)],
        cwd=bundle,
        check=False,
        timeout=60,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr
    got = json.loads(fresh.read_text(encoding="utf-8"))
    assert set(got) == {"lane", "retention_hops", "artifacts", "totals"}


def test_edge_retention_hops_is_three(release_dist: Path) -> None:
    """Edge lane retention_hops is 3 so spine:c hop-3 routes are active."""
    policy = json.loads(
        (release_dist / "bundles" / "pnpmfix-edge" / "share" / "lane-policy.json").read_text(
            encoding="utf-8"
        )
    )
    assert policy["retention_hops"] == 3
    preview = json.loads(
        (release_dist / "bundles" / "pnpmfix-edge" / "share" / "inspect-preview.json").read_text(
            encoding="utf-8"
        )
    )
    assert preview["retention_hops"] == 3
    by = {a["coordinate"]: a for a in preview["artifacts"]}
    assert "cascade:3:dep:legacy@spine:a/spine:b:ban:dep:legacy" in by["spine:c"]["holds"]


def test_cargo_packages_path_order_trap(release_dist: Path) -> None:
    """pnpm-report cargo_packages follow sorted crate path order, not package-name order."""
    report = json.loads((release_dist / "pnpm-report.json").read_text(encoding="utf-8"))
    assert report["cargo_packages"] == [
        "pnpmfix-graph",
        "pnpmfix-cli",
        "pnpmfix-core",
        "pnpmfix-index",
    ]
    assert report["cargo_packages"] != sorted(report["cargo_packages"])
    manifest = json.loads((release_dist / "release-manifest.json").read_text(encoding="utf-8"))
    assert [e["name"] for e in manifest["workspace"]] == report["cargo_packages"]


def test_release_sh_uses_locked_offline_cargo(release_dist: Path) -> None:
    """release.sh must build with cargo --locked --offline and mention overrides."""
    _ = release_dist
    text = (APP / "scripts" / "release.sh").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    assert re.search(r"cargo\s+build\s+--release\s+--locked\s+--offline", text)
    assert "overrides" in code or "overrides/deps" in code
    assert "patch_url" in code


def test_hold_count_is_artifact_status_not_string_count(release_dist: Path) -> None:
    """Manifest hold_count equals artifacts with status=hold, not hold-string count."""
    manifest = json.loads((release_dist / "release-manifest.json").read_text(encoding="utf-8"))
    saw_gap = False
    for entry in manifest["bundles"]:
        lane = entry["lane"]
        preview = json.loads(
            (
                release_dist / "bundles" / f"pnpmfix-{lane}" / "share" / "inspect-preview.json"
            ).read_text(encoding="utf-8")
        )
        held = sum(1 for a in preview["artifacts"] if a["status"] == "hold")
        hold_strings = sum(len(a["holds"]) for a in preview["artifacts"])
        assert entry["hold_count"] == held == preview["totals"]["hold"]
        if hold_strings != held:
            saw_gap = True
            assert entry["hold_count"] != hold_strings
    assert saw_gap


def test_deps_csv_matches_pins_and_store(release_dist: Path) -> None:
    """Repaired deps.csv must match pins.csv digests and file:// pnpm-store URLs (not invent hashes)."""
    _ = release_dist
    pins = {}
    with (APP / "config" / "pins.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            pins[row["wrap"]] = row["sha256"].lower()
    with (APP / "config" / "deps.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["coordinate"] in {"dep:fmt", "dep:zlib", "dep:spdlog"}:
                wrap = row["coordinate"].split(":", 1)[1]
                assert row["source_url"] == f"file:///app/pnpm-store/{wrap}-{row['version']}.tgz"
                digest = row["source_hash"]
                if digest.startswith("sha256:"):
                    digest = digest[7:]
                assert digest.lower() == pins[wrap]
                assert row["provide"] == wrap

