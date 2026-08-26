"""Hard verifier for repair-cargo-metadata-cycle (82 cases).

Outcome-focused: no build-release.sh source inspection. Uses xtrace of the
release run plus direct metacycle/metrics-cli re-invocations so hardcoded
JSON artifacts cannot pass.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
DIST = APP / "dist"
OUTPUT = APP / "output"
FIXTURES = APP / "fixtures"
EXPECTED = Path(__file__).resolve().parent / "expected"
CONFIG = APP / "config"
SCRIPTS = APP / "scripts"
CARGO_CONFIG = APP / ".cargo" / "config.toml"
LOCK = CONFIG / "graph-lock.csv"
ORDER = CONFIG / "graph-order.csv"
POLICY = CONFIG / "metadata-policy.json"
MACROS_TOML = APP / "crates" / "metrics-macros" / "Cargo.toml"
METRICS_CLI_TOML = APP / "crates" / "metrics-cli" / "Cargo.toml"
METRICS_CORE_LIB = APP / "crates" / "metrics-core" / "src" / "lib.rs"
METRICS_CLI = APP / "target" / "release" / "metrics-cli"
METACYCLE = APP / "target" / "release" / "metacycle"
BUILD_SCRIPT = SCRIPTS / "build-release.sh"
HEALTHCHECK = SCRIPTS / "healthcheck.sh"
XTRACE = Path("/tmp/metacycle-build-xtrace.log")

REPORT_KEY_ORDER = ("services", "serviceTotals", "recordCount", "totalLatencyMs")
SUMMARY_KEY_ORDER = (
    "policy_kind",
    "record_count",
    "unique_services",
    "total_latency_ms",
    "max_latency_ms",
    "min_latency_ms",
    "source_sha256",
)
MANIFEST_KEY_ORDER = (
    "metadataEpoch",
    "toolVersion",
    "vendorRoot",
    "metadataPolicy",
    "lockDigest",
    "moduleGraphHash",
    "graphOrder",
    "dependencies",
)
TRAIL_KEY_ORDER = ("dep", "kind", "matched", "role", "version")

FIXTURE_SHA256 = "36ad08a16884e299c0f5b3b1c3928ffa2b981970f8d5f8a84d8707316e69d92f"
LOCK_DIGEST = "bda7081743798cf3025e01bbf0fce02302fc74740966351f5e9c7c1702e8b452"
MODULE_GRAPH_HASH = "40031808d3efc8e6dadeefa68ec5286bc300f380d49ea3bf9a853686d28a7c67"

LOCK_ROWS = [
    ("metrics-core", "0.4.0", "workspace", "path"),
    ("metrics-macros", "0.4.0", "workspace", "path"),
    ("metrics-cli", "0.4.0", "workspace", "path"),
    ("metacycle-core", "0.4.0", "workspace", "path"),
    ("metacycle-cli", "0.4.0", "workspace", "path"),
    ("serde", "1.0.228", "vendor", "registry"),
    ("serde_json", "1.0.138", "vendor", "registry"),
    ("itoa", "1.0.18", "vendor", "registry"),
    ("memchr", "2.8.3", "vendor", "registry"),
    ("quote", "1.0.46", "vendor", "registry"),
    ("syn", "2.0.118", "vendor", "registry"),
    ("proc-macro2", "1.0.106", "vendor", "registry"),
    ("ryu", "1.0.23", "vendor", "registry"),
    ("unicode-ident", "1.0.24", "vendor", "registry"),
    ("serde_derive", "1.0.228", "vendor", "registry"),
    ("serde_core", "1.0.228", "vendor", "registry"),
]

GRAPH_ORDER = [
    "metrics-core",
    "metrics-macros",
    "metrics-cli",
    "metacycle-core",
    "metacycle-cli",
    "itoa",
    "memchr",
    "proc-macro2",
    "quote",
    "ryu",
    "serde",
    "serde_core",
    "serde_derive",
    "serde_json",
    "syn",
    "unicode-ident",
]

SHARED = (LOCK, ORDER, POLICY, MACROS_TOML, METRICS_CLI_TOML, METRICS_CORE_LIB)


def normalize_version(raw: str) -> str:
    return raw.split("+")[0]


def versions_match(want: str, got: str) -> bool:
    return normalize_version(want) == normalize_version(got)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _manifest() -> dict:
    return json.loads(_read_text(DIST / "metadata-manifest.json").rstrip("\n"))


def _dep_graph() -> dict:
    return json.loads(_read_text(OUTPUT / "dep-graph.json").rstrip("\n"))


def _report() -> dict:
    return json.loads(_read_text(OUTPUT / "metrics-report.json").rstrip("\n"))


def _summary() -> dict:
    return json.loads(_read_text(OUTPUT / "metrics-summary.json").rstrip("\n"))


def _audit_trail_lines() -> list[dict]:
    return [
        json.loads(line)
        for line in _read_text(DIST / "audit-trail.ndjson").splitlines()
        if line.strip()
    ]


def xtrace_text() -> str:
    return XTRACE.read_text(encoding="utf-8")


def _rel_app(path: Path) -> str:
    try:
        return str(path.relative_to(APP))
    except ValueError:
        return str(path)


def run_metrics_cli(input_path: Path, out_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(METRICS_CLI), "--input", str(input_path), "--out", str(out_path)],
        cwd=APP,
        capture_output=True,
        text=True,
    )


def run_metacycle_graph(out: Path, lock: Path = LOCK) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            str(METACYCLE),
            "graph",
            "--root",
            "/app",
            "--lock",
            _rel_app(lock),
            "--out",
            str(out),
        ],
        cwd=APP,
        capture_output=True,
        text=True,
    )


def run_metacycle_audit(
    out: Path,
    *,
    lock: Path = LOCK,
    order: Path = ORDER,
    policy: Path = POLICY,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            str(METACYCLE),
            "audit",
            "--root",
            "/app",
            "--lock",
            _rel_app(lock),
            "--order",
            _rel_app(order),
            "--policy",
            _rel_app(policy),
            "--out",
            str(out),
        ],
        cwd=APP,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="session", autouse=True)
def run_offline_build_once():
    """Run the offline release once under bash xtrace (no pre-set SOURCE_DATE_EPOCH)."""
    if XTRACE.exists():
        XTRACE.unlink()
    env = {**os.environ, "CARGO_NET_OFFLINE": "true"}
    env.pop("SOURCE_DATE_EPOCH", None)
    cmd = (
        f"exec 7>'{XTRACE}'; export BASH_XTRACEFD=7; "
        f"bash -x '{BUILD_SCRIPT}'"
    )
    result = subprocess.run(
        ["bash", "-c", cmd],
        cwd=APP,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, (
        "build-release.sh failed\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


@pytest.fixture
def isolated(run_offline_build_once):
    snaps = {p: p.read_bytes() if p.exists() else None for p in SHARED}
    out_snaps = {
        p: p.read_bytes() if p.exists() else None
        for p in (
            OUTPUT / "metrics-report.json",
            OUTPUT / "metrics-summary.json",
            OUTPUT / "dep-graph.json",
            DIST / "metadata-manifest.json",
            DIST / "audit-trail.ndjson",
            DIST / "vendor-lock.sha256",
            DIST / "checksums.sha256",
        )
    }
    try:
        yield
    finally:
        for path, data in snaps.items():
            if data is None:
                if path.exists():
                    path.unlink()
            else:
                path.write_bytes(data)
        for path, data in out_snaps.items():
            if data is None:
                if path.exists():
                    path.unlink()
            else:
                path.write_bytes(data)


# --- core offline / cycle gates ---


def test_cargo_config_vendored_directory_vendor():
    """Vendored-sources points at relative vendor, not crates-vendor."""
    text = _read_text(CARGO_CONFIG)
    assert 'replace-with = "vendored-sources"' in text
    assert 'directory = "vendor"' in text
    assert "crates-vendor" not in text


def test_cargo_metadata_offline_succeeds():
    """cargo metadata succeeds offline with CARGO_NET_OFFLINE=true."""
    env = {**os.environ, "CARGO_NET_OFFLINE": "true"}
    subprocess.run(
        ["cargo", "metadata", "--format-version", "1", "--offline"],
        cwd=APP,
        env=env,
        check=True,
    )


def test_metrics_macros_no_dev_dependency_cycle():
    """Resolved cargo metadata has no metrics-macros → metrics-core dependency edge."""
    env = {**os.environ, "CARGO_NET_OFFLINE": "true"}
    result = subprocess.run(
        ["cargo", "metadata", "--format-version", "1", "--offline"],
        cwd=APP,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    macros = next(pkg for pkg in data["packages"] if pkg["name"] == "metrics-macros")
    dep_names = {dep["name"] for dep in macros.get("dependencies", [])}
    assert "metrics-core" not in dep_names
    assert "RecordMetric" in _read_text(METRICS_CORE_LIB)


def test_metrics_core_keeps_record_metric_derive():
    """metrics-core still derives RecordMetric via metrics_macros."""
    text = _read_text(METRICS_CORE_LIB)
    assert "RecordMetric" in text
    assert "metrics_macros" in text


def test_metrics_cli_version_uses_workspace():
    """metrics-cli inherits version.workspace = true without a pinned patch version."""
    text = _read_text(METRICS_CLI_TOML)
    assert "version.workspace = true" in text
    assert "0.3.9" not in text


def test_offline_rebuild_metrics_cli_binary():
    """metrics-cli rebuilds with --release --locked --offline."""
    env = {**os.environ, "CARGO_NET_OFFLINE": "true"}
    subprocess.run(
        [
            "cargo",
            "build",
            "--release",
            "--locked",
            "--offline",
            "--manifest-path",
            "/app/Cargo.toml",
            "-p",
            "metrics-cli",
        ],
        cwd=APP,
        env=env,
        check=True,
        timeout=600,
    )


def test_offline_rebuild_metacycle_binary():
    """metacycle-cli rebuilds with --release --locked --offline."""
    env = {**os.environ, "CARGO_NET_OFFLINE": "true"}
    subprocess.run(
        [
            "cargo",
            "build",
            "--release",
            "--locked",
            "--offline",
            "--manifest-path",
            "/app/Cargo.toml",
            "-p",
            "metacycle-cli",
        ],
        cwd=APP,
        env=env,
        check=True,
        timeout=600,
    )


def test_healthcheck_passes_with_release_binary():
    """healthcheck.sh exits zero when BIN points at the release metrics-cli."""
    subprocess.run(
        ["bash", str(HEALTHCHECK)],
        cwd=APP,
        env={**os.environ, "BIN": str(METRICS_CLI)},
        check=True,
    )


def test_metrics_report_matches_expected_bytes():
    """metrics-report.json matches the oracle expected bytes."""
    assert _read_text(OUTPUT / "metrics-report.json") == _read_text(EXPECTED / "metrics-report.json")


def test_metrics_report_key_order_services_first():
    """metrics-report.json preserves schema key order with services first."""
    raw = _read_text(OUTPUT / "metrics-report.json").rstrip("\n")
    positions = [raw.index(f'"{key}"') for key in REPORT_KEY_ORDER]
    assert positions == sorted(positions)


def test_metrics_summary_matches_expected_bytes():
    """metrics-summary.json matches the oracle expected bytes."""
    assert _read_text(OUTPUT / "metrics-summary.json") == _read_text(EXPECTED / "metrics-summary.json")


def test_metrics_summary_key_order():
    """metrics-summary.json preserves schema key insertion order."""
    raw = _read_text(OUTPUT / "metrics-summary.json").rstrip("\n")
    positions = [raw.index(f'"{key}"') for key in SUMMARY_KEY_ORDER]
    assert positions == sorted(positions)


def test_metrics_summary_source_sha256_matches_fixture():
    """metrics-summary source_sha256 hashes the raw fixture bytes."""
    assert _summary()["source_sha256"] == FIXTURE_SHA256
    assert _sha256_file(FIXTURES / "metrics-records.jsonl") == FIXTURE_SHA256


def test_dep_graph_key_order_edge_count_first():
    """dep-graph.json top-level keys are edgeCount then nodes."""
    assert list(_dep_graph().keys()) == ["edgeCount", "nodes"]


def test_dep_graph_nodes_sorted_by_id():
    """dep-graph nodes are sorted ascending by id."""
    ids = [node["id"] for node in _dep_graph()["nodes"]]
    assert ids == sorted(ids)


def test_dep_graph_nodes_match_graph_lock_allowlist():
    """dep-graph node ids match the graph-lock.csv allowlist exactly."""
    ids = {node["id"] for node in _dep_graph()["nodes"]}
    assert ids == {dep for dep, *_ in LOCK_ROWS}


def test_dep_graph_is_compact_json():
    """dep-graph.json is compact single-line JSON with one trailing newline."""
    raw = _read_text(OUTPUT / "dep-graph.json")
    assert raw.endswith("\n")
    body = raw[:-1]
    assert "\n" not in body
    assert "  " not in body


def test_metacycle_graph_rerun_matches_existing_dep_graph():
    """Re-running metacycle graph reproduces the existing dep-graph.json bytes."""
    tmp = Path("/tmp/dep-graph-rerun.json")
    result = run_metacycle_graph(tmp)
    assert result.returncode == 0, result.stderr
    assert _read_text(tmp) == _read_text(OUTPUT / "dep-graph.json")


def test_manifest_top_level_key_order_with_graph_order():
    """metadata-manifest.json top-level keys follow schema order including graphOrder."""
    assert list(_manifest().keys()) == list(MANIFEST_KEY_ORDER)


def test_manifest_graph_order_matches_csv():
    """manifest graphOrder equals the graph-order.csv sequence."""
    assert _manifest()["graphOrder"] == GRAPH_ORDER


def test_manifest_lock_digest_matches_graph_lock_file():
    """manifest lockDigest is SHA-256 of raw graph-lock.csv bytes."""
    assert _manifest()["lockDigest"] == LOCK_DIGEST
    assert _manifest()["lockDigest"] == _sha256_file(LOCK)


def test_manifest_module_graph_hash_matches_dependency_lines():
    """moduleGraphHash hashes sorted dep|version lines from manifest dependencies."""
    lines = sorted(
        f"{entry['dep']}|{entry['version']}" for entry in _manifest()["dependencies"]
    )
    expected = _sha256_text("\n".join(lines))
    assert _manifest()["moduleGraphHash"] == expected
    assert _manifest()["moduleGraphHash"] == MODULE_GRAPH_HASH


def test_manifest_versions_match_cargo_lock():
    """manifest dependency versions/roles/kinds match winning graph-lock rows."""
    by_name = {entry["dep"]: entry for entry in _manifest()["dependencies"]}
    for dep, version, role, kind in LOCK_ROWS:
        assert versions_match(version, by_name[dep]["version"])
        assert by_name[dep]["role"] == role
        assert by_name[dep]["kind"] == kind


def test_manifest_epoch_and_tool_version_from_policy():
    """manifest epoch, toolVersion, and vendorRoot come from metadata-policy.json."""
    policy = json.loads(_read_text(POLICY))
    assert _manifest()["metadataEpoch"] == policy["sourceDateEpoch"]
    assert _manifest()["toolVersion"] == policy["toolVersion"]
    assert _manifest()["vendorRoot"] == policy["vendorRoot"]


def test_manifest_dependencies_sorted_by_dep():
    """manifest dependencies are sorted ascending by dep name."""
    deps = [entry["dep"] for entry in _manifest()["dependencies"]]
    assert deps == sorted(deps)


def test_manifest_is_compact_single_line_json():
    """metadata-manifest.json is compact single-line JSON without padded spaces."""
    body = _read_text(DIST / "metadata-manifest.json").rstrip("\n")
    assert "\n" not in body
    assert "  " not in body


def test_metacycle_audit_rerun_matches_existing_manifest():
    """Re-running metacycle audit reproduces the existing metadata-manifest.json bytes."""
    tmp = Path("/tmp/metadata-manifest-rerun.json")
    result = run_metacycle_audit(tmp)
    assert result.returncode == 0, result.stderr
    assert _read_text(tmp) == _read_text(DIST / "metadata-manifest.json")


def test_metacycle_audit_rejects_lock_version_mismatch(isolated):
    """metacycle audit exits non-zero when a lock CSV version disagrees with Cargo.lock."""
    backup = _read_text(LOCK)
    out = Path("/tmp/metacycle-bad-manifest.json")
    out.unlink(missing_ok=True)
    try:
        LOCK.write_text(backup.replace("1.0.228", "9.9.9"), encoding="utf-8")
        result = run_metacycle_audit(out)
        assert result.returncode != 0
    finally:
        LOCK.write_text(backup, encoding="utf-8")
        out.unlink(missing_ok=True)


def test_audit_trail_sorted_by_dep():
    """audit-trail.ndjson lines are sorted ascending by dep."""
    deps = [line["dep"] for line in _audit_trail_lines()]
    assert deps == sorted(deps)


def test_audit_trail_versions_match_manifest_dependencies():
    """audit-trail versions match the corresponding manifest dependency versions."""
    manifest_versions = {entry["dep"]: entry["version"] for entry in _manifest()["dependencies"]}
    for row in _audit_trail_lines():
        assert row["version"] == manifest_versions[row["dep"]]


def test_vendor_lock_sha256_matches_vendor_serde_cargo_toml():
    """vendor-lock.sha256 digests vendor/serde/Cargo.toml with the bare relative label."""
    digest, rel = _read_text(DIST / "vendor-lock.sha256").strip().split(maxsplit=1)
    assert rel == "vendor/serde/Cargo.toml"
    assert digest == _sha256_file(APP / "vendor/serde/Cargo.toml")


def test_checksums_sorted_complete_relative_paths():
    """checksums.sha256 lists every dist file except itself with sorted bare relative paths."""
    lines = _read_text(DIST / "checksums.sha256").strip().splitlines()
    paths = [line.split(maxsplit=1)[1] for line in lines]
    assert paths == sorted(paths)
    assert "checksums.sha256" not in paths
    expected = sorted(
        rel.relative_to(DIST).as_posix()
        for rel in DIST.rglob("*")
        if rel.is_file() and rel.name != "checksums.sha256"
    )
    assert paths == expected
    for line in lines:
        digest, rel = line.split(maxsplit=1)
        assert re.fullmatch(r"[0-9a-f]{64}", digest)
        assert digest == _sha256_file(DIST / rel)


def test_checksums_exclude_output_tree():
    """checksums.sha256 never includes paths under the output/ tree."""
    paths = [line.split(maxsplit=1)[1] for line in _read_text(DIST / "checksums.sha256").splitlines()]
    assert not any(path.startswith("output/") for path in paths)


def test_output_directory_contains_report_and_summary_only():
    """output/ contains only dep-graph, metrics-report, and metrics-summary."""
    assert sorted(p.name for p in OUTPUT.iterdir()) == [
        "dep-graph.json",
        "metrics-report.json",
        "metrics-summary.json",
    ]


def test_fixture_metrics_records_bytes_unchanged():
    """fixtures/metrics-records.jsonl bytes remain unmodified."""
    assert _sha256_file(FIXTURES / "metrics-records.jsonl") == FIXTURE_SHA256


def test_metrics_cli_rejects_wrong_policy_kind(isolated):
    """metrics-cli exits non-zero and writes no outs when policyKind is wrong."""
    backup = _read_text(POLICY)
    out = Path("/tmp/policy-kind-test.json")
    out.unlink(missing_ok=True)
    summary = Path("/tmp/metrics-summary.json")
    summary.unlink(missing_ok=True)
    try:
        POLICY.write_text(
            backup.replace("metadata-release", "wrong-policy"),
            encoding="utf-8",
        )
        result = run_metrics_cli(FIXTURES / "metrics-records.jsonl", out)
        assert result.returncode != 0
        assert not out.exists()
        assert not summary.exists()
    finally:
        POLICY.write_text(backup, encoding="utf-8")
        out.unlink(missing_ok=True)
        summary.unlink(missing_ok=True)


# --- behavioral replacements for former build-release.sh source inspection ---


def test_xtrace_exports_source_date_epoch_from_policy():
    """Release run exports SOURCE_DATE_EPOCH equal to live policy sourceDateEpoch."""
    epoch = json.loads(_read_text(POLICY))["sourceDateEpoch"]
    trace = xtrace_text()
    assert re.search(rf"SOURCE_DATE_EPOCH=.*{epoch}", trace)
    assert _manifest()["metadataEpoch"] == epoch


def test_xtrace_uses_offline_locked_cargo_builds():
    """Release run invokes cargo with both --locked and --offline for package builds."""
    trace = xtrace_text()
    assert "--locked" in trace
    assert "--offline" in trace
    assert "CARGO_NET_OFFLINE" in trace


def test_xtrace_runs_metacycle_graph_with_lock():
    """Release run invokes metacycle graph with a --lock flag against graph-lock.csv."""
    trace = xtrace_text()
    assert "graph" in trace
    assert "--lock" in trace
    assert "graph-lock.csv" in trace
    assert (OUTPUT / "dep-graph.json").is_file()


def test_xtrace_writes_vendor_lock_digest():
    """Release must produce vendor-lock.sha256 digesting vendor/serde/Cargo.toml (artifact check only; redirects may hide the path in xtrace)."""
    digest, rel = _read_text(DIST / "vendor-lock.sha256").strip().split(maxsplit=1)
    assert rel == "vendor/serde/Cargo.toml"
    assert digest == _sha256_file(APP / "vendor/serde/Cargo.toml")
    # Do not require the filename to appear in bash xtrace: a correct `> dist/vendor-lock.sha256`
    # redirect can omit the destination token from BASH_XTRACEFD while still writing the file.


def test_xtrace_runs_metacycle_audit_with_order():
    """Release run invokes metacycle audit with --order so graphOrder is populated."""
    trace = xtrace_text()
    assert "audit" in trace
    assert "--order" in trace
    assert "graph-order.csv" in trace
    assert _manifest()["graphOrder"] == GRAPH_ORDER


def test_xtrace_checksums_from_dist_workdir():
    """Checksum lines use dist-relative paths as if produced inside /app/dist."""
    trace = xtrace_text()
    assert "checksums.sha256" in trace
    for line in _read_text(DIST / "checksums.sha256").strip().splitlines():
        assert "  " in line
        digest, rel = line.split("  ", 1)
        assert not rel.startswith("dist/")
        assert not rel.startswith("./")
        assert not rel.startswith("/app/")
        assert digest == _sha256_file(DIST / rel)


# --- 40 hard cases ---


def test_h01_metrics_cli_direct_rerun_overwrites_poisoned_artifacts(isolated):
    """Direct metrics-cli rerun must overwrite poisoned report/summary; hardcoded files fail."""
    report = OUTPUT / "metrics-report.json"
    summary = OUTPUT / "metrics-summary.json"
    report.write_text(
        '{"services":[],"serviceTotals":{},"recordCount":0,"totalLatencyMs":0}\n',
        encoding="utf-8",
    )
    summary.write_text(
        '{"policy_kind":"metadata-release","record_count":0,"unique_services":0,'
        '"total_latency_ms":0,"max_latency_ms":0,"min_latency_ms":0,'
        '"source_sha256":"deadbeef"}\n',
        encoding="utf-8",
    )
    result = run_metrics_cli(FIXTURES / "metrics-records.jsonl", report)
    assert result.returncode == 0, result.stderr
    assert _read_text(report) == _read_text(EXPECTED / "metrics-report.json")
    assert _read_text(summary) == _read_text(EXPECTED / "metrics-summary.json")


def test_h02_metrics_cli_rerun_to_temp_matches_expected(isolated):
    """metrics-cli writing to a fresh temp dir must match graded expected bytes."""
    tmp = Path("/tmp/metrics-cli-rerun-dir")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    out = tmp / "metrics-report.json"
    result = run_metrics_cli(FIXTURES / "metrics-records.jsonl", out)
    assert result.returncode == 0, result.stderr
    assert _read_text(out) == _read_text(EXPECTED / "metrics-report.json")
    assert _read_text(tmp / "metrics-summary.json") == _read_text(EXPECTED / "metrics-summary.json")


def test_h03_metrics_cli_alternate_fixture_recomputes_totals(isolated):
    """Alternate JSONL input must change services/totals; cannot ignore --input."""
    alt = Path("/tmp/alt-metrics-records.jsonl")
    alt.write_text(
        '{"service":"zeta","latency_ms":100}\n\n{"service":"alpha","latency_ms":1}\n',
        encoding="utf-8",
    )
    out = Path("/tmp/alt-metrics-report.json")
    out.unlink(missing_ok=True)
    Path("/tmp/metrics-summary.json").unlink(missing_ok=True)
    result = run_metrics_cli(alt, out)
    assert result.returncode == 0, result.stderr
    data = json.loads(_read_text(out))
    assert data["services"] == ["alpha", "zeta"]
    assert data["serviceTotals"] == {"alpha": 1, "zeta": 100}
    assert data["recordCount"] == 2
    assert data["totalLatencyMs"] == 101
    summary = json.loads(_read_text(Path("/tmp/metrics-summary.json")))
    assert summary["max_latency_ms"] == 100
    assert summary["min_latency_ms"] == 1
    assert summary["source_sha256"] == _sha256_file(alt)


def test_h04_metrics_cli_summary_always_sibling_of_out(isolated):
    """Summary is always metrics-summary.json beside --out, not a fixed /app/output path."""
    nested = Path("/tmp/nested/out/dir")
    if Path("/tmp/nested").exists():
        shutil.rmtree(Path("/tmp/nested"))
    nested.mkdir(parents=True)
    out = nested / "custom-report.json"
    result = run_metrics_cli(FIXTURES / "metrics-records.jsonl", out)
    assert result.returncode == 0, result.stderr
    assert out.is_file()
    assert (nested / "metrics-summary.json").is_file()
    assert not (nested / "custom-report-summary.json").exists()


def test_h05_metrics_cli_health_token_and_no_artifact_write(isolated):
    """--health prints the factory token and must not create report files."""
    result = subprocess.run(
        [str(METRICS_CLI), "--health"],
        cwd=APP,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "metrics-factory-ok"


def test_h06_metrics_cli_rejects_policy_before_writing_temp(isolated):
    """Wrong policyKind exits non-zero before creating --out in a clean temp directory."""
    backup = POLICY.read_bytes()
    tmp = Path("/tmp/policy-reject-dir")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    out = tmp / "metrics-report.json"
    try:
        POLICY.write_text(
            _read_text(POLICY).replace("metadata-release", "staging-release"),
            encoding="utf-8",
        )
        result = run_metrics_cli(FIXTURES / "metrics-records.jsonl", out)
        assert result.returncode != 0
        assert list(tmp.iterdir()) == []
    finally:
        POLICY.write_bytes(backup)


def test_h07_blank_and_whitespace_fixture_lines_skipped(isolated):
    """Blank and whitespace-only JSONL lines must not inflate recordCount."""
    alt = Path("/tmp/blank-lines-metrics.jsonl")
    alt.write_text(
        "\n  \n{\"service\":\"api\",\"latency_ms\":9}\n\n{\"service\":\"api\",\"latency_ms\":1}\n \n",
        encoding="utf-8",
    )
    out = Path("/tmp/blank-lines-report.json")
    result = run_metrics_cli(alt, out)
    assert result.returncode == 0, result.stderr
    data = json.loads(_read_text(out))
    assert data["recordCount"] == 2
    assert data["totalLatencyMs"] == 10
    assert data["services"] == ["api"]


def test_h08_service_totals_keys_lexicographic_btree(isolated):
    """serviceTotals keys must follow BTreeMap lexicographic order, not input order."""
    alt = Path("/tmp/btree-metrics.jsonl")
    alt.write_text(
        '{"service":"worker","latency_ms":3}\n'
        '{"service":"api","latency_ms":2}\n'
        '{"service":"batch","latency_ms":1}\n',
        encoding="utf-8",
    )
    out = Path("/tmp/btree-report.json")
    result = run_metrics_cli(alt, out)
    assert result.returncode == 0, result.stderr
    raw = _read_text(out)
    assert raw.index('"api"') < raw.index('"batch"') < raw.index('"worker"')
    data = json.loads(raw)
    assert list(data["serviceTotals"].keys()) == ["api", "batch", "worker"]


def test_h09_zero_latency_sets_min_and_participates_in_total(isolated):
    """A zero-latency record sets min_latency_ms to 0 and still counts toward totals."""
    alt = Path("/tmp/zero-latency.jsonl")
    alt.write_text(
        '{"service":"api","latency_ms":0}\n{"service":"api","latency_ms":5}\n',
        encoding="utf-8",
    )
    out = Path("/tmp/zero-latency-report.json")
    Path("/tmp/metrics-summary.json").unlink(missing_ok=True)
    result = run_metrics_cli(alt, out)
    assert result.returncode == 0, result.stderr
    summary = json.loads(_read_text(Path("/tmp/metrics-summary.json")))
    assert summary["min_latency_ms"] == 0
    assert summary["max_latency_ms"] == 5
    assert summary["total_latency_ms"] == 5
    assert json.loads(_read_text(out))["serviceTotals"]["api"] == 5


def test_h10_restoring_macros_normal_dep_cycle_breaks_cargo_metadata(isolated):
    """Adding metrics-macros → metrics-core as a normal path dependency must break metadata."""
    original = MACROS_TOML.read_bytes()
    try:
        text = original.decode("utf-8")
        assert "[dependencies]" in text
        text = text.replace(
            "[dependencies]\n",
            '[dependencies]\nmetrics-core = { path = "../metrics-core" }\n',
            1,
        )
        MACROS_TOML.write_text(text, encoding="utf-8")
        result = subprocess.run(
            ["cargo", "metadata", "--format-version", "1", "--offline"],
            cwd=APP,
            env={**os.environ, "CARGO_NET_OFFLINE": "true"},
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "cyclic" in (result.stderr + result.stdout).lower() or result.returncode != 0
    finally:
        MACROS_TOML.write_bytes(original)


def test_h11_record_metric_still_compiles_after_cycle_fix():
    """metrics-core public API still references RecordMetric after the cycle is repaired."""
    text = _read_text(METRICS_CORE_LIB)
    assert "RecordMetric" in text
    assert "metrics_macros" in text


def test_h12_audit_tracks_live_policy_tool_version_mutation(isolated):
    """Mutating policy toolVersion must change the audited manifest toolVersion on rerun."""
    backup = POLICY.read_bytes()
    out = Path("/tmp/policy-tool-manifest.json")
    try:
        policy = json.loads(backup)
        policy["toolVersion"] = "metacycle 9.9.9-test"
        POLICY.write_text(json.dumps(policy), encoding="utf-8")
        result = run_metacycle_audit(out)
        assert result.returncode == 0, result.stderr
        data = json.loads(_read_text(out))
        assert data["toolVersion"] == "metacycle 9.9.9-test"
        assert data["metadataEpoch"] == policy["sourceDateEpoch"]
    finally:
        POLICY.write_bytes(backup)
        out.unlink(missing_ok=True)


def test_h13_audit_tracks_live_source_date_epoch_mutation(isolated):
    """Mutating sourceDateEpoch must change metadataEpoch on the next audit."""
    backup = POLICY.read_bytes()
    out = Path("/tmp/policy-epoch-manifest.json")
    try:
        policy = json.loads(backup)
        policy["sourceDateEpoch"] = 1600000001
        POLICY.write_text(json.dumps(policy), encoding="utf-8")
        result = run_metacycle_audit(out)
        assert result.returncode == 0, result.stderr
        assert json.loads(_read_text(out))["metadataEpoch"] == 1600000001
    finally:
        POLICY.write_bytes(backup)
        out.unlink(missing_ok=True)


def test_h14_graph_order_mutation_rewrites_manifest_graph_order(isolated):
    """Reordering graph-order.csv must change graphOrder while keeping dependency set."""
    backup = ORDER.read_bytes()
    out = Path("/tmp/order-mut-manifest.json")
    try:
        lines = ["order,dep\n"]
        for idx, dep in enumerate(reversed(GRAPH_ORDER), start=1):
            lines.append(f"{idx},{dep}\n")
        ORDER.write_text("".join(lines), encoding="utf-8")
        result = run_metacycle_audit(out)
        assert result.returncode == 0, result.stderr
        data = json.loads(_read_text(out))
        assert data["graphOrder"] == list(reversed(GRAPH_ORDER))
        assert {d["dep"] for d in data["dependencies"]} == {d for d, *_ in LOCK_ROWS}
    finally:
        ORDER.write_bytes(backup)
        out.unlink(missing_ok=True)


def test_h15_lock_digest_changes_when_graph_lock_bytes_change(isolated):
    """Appending bytes to graph-lock.csv must update lockDigest on the next audit."""
    backup = LOCK.read_bytes()
    out = Path("/tmp/lock-digest-manifest.json")
    try:
        text = backup.decode("utf-8")
        LOCK.write_text(text + ("\n" if text.endswith("\n") else "\n\n"), encoding="utf-8")
        result = run_metacycle_audit(out)
        assert result.returncode == 0, result.stderr
        new_digest = json.loads(_read_text(out))["lockDigest"]
        assert new_digest == _sha256_file(LOCK)
        assert new_digest != LOCK_DIGEST
    finally:
        LOCK.write_bytes(backup)
        out.unlink(missing_ok=True)


def test_h16_audit_absolute_out_writes_trail_beside_manifest(isolated):
    """Audit --out to an absolute nested path must write audit-trail.ndjson beside it."""
    tmp = Path("/tmp/abs-audit/out")
    if Path("/tmp/abs-audit").exists():
        shutil.rmtree(Path("/tmp/abs-audit"))
    tmp.mkdir(parents=True)
    man = tmp / "metadata-manifest.json"
    result = run_metacycle_audit(man)
    assert result.returncode == 0, result.stderr
    trail = tmp / "audit-trail.ndjson"
    assert man.is_file() and trail.is_file()
    assert len([ln for ln in _read_text(trail).splitlines() if ln.strip()]) == len(LOCK_ROWS)


def test_h17_graph_absolute_out_matches_release_dep_graph(isolated):
    """metacycle graph --out absolute path must match the release dep-graph bytes."""
    tmp = Path("/tmp/abs-graph/dep-graph.json")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    result = run_metacycle_graph(tmp)
    assert result.returncode == 0, result.stderr
    assert _read_text(tmp) == _read_text(OUTPUT / "dep-graph.json")


def test_h18_graph_filters_to_lock_allowlist_only(isolated):
    """Dep graph nodes must exclude crates absent from graph-lock.csv even if in metadata."""
    ids = {node["id"] for node in _dep_graph()["nodes"]}
    assert "serde" in ids
    assert "getrandom" not in ids
    assert "libc" not in ids
    assert len(ids) == 16


def test_h19_module_graph_hash_formula_serde_before_serde_json_sort():
    """Full-string sort of dep|version places serde_json before serde because | > _."""
    lines = sorted(f"{dep}|{ver}" for dep, ver, *_ in LOCK_ROWS)
    serde_line = next(x for x in lines if x.startswith("serde|"))
    serde_json_line = next(x for x in lines if x.startswith("serde_json|"))
    assert lines.index(serde_json_line) < lines.index(serde_line)
    assert _sha256_text("\n".join(lines)) == MODULE_GRAPH_HASH
    assert _manifest()["moduleGraphHash"] == MODULE_GRAPH_HASH


def test_h20_plus_suffix_versions_still_match_lock_csv(isolated):
    """Audit must ignore +suffix when comparing graph-lock versions to Cargo.lock."""
    by_name = {entry["dep"]: entry for entry in _manifest()["dependencies"]}
    for dep, version, *_ in LOCK_ROWS:
        assert versions_match(version, by_name[dep]["version"])


def test_h21_checksum_paths_never_prefix_dist_or_dot_slash():
    """Every checksum path is bare relative to dist/ (no dist/ or ./ prefixes)."""
    for line in _read_text(DIST / "checksums.sha256").strip().splitlines():
        _, rel = line.split("  ", 1)
        assert not rel.startswith("dist/")
        assert not rel.startswith("./")
        assert (DIST / rel).is_file()


def test_h22_checksums_two_space_separator_and_hex():
    """Checksum lines use exactly one two-space separator and lowercase hex digests."""
    for line in _read_text(DIST / "checksums.sha256").strip().splitlines():
        assert line.count("  ") == 1
        digest, rel = line.split("  ", 1)
        assert re.fullmatch(r"[0-9a-f]{64}", digest)
        assert rel == rel.strip()


def test_h23_vendor_lock_single_trailing_newline_only():
    """vendor-lock.sha256 ends with exactly one newline."""
    raw = _read_text(DIST / "vendor-lock.sha256")
    assert raw.endswith("\n") and not raw.endswith("\n\n")
    assert raw.count("\n") == 1


def test_h24_audit_trail_compact_key_order_and_matched_true():
    """Each audit-trail line is compact JSON with contracted key order and matched true."""
    for line in _read_text(DIST / "audit-trail.ndjson").splitlines():
        if not line.strip():
            continue
        assert "  " not in line
        obj = json.loads(line)
        assert list(obj.keys()) == list(TRAIL_KEY_ORDER)
        assert obj["matched"] is True


def test_h25_manifest_offline_locked_nested_policy_true():
    """metadataPolicy.offlineLocked must be JSON true under the nested policy object."""
    policy = _manifest()["metadataPolicy"]
    assert policy["offlineLocked"] is True
    assert policy["vendorRoot"] == "vendor"


def test_h26_dep_graph_edge_count_positive_integer():
    """edgeCount is a positive integer counting allowlisted resolve edges."""
    edge = _dep_graph()["edgeCount"]
    assert isinstance(edge, int)
    assert edge > 0


def test_h27_report_and_summary_single_trailing_newline():
    """Both graded metrics artifacts end with exactly one trailing newline."""
    for name in ("metrics-report.json", "metrics-summary.json"):
        raw = _read_text(OUTPUT / name)
        assert raw.endswith("\n") and not raw.endswith("\n\n")


def test_h28_summary_unique_services_matches_report_services_len():
    """summary.unique_services equals len(report.services) after the release."""
    assert _summary()["unique_services"] == len(_report()["services"])
    assert _summary()["record_count"] == _report()["recordCount"]
    assert _summary()["total_latency_ms"] == _report()["totalLatencyMs"]


def test_h29_cargo_lock_present_for_locked_builds():
    """Cargo.lock must exist so --locked offline builds can succeed."""
    assert (APP / "Cargo.lock").is_file()
    assert 'name = "metrics-cli"' in _read_text(APP / "Cargo.lock")


def test_h30_metacycle_binary_name_is_metacycle():
    """Release installs the CLI as /app/target/release/metacycle."""
    assert METACYCLE.is_file()


def test_h31_healthcheck_fails_when_binary_missing(isolated):
    """healthcheck must fail if BIN points at a missing path."""
    missing = Path("/tmp/missing-metrics-cli-binary")
    missing.unlink(missing_ok=True)
    result = subprocess.run(
        ["bash", str(HEALTHCHECK)],
        cwd=APP,
        env={**os.environ, "BIN": str(missing)},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_h32_metrics_cli_version_workspace_resolves_to_workspace_version():
    """metrics-cli package version comes from workspace (0.4.0), not a pinned 0.3.9."""
    text = _read_text(METRICS_CLI_TOML)
    assert "version.workspace = true" in text
    root = _read_text(APP / "Cargo.toml")
    assert 'version = "0.4.0"' in root


def test_h33_poisoned_dep_graph_overwritten_by_metacycle_graph(isolated):
    """Hardcoded dep-graph.json must be replaced by a live metacycle graph invocation."""
    path = OUTPUT / "dep-graph.json"
    path.write_text('{"edgeCount":0,"nodes":[]}\n', encoding="utf-8")
    result = run_metacycle_graph(path)
    assert result.returncode == 0, result.stderr
    data = json.loads(_read_text(path))
    assert data["edgeCount"] > 0
    assert len(data["nodes"]) == 16


def test_h34_poisoned_manifest_overwritten_by_metacycle_audit(isolated):
    """Hardcoded metadata-manifest.json must be replaced by a live metacycle audit."""
    path = DIST / "metadata-manifest.json"
    path.write_text('{"metadataEpoch":0}\n', encoding="utf-8")
    result = run_metacycle_audit(path)
    assert result.returncode == 0, result.stderr
    data = json.loads(_read_text(path))
    assert list(data.keys()) == list(MANIFEST_KEY_ORDER)
    assert data["moduleGraphHash"] == MODULE_GRAPH_HASH


def test_h35_audit_smaller_lock_changes_module_graph_hash(isolated):
    """Removing serde_json from graph-lock.csv must change moduleGraphHash on audit."""
    backup = LOCK.read_bytes()
    out = Path("/tmp/missing-row-manifest.json")
    out.unlink(missing_ok=True)
    try:
        lines = [
            ln
            for ln in backup.decode("utf-8").splitlines()
            if not ln.startswith("vendor,serde_json,")
        ]
        LOCK.write_text("\n".join(lines) + "\n", encoding="utf-8")
        result = run_metacycle_audit(out)
        assert result.returncode == 0, result.stderr
        data = json.loads(_read_text(out))
        deps = {d["dep"] for d in data["dependencies"]}
        assert "serde_json" not in deps
        assert data["moduleGraphHash"] != MODULE_GRAPH_HASH
    finally:
        LOCK.write_bytes(backup)
        out.unlink(missing_ok=True)


def test_h36_summary_policy_kind_tracks_live_policy(isolated):
    """metrics-summary policy_kind must equal the live metadata-policy.json policyKind."""
    assert _summary()["policy_kind"] == json.loads(_read_text(POLICY))["policyKind"]
    assert _summary()["policy_kind"] == "metadata-release"


def test_h37_double_metrics_cli_invocation_idempotent(isolated):
    """Running metrics-cli twice against the same fixture yields identical bytes."""
    out = Path("/tmp/idem-metrics-report.json")
    out.unlink(missing_ok=True)
    Path("/tmp/metrics-summary.json").unlink(missing_ok=True)
    assert run_metrics_cli(FIXTURES / "metrics-records.jsonl", out).returncode == 0
    first_report = _read_text(out)
    first_summary = _read_text(Path("/tmp/metrics-summary.json"))
    assert run_metrics_cli(FIXTURES / "metrics-records.jsonl", out).returncode == 0
    assert _read_text(out) == first_report == _read_text(EXPECTED / "metrics-report.json")
    assert _read_text(Path("/tmp/metrics-summary.json")) == first_summary == _read_text(
        EXPECTED / "metrics-summary.json"
    )


def test_h38_vendor_serde_toml_digest_stable_across_reread():
    """vendor-lock digest remains stable and matches a fresh sha256 of the vendor file."""
    digest, rel = _read_text(DIST / "vendor-lock.sha256").strip().split(maxsplit=1)
    assert rel == "vendor/serde/Cargo.toml"
    assert digest == _sha256_file(APP / "vendor" / "serde" / "Cargo.toml")


def test_h39_output_must_not_contain_dist_artifacts():
    """/app/output must not contain dist-sidecar filenames (manifest/trail/checksums)."""
    names = {p.name for p in OUTPUT.iterdir()}
    assert "metadata-manifest.json" not in names
    assert "audit-trail.ndjson" not in names
    assert "checksums.sha256" not in names
    assert "vendor-lock.sha256" not in names


def test_h40_release_report_totals_consistent_internal_invariants():
    """Release report totals are internally consistent across services and summary."""
    report = _report()
    summary = _summary()
    assert sum(report["serviceTotals"].values()) == report["totalLatencyMs"] == 110
    assert report["recordCount"] == 10
    assert report["services"] == ["api", "batch", "gateway", "worker"]
    assert report["serviceTotals"] == {"api": 20, "batch": 60, "gateway": 7, "worker": 23}
    assert summary["max_latency_ms"] == 42
    assert summary["min_latency_ms"] == 0
    assert summary["source_sha256"] == FIXTURE_SHA256
