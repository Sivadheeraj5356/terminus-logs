"""Verifier tests for indigo-palisade-mediator.

Spec coverage map:
- CLI and file presence tests -> instruction.md and README command sections
- Schema tests -> /app/schemas/*.schema.*
- Version, range, BOM, relocation, exclusion, scope tests -> mediation-policy.md
- Fatal/reportable tests -> reason/severity table in mediation-policy.md
- Cross-output tests -> cross-output invariants in mediation-policy.md
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
from pathlib import Path

APP = Path("/app")
CLI = [
    "/app/bin/mediate-deps",
    "--data-dir",
    "--out-json",
    "--out-classpath",
    "--out-mediation",
    "--out-findings",
]

ALL_REASONS = [
    "bom_override_rejected",
    "checksum_mismatch",
    "license_denied",
    "license_unknown",
    "range_conflict",
    "relocated_artifact",
    "scope_excluded",
    "dependency_cycle",
    "duplicate_primary_key",
    "invalid_version",
    "invalid_range",
    "relocation_cycle",
    "schema_invalid",
    "unknown_checksum_row",
    "unresolved_required_artifact",
]

CLASSPATH_HEADER = [
    "order",
    "coord",
    "version",
    "scope",
    "jar",
    "sha256",
    "license",
    "reason_codes",
]
MEDIATION_HEADER = [
    "coord",
    "requested_versions",
    "selected_version",
    "selected_by",
    "depth",
    "scope",
    "original_coords",
    "reason_codes",
]
FINDINGS_HEADER = ["finding_id", "reason", "severity", "coord", "version", "detail"]


def _default_out(tmp: Path) -> dict[str, Path]:
    out = tmp / "out"
    return {
        "json": out / "audit.json",
        "classpath": out / "classpath.csv",
        "mediation": out / "mediation.csv",
        "findings": out / "findings.csv",
    }


def _copy_data(tmp: Path, **overrides: Path | str) -> Path:
    data = tmp / "data"
    shutil.copytree(APP / "data", data)
    for name, content in overrides.items():
        dest = data / name
        if isinstance(content, Path):
            shutil.copy(content, dest)
        else:
            dest.write_text(content, encoding="utf-8")
    return data


def _run(data_dir: Path, outputs: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    cmd = [
        "/app/bin/mediate-deps",
        "--data-dir",
        str(data_dir),
        "--out-json",
        str(outputs["json"]),
        "--out-classpath",
        str(outputs["classpath"]),
        "--out-mediation",
        str(outputs["mediation"]),
        "--out-findings",
        str(outputs["findings"]),
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    return rows[0], rows[1:]


def _reason_code_counts(
    findings_rows: list[list[str]], mediation_rows: list[list[str]], classpath_rows: list[list[str]]
) -> dict[str, int]:
    counts: dict[str, int] = {r: 0 for r in ALL_REASONS}
    for row in findings_rows:
        counts[row[1]] = counts.get(row[1], 0) + 1
    for row in mediation_rows + classpath_rows:
        codes = row[-1]
        if codes:
            for code in codes.split(";"):
                counts[code] = counts.get(code, 0) + 1
    return counts


def _assert_bundle_bytes_equal(outs1: dict[str, Path], outs2: dict[str, Path]) -> None:
    for key in ("classpath", "mediation", "findings"):
        assert outs1[key].read_bytes() == outs2[key].read_bytes()
    audit1 = json.loads(outs1["json"].read_text(encoding="utf-8"))
    audit2 = json.loads(outs2["json"].read_text(encoding="utf-8"))
    audit1.pop("outputs", None)
    audit2.pop("outputs", None)
    assert audit1 == audit2


def _write_clean_direct_checksums(data: Path) -> None:
    (data / "checksums.csv").write_text(
        "coord,version,sha256\n"
        "org.demo:api,1.2.3,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n",
        encoding="utf-8",
    )


def _assert_fatal_without_outputs(data: Path, outs: dict[str, Path]) -> None:
    result = _run(data, outs)
    assert result.returncode != 0
    assert not any(outs[k].exists() for k in outs)


def _prepare_clean_direct_bundle(data: Path) -> None:
    shutil.copy(APP / "examples" / "clean-direct" / "roots.edn", data / "roots.edn")
    shutil.copy(APP / "examples" / "clean-direct" / "local_repo.edn", data / "local_repo.edn")
    _write_clean_direct_checksums(data)


def _minimal_bundle(tmp: Path) -> tuple[Path, dict[str, Path]]:
    data = tmp / "data"
    data.mkdir(parents=True)
    shutil.copy(APP / "data" / "mediation_config.edn", data)
    shutil.copy(APP / "data" / "bom.edn", data)
    shutil.copy(APP / "data" / "relocations.csv", data)
    shutil.copy(APP / "data" / "license_policy.csv", data)
    (data / "checksums.csv").write_text("coord,version,sha256\n", encoding="utf-8")
    return data, _default_out(tmp)


# --- CLI and file presence (instruction.md, README) ---


def test_policy_and_schema_files_exist_in_app():
    """Policy and schema files referenced by instruction.md must exist under /app."""
    assert (APP / "mediation-policy.md").is_file()
    assert (APP / "schemas" / "audit.schema.json").is_file()
    assert (APP / "schemas" / "classpath.schema.csv").is_file()
    assert (APP / "schemas" / "mediation.schema.csv").is_file()
    assert (APP / "schemas" / "findings.schema.csv").is_file()
    assert (APP / "schemas" / "inputs.schema.md").is_file()


def test_exact_cli_flags_are_required_and_outputs_are_created(tmp_path):
    """CLI must accept only documented flags and create all four output files."""
    data, outs = _minimal_bundle(tmp_path)
    shutil.copy(APP / "examples" / "clean-direct" / "roots.edn", data / "roots.edn")
    shutil.copy(APP / "examples" / "clean-direct" / "local_repo.edn", data / "local_repo.edn")
    _write_clean_direct_checksums(data)
    result = _run(data, outs)
    assert result.returncode == 0, result.stderr + result.stdout
    for key in ("json", "classpath", "mediation", "findings"):
        assert outs[key].is_file()

    bad = subprocess.run(
        ["/app/bin/mediate-deps", str(data), "--out-json", str(outs["json"])],
        capture_output=True,
        text=True,
    )
    assert bad.returncode != 0


# --- Schema tests (/app/schemas) ---


def test_audit_json_top_level_keys_are_exact_and_ordered(tmp_path):
    """audit.json top-level keys must be summary, by_reason, license_summary, outputs in order."""
    data, outs = _minimal_bundle(tmp_path)
    shutil.copy(APP / "examples" / "clean-direct" / "roots.edn", data / "roots.edn")
    shutil.copy(APP / "examples" / "clean-direct" / "local_repo.edn", data / "local_repo.edn")
    _write_clean_direct_checksums(data)
    assert _run(data, outs).returncode == 0
    raw = outs["json"].read_text(encoding="utf-8")
    keys = [line.strip().split(":")[0].strip('"') for line in raw.splitlines() if line.strip().startswith('"')]
    top = [k for k in keys if k in {"summary", "by_reason", "license_summary", "outputs"}]
    assert top == ["summary", "by_reason", "license_summary", "outputs"]


def test_classpath_csv_header_order_and_reason_codes(tmp_path):
    """classpath.csv must use the documented header and semicolon reason_codes."""
    data, outs = _minimal_bundle(tmp_path)
    shutil.copy(APP / "examples" / "clean-direct" / "roots.edn", data / "roots.edn")
    shutil.copy(APP / "examples" / "clean-direct" / "local_repo.edn", data / "local_repo.edn")
    _write_clean_direct_checksums(data)
    assert _run(data, outs).returncode == 0
    header, rows = _read_csv(outs["classpath"])
    assert header == CLASSPATH_HEADER
    for row in rows:
        codes = row[7]
        if codes:
            parts = codes.split(";")
            assert parts == sorted(parts)


def test_mediation_csv_header_sort_and_selected_by_values(tmp_path):
    """mediation.csv must be sorted by coord and use allowed selected_by values."""
    data = _copy_data(tmp_path)
    outs = _default_out(tmp_path)
    assert _run(data, outs).returncode == 0
    header, rows = _read_csv(outs["mediation"])
    assert header == MEDIATION_HEADER
    coords = [r[0] for r in rows]
    assert coords == sorted(coords)
    allowed = {"root", "nearest", "bom", "highest"}
    for row in rows:
        assert row[3] in allowed


def test_findings_csv_header_and_stable_ids(tmp_path):
    """findings.csv must use documented header and F0001-style finding_id values."""
    data = _copy_data(tmp_path)
    outs = _default_out(tmp_path)
    assert _run(data, outs).returncode == 0
    header, rows = _read_csv(outs["findings"])
    assert header == FINDINGS_HEADER
    for idx, row in enumerate(rows, start=1):
        assert row[0] == f"F{idx:04d}"


def test_by_reason_contains_all_zero_count_reasons(tmp_path):
    """by_reason must list all fifteen documented reasons, including zero counts."""
    data = _copy_data(tmp_path)
    outs = _default_out(tmp_path)
    assert _run(data, outs).returncode == 0
    audit = json.loads(outs["json"].read_text(encoding="utf-8"))
    assert set(audit["by_reason"]) == set(ALL_REASONS)


# --- Version, range, BOM (mediation-policy.md) ---


def test_semver_qualifier_ordering_and_highest_candidate(tmp_path):
    """Qualifiers sort after releases and highest candidate is selected inside a range."""
    data, outs = _minimal_bundle(tmp_path)
    roots = '[{:coord "org.demo:api" :version "[1.0.0,2.0.0)" :scope :compile :optional false :exclusions []}]'
    repo = (
        '{"org.demo:api" {"1.0.0-RC1" {:jar "repo/a.jar" :sha256 "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" '
        ':license "MIT" :deps []} "1.0.0" {:jar "repo/b.jar" :sha256 "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" '
        ':license "MIT" :deps []}}}'
    )
    (data / "roots.edn").write_text(roots, encoding="utf-8")
    (data / "local_repo.edn").write_text(repo, encoding="utf-8")
    (data / "bom.edn").write_text("{}", encoding="utf-8")
    (data / "checksums.csv").write_text(
        "coord,version,sha256\norg.demo:api,1.0.0,bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n",
        encoding="utf-8",
    )
    assert _run(data, outs).returncode == 0
    _, med = _read_csv(outs["mediation"])
    api = next(r for r in med if r[0] == "org.demo:api")
    assert api[2] == "1.0.0"


def test_inclusive_exclusive_version_range_boundaries(tmp_path):
    """Range boundaries follow inclusive/exclusive rules from mediation-policy.md."""
    data, outs = _minimal_bundle(tmp_path)
    roots = '[{:coord "org.demo:api" :version "[1.0.0,2.0.0)" :scope :compile :optional false :exclusions []}]'
    repo = (
        '{"org.demo:api" {"1.0.0" {:jar "repo/a.jar" :sha256 "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" '
        ':license "MIT" :deps []} "2.0.0" {:jar "repo/b.jar" :sha256 "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" '
        ':license "MIT" :deps []}}}'
    )
    (data / "roots.edn").write_text(roots, encoding="utf-8")
    (data / "local_repo.edn").write_text(repo, encoding="utf-8")
    (data / "bom.edn").write_text("{}", encoding="utf-8")
    (data / "checksums.csv").write_text(
        "coord,version,sha256\norg.demo:api,1.0.0,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n",
        encoding="utf-8",
    )
    assert _run(data, outs).returncode == 0
    _, med = _read_csv(outs["mediation"])
    assert next(r for r in med if r[0] == "org.demo:api")[2] == "1.0.0"


def test_bom_exact_version_applies_inside_requested_range(tmp_path):
    """BOM exact pin applies when the version lies inside the dependency range."""
    data, outs = _minimal_bundle(tmp_path)
    shutil.copy(APP / "examples" / "bom-range" / "roots.edn", data / "roots.edn")
    shutil.copy(APP / "examples" / "bom-range" / "bom.edn", data / "bom.edn")
    repo = (
        '{"org.demo:api" {"1.2.0" {:jar "repo/api.jar" :sha256 "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" '
        ':license "MIT" :deps [{:coord "org.demo:core" :version "[1.0.0,2.0.0)" :scope :compile :optional false}]}} '
        '"org.demo:core" {"1.5.0" {:jar "repo/c1.jar" :sha256 "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" :license "MIT" :deps []} '
        '"1.8.0" {:jar "repo/c2.jar" :sha256 "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc" :license "MIT" :deps []}}}'
    )
    (data / "local_repo.edn").write_text(repo, encoding="utf-8")
    (data / "checksums.csv").write_text(
        "coord,version,sha256\n"
        "org.demo:api,1.2.0,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        "org.demo:core,1.8.0,cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\n",
        encoding="utf-8",
    )
    assert _run(data, outs).returncode == 0
    _, med = _read_csv(outs["mediation"])
    core = next(r for r in med if r[0] == "org.demo:core")
    assert core[2] == "1.8.0"
    assert core[3] == "bom"


def test_bom_outside_range_is_rejected_and_reported(tmp_path):
    """BOM exact pin outside dependency range reports bom_override_rejected."""
    data, outs = _minimal_bundle(tmp_path)
    roots = '[{:coord "org.demo:api" :version "1.0.0" :scope :compile :optional false :exclusions []}]'
    repo = (
        '{"org.demo:api" {"1.0.0" {:jar "repo/api.jar" :sha256 "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" '
        ':license "MIT" :deps [{:coord "org.demo:core" :version "[1.0.0,1.5.0)" :scope :compile :optional false}]}} '
        '"org.demo:core" {"1.4.0" {:jar "repo/c1.jar" :sha256 "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" :license "MIT" :deps []} '
        '"1.6.0" {:jar "repo/c2.jar" :sha256 "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc" :license "MIT" :deps []}}}'
    )
    (data / "roots.edn").write_text(roots, encoding="utf-8")
    (data / "local_repo.edn").write_text(repo, encoding="utf-8")
    (data / "bom.edn").write_text('{"org.demo:core" "1.9.0"}', encoding="utf-8")
    (data / "checksums.csv").write_text(
        "coord,version,sha256\n"
        "org.demo:api,1.0.0,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        "org.demo:core,1.4.0,bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n",
        encoding="utf-8",
    )
    assert _run(data, outs).returncode == 0
    _, findings = _read_csv(outs["findings"])
    assert any(r[1] == "bom_override_rejected" for r in findings)


# --- Interaction tests (mediation-policy.md) ---


def test_nearest_wins_over_higher_transitive_version(tmp_path):
    """Nearest-wins prefers the shallower request over a deeper higher version."""
    data, outs = _minimal_bundle(tmp_path)
    roots = (
        "[{:coord \"org.alpha:gateway\" :version \"1.0.0\" :scope :compile :optional false :exclusions []} "
        "{:coord \"org.beta:app\" :version \"1.0.0\" :scope :compile :optional false :exclusions []}]"
    )
    repo = (
        '{"org.alpha:gateway" {"1.0.0" {:jar "repo/g.jar" :sha256 "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" '
        ':license "MIT" :deps [{:coord "org.shared:lib" :version "1.5.0" :scope :compile :optional false}]}} '
        '"org.beta:app" {"1.0.0" {:jar "repo/a.jar" :sha256 "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" '
        ':license "MIT" :deps [{:coord "org.beta:middle" :version "1.0.0" :scope :compile :optional false}]}} '
        '"org.beta:middle" {"1.0.0" {:jar "repo/m.jar" :sha256 "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" '
        ':license "MIT" :deps [{:coord "org.shared:lib" :version "1.9.0" :scope :compile :optional false}]}} '
        '"org.shared:lib" {"1.5.0" {:jar "repo/l1.jar" :sha256 "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc" :license "MIT" :deps []} '
        '"1.9.0" {:jar "repo/l2.jar" :sha256 "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd" :license "MIT" :deps []}}}'
    )
    (data / "roots.edn").write_text(roots, encoding="utf-8")
    (data / "local_repo.edn").write_text(repo, encoding="utf-8")
    (data / "bom.edn").write_text("{}", encoding="utf-8")
    (data / "checksums.csv").write_text(
        "coord,version,sha256\n"
        "org.alpha:gateway,1.0.0,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        "org.beta:app,1.0.0,bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
        "org.beta:middle,1.0.0,eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee\n"
        "org.shared:lib,1.5.0,cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\n"
        "org.shared:lib,1.9.0,dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd\n",
        encoding="utf-8",
    )
    assert _run(data, outs).returncode == 0
    _, med = _read_csv(outs["mediation"])
    lib = next(r for r in med if r[0] == "org.shared:lib")
    assert lib[2] == "1.5.0"


def test_nearest_tie_chooses_highest_version_then_coord(tmp_path):
    """Equal-depth ties choose the highest version, then lexicographic coordinate."""
    data, outs = _minimal_bundle(tmp_path)
    roots = (
        "[{:coord \"org.alpha:a\" :version \"1.0.0\" :scope :compile :optional false :exclusions []} "
        "{:coord \"org.beta:b\" :version \"1.0.0\" :scope :compile :optional false :exclusions []}]"
    )
    repo = (
        '{"org.alpha:a" {"1.0.0" {:jar "repo/a.jar" :sha256 "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" '
        ':license "MIT" :deps [{:coord "org.shared:x" :version "1.2.0" :scope :compile :optional false}]}} '
        '"org.beta:b" {"1.0.0" {:jar "repo/b.jar" :sha256 "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" '
        ':license "MIT" :deps [{:coord "org.shared:x" :version "1.8.0" :scope :compile :optional false}]}} '
        '"org.shared:x" {"1.2.0" {:jar "repo/x1.jar" :sha256 "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc" :license "MIT" :deps []} '
        '"1.8.0" {:jar "repo/x2.jar" :sha256 "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd" :license "MIT" :deps []}}}'
    )
    (data / "roots.edn").write_text(roots, encoding="utf-8")
    (data / "local_repo.edn").write_text(repo, encoding="utf-8")
    (data / "bom.edn").write_text("{}", encoding="utf-8")
    (data / "checksums.csv").write_text(
        "coord,version,sha256\n"
        "org.alpha:a,1.0.0,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        "org.beta:b,1.0.0,bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
        "org.shared:x,1.8.0,dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd\n",
        encoding="utf-8",
    )
    assert _run(data, outs).returncode == 0
    _, med = _read_csv(outs["mediation"])
    assert next(r for r in med if r[0] == "org.shared:x")[2] == "1.8.0"


def test_transitive_exclusion_blocks_relocated_artifact(tmp_path):
    """Root exclusions block relocated transitive artifacts."""
    data, outs = _minimal_bundle(tmp_path)
    shutil.copy(APP / "examples" / "exclusions" / "roots.edn", data / "roots.edn")
    shutil.copy(APP / "examples" / "exclusions" / "local_repo.edn", data / "local_repo.edn")
    (data / "bom.edn").write_text("{}", encoding="utf-8")
    (data / "relocations.csv").write_text(
        "from_coord,to_coord,reason\norg.demo:blocked,org.demo:shadow,rename\n", encoding="utf-8"
    )
    (data / "checksums.csv").write_text(
        "coord,version,sha256\n"
        "org.demo:parent,1.0.0,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        "org.demo:kept,1.0.0,cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\n",
        encoding="utf-8",
    )
    assert _run(data, outs).returncode == 0
    _, med = _read_csv(outs["mediation"])
    coords = {r[0] for r in med}
    assert "org.demo:shadow" not in coords
    assert "org.demo:kept" in coords


def test_optional_dependency_pruned_unless_root(tmp_path):
    """Optional dependencies are pruned unless declared as roots."""
    data, outs = _minimal_bundle(tmp_path)
    roots = '[{:coord "org.demo:parent" :version "1.0.0" :scope :compile :optional false :exclusions []}]'
    repo = (
        '{"org.demo:parent" {"1.0.0" {:jar "repo/p.jar" :sha256 "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" '
        ':license "MIT" :deps [{:coord "org.demo:opt" :version "1.0.0" :scope :compile :optional true}]}} '
        '"org.demo:opt" {"1.0.0" {:jar "repo/o.jar" :sha256 "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" :license "MIT" :deps []}}}'
    )
    (data / "roots.edn").write_text(roots, encoding="utf-8")
    (data / "local_repo.edn").write_text(repo, encoding="utf-8")
    (data / "bom.edn").write_text("{}", encoding="utf-8")
    (data / "checksums.csv").write_text(
        "coord,version,sha256\norg.demo:parent,1.0.0,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n",
        encoding="utf-8",
    )
    assert _run(data, outs).returncode == 0
    _, med = _read_csv(outs["mediation"])
    assert "org.demo:opt" not in {r[0] for r in med}


def test_scope_propagation_uses_earlier_scope_order(tmp_path):
    """Scope propagation keeps the earlier scope from scope-order."""
    data, outs = _minimal_bundle(tmp_path)
    roots = (
        "[{:coord \"org.alpha:api\" :version \"1.0.0\" :scope :compile :optional false :exclusions []} "
        "{:coord \"org.beta:api\" :version \"1.0.0\" :scope :compile :optional false :exclusions []}]"
    )
    repo = (
        '{"org.alpha:api" {"1.0.0" {:jar "repo/a.jar" :sha256 "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" '
        ':license "MIT" :deps [{:coord "org.demo:core" :version "1.0.0" :scope :runtime :optional false}]}} '
        '"org.beta:api" {"1.0.0" {:jar "repo/b.jar" :sha256 "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" '
        ':license "MIT" :deps [{:coord "org.demo:core" :version "1.0.0" :scope :compile :optional false}]}} '
        '"org.demo:core" {"1.0.0" {:jar "repo/core.jar" :sha256 "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc" :license "MIT" :deps []}}}'
    )
    (data / "roots.edn").write_text(roots, encoding="utf-8")
    (data / "local_repo.edn").write_text(repo, encoding="utf-8")
    (data / "bom.edn").write_text("{}", encoding="utf-8")
    (data / "checksums.csv").write_text(
        "coord,version,sha256\n"
        "org.alpha:api,1.0.0,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        "org.beta:api,1.0.0,bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
        "org.demo:core,1.0.0,cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\n",
        encoding="utf-8",
    )
    assert _run(data, outs).returncode == 0
    _, med = _read_csv(outs["mediation"])
    core = next(r for r in med if r[0] == "org.demo:core")
    assert core[5] == "compile"


def test_scope_excluded_artifact_appears_in_mediation_not_classpath(tmp_path):
    """Artifacts outside include-scopes appear in mediation but not classpath.csv."""
    data = _copy_data(tmp_path)
    outs = _default_out(tmp_path)
    assert _run(data, outs).returncode == 0
    _, med = _read_csv(outs["mediation"])
    _, cp = _read_csv(outs["classpath"])
    med_coords = {r[0] for r in med if r[2]}
    cp_coords = {r[1] for r in cp}
    assert "org.demo:probe" in med_coords
    assert "org.demo:probe" not in cp_coords


def test_relocation_chain_updates_original_coords(tmp_path):
    """Relocation chains record all original coordinates in mediation.csv."""
    data, outs = _minimal_bundle(tmp_path)
    roots = '[{:coord "org.old:a" :version "1.0.0" :scope :compile :optional false :exclusions []}]'
    shutil.copy(APP / "examples" / "relocation-chain" / "local_repo.edn", data / "local_repo.edn")
    shutil.copy(APP / "examples" / "relocation-chain" / "relocations.csv", data / "relocations.csv")
    (data / "roots.edn").write_text(roots, encoding="utf-8")
    (data / "bom.edn").write_text("{}", encoding="utf-8")
    (data / "checksums.csv").write_text(
        "coord,version,sha256\norg.final:a,1.0.0,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n",
        encoding="utf-8",
    )
    assert _run(data, outs).returncode == 0
    _, med = _read_csv(outs["mediation"])
    row = next(r for r in med if r[0] == "org.final:a")
    originals = set(row[6].split(";"))
    assert originals == {"org.final:a", "org.new:a", "org.old:a"}


def test_checksum_mismatch_report_mode_is_nonfatal(tmp_path):
    """checksum-mode :report emits checksum_mismatch findings but exits zero."""
    data = _copy_data(tmp_path)
    outs = _default_out(tmp_path)
    result = _run(data, outs)
    assert result.returncode == 0
    _, findings = _read_csv(outs["findings"])
    assert any(r[1] == "checksum_mismatch" for r in findings)


def test_checksum_mismatch_fatal_mode_exits_without_outputs(tmp_path):
    """checksum-mode :fatal treats checksum_mismatch as fatal with no outputs."""
    data = _copy_data(tmp_path)
    cfg = (data / "mediation_config.edn").read_text(encoding="utf-8").replace(":report", ":fatal")
    (data / "mediation_config.edn").write_text(cfg, encoding="utf-8")
    outs = _default_out(tmp_path)
    result = _run(data, outs)
    assert result.returncode != 0
    assert not outs["json"].exists()
    assert not outs["classpath"].exists()
    assert not outs["mediation"].exists()
    assert not outs["findings"].exists()


def test_denied_license_is_reportable_not_fatal(tmp_path):
    """Denied licenses produce license_denied findings without failing the run."""
    data = _copy_data(tmp_path)
    outs = _default_out(tmp_path)
    assert _run(data, outs).returncode == 0
    _, findings = _read_csv(outs["findings"])
    assert any(r[1] == "license_denied" for r in findings)


def test_unknown_license_creates_warning(tmp_path):
    """Licenses missing from policy produce license_unknown warnings."""
    data, outs = _minimal_bundle(tmp_path)
    roots = '[{:coord "org.demo:api" :version "1.0.0" :scope :compile :optional false :exclusions []}]'
    repo = (
        '{"org.demo:api" {"1.0.0" {:jar "repo/api.jar" :sha256 "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" '
        ':license "Custom-License" :deps []}}}'
    )
    (data / "roots.edn").write_text(roots, encoding="utf-8")
    (data / "local_repo.edn").write_text(repo, encoding="utf-8")
    (data / "bom.edn").write_text("{}", encoding="utf-8")
    (data / "checksums.csv").write_text(
        "coord,version,sha256\norg.demo:api,1.0.0,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n",
        encoding="utf-8",
    )
    assert _run(data, outs).returncode == 0
    _, findings = _read_csv(outs["findings"])
    assert any(r[1] == "license_unknown" and r[2] == "warning" for r in findings)


def test_range_conflict_is_reportable_not_fatal(tmp_path):
    """Impossible exact version intersection reports range_conflict and exits zero."""
    data, outs = _minimal_bundle(tmp_path)
    roots = (
        "[{:coord \"org.alpha:a\" :version \"1.0.0\" :scope :compile :optional false :exclusions []} "
        "{:coord \"org.beta:b\" :version \"1.0.0\" :scope :compile :optional false :exclusions []}]"
    )
    repo = (
        '{"org.alpha:a" {"1.0.0" {:jar "repo/a.jar" :sha256 "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" '
        ':license "MIT" :deps [{:coord "org.shared:x" :version "1.2.0" :scope :compile :optional false}]}} '
        '"org.beta:b" {"1.0.0" {:jar "repo/b.jar" :sha256 "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" '
        ':license "MIT" :deps [{:coord "org.shared:x" :version "1.8.0" :scope :compile :optional false}]}} '
        '"org.shared:x" {"1.5.0" {:jar "repo/x1.jar" :sha256 "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc" :license "MIT" :deps []}}}'
    )
    (data / "roots.edn").write_text(roots, encoding="utf-8")
    (data / "local_repo.edn").write_text(repo, encoding="utf-8")
    (data / "bom.edn").write_text("{}", encoding="utf-8")
    (data / "checksums.csv").write_text(
        "coord,version,sha256\n"
        "org.alpha:a,1.0.0,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        "org.beta:b,1.0.0,bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n",
        encoding="utf-8",
    )
    result = _run(data, outs)
    assert result.returncode == 0, result.stderr + result.stdout
    _, findings = _read_csv(outs["findings"])
    assert any(r[1] == "range_conflict" and r[2] == "error" for r in findings)
    _, med = _read_csv(outs["mediation"])
    shared = next(r for r in med if r[0] == "org.shared:x")
    assert shared[2] == ""
    assert "range_conflict" in shared[7]


def test_classpath_topological_order_is_deterministic(tmp_path):
    """Classpath order is deterministic and respects dependency edges."""
    data = _copy_data(tmp_path)
    outs = _default_out(tmp_path)
    assert _run(data, outs).returncode == 0
    _, cp = _read_csv(outs["classpath"])
    orders = [r[0] for r in cp]
    assert orders == sorted(orders, key=lambda x: int(x[2:]))
    coords = [r[1] for r in cp]
    if "org.alpha:core" in coords and "org.alpha:gateway" in coords:
        assert coords.index("org.alpha:core") < coords.index("org.alpha:gateway")


# --- Adversarial / anti-shortcut tests ---


def test_reordering_inputs_produces_byte_identical_outputs(tmp_path):
    """Reordering EDN map and CSV rows without semantic change yields identical bytes."""
    data1 = _copy_data(tmp_path / "a")
    data2 = _copy_data(tmp_path / "b")
    outs1 = _default_out(tmp_path / "a")
    outs2 = _default_out(tmp_path / "b")

    rel_lines = (data2 / "relocations.csv").read_text(encoding="utf-8").splitlines()
    (data2 / "relocations.csv").write_text(
        "\n".join([rel_lines[0]] + list(reversed(rel_lines[1:]))) + "\n", encoding="utf-8"
    )

    chk_lines = (data2 / "checksums.csv").read_text(encoding="utf-8").splitlines()
    if len(chk_lines) > 2:
        (data2 / "checksums.csv").write_text(
            "\n".join([chk_lines[0]] + list(reversed(chk_lines[1:]))) + "\n", encoding="utf-8"
        )

    assert _run(data1, outs1).returncode == 0
    assert _run(data2, outs2).returncode == 0
    _assert_bundle_bytes_equal(outs1, outs2)


def test_irrelevant_unreachable_artifacts_do_not_change_outputs(tmp_path):
    """Unreachable repository artifacts must not change mediation output bytes."""
    data1 = _copy_data(tmp_path / "a")
    data2 = _copy_data(tmp_path / "b")
    outs1 = _default_out(tmp_path / "a")
    outs2 = _default_out(tmp_path / "b")

    repo_text = (data2 / "local_repo.edn").read_text(encoding="utf-8")
    extra = (
        ' "org.zoo:noise" {"9.9.9" {:jar "repo/noise.jar" '
        ':sha256 "9999999999999999999999999999999999999999999999999999999999999999" '
        ':license "MIT" :deps []}}'
    )
    (data2 / "local_repo.edn").write_text(repo_text.rstrip()[:-1] + extra + "}", encoding="utf-8")

    assert _run(data1, outs1).returncode == 0
    assert _run(data2, outs2).returncode == 0
    _assert_bundle_bytes_equal(outs1, outs2)


def test_cross_output_invariants_match_counts_and_references(tmp_path):
    """Cross-output invariants tie audit counts to CSV rows and coord references."""
    data = _copy_data(tmp_path)
    outs = _default_out(tmp_path)
    assert _run(data, outs).returncode == 0
    audit = json.loads(outs["json"].read_text(encoding="utf-8"))
    _, cp = _read_csv(outs["classpath"])
    _, med = _read_csv(outs["mediation"])
    _, findings = _read_csv(outs["findings"])
    assert audit["summary"]["classpath_count"] == len(cp)
    assert audit["summary"]["finding_count"] == len(findings)
    selected = [r for r in med if r[2]]
    assert audit["summary"]["selected_count"] == len(selected)
    med_map = {r[0]: r[2] for r in med}
    for row in cp:
        assert med_map[row[1]] == row[2]
    observed = _reason_code_counts(findings, med, cp)
    for reason, count in audit["by_reason"].items():
        if count:
            assert observed.get(reason, 0) == count


def test_repeated_runs_are_byte_identical(tmp_path):
    """Repeated CLI runs against the same inputs produce byte-identical outputs."""
    data = _copy_data(tmp_path)
    outs = _default_out(tmp_path / "run")
    first = {
        "json": outs["json"],
        "classpath": outs["classpath"],
        "mediation": outs["mediation"],
        "findings": outs["findings"],
    }
    assert _run(data, first).returncode == 0
    bytes1 = {k: first[k].read_bytes() for k in first}
    assert _run(data, first).returncode == 0
    bytes2 = {k: first[k].read_bytes() for k in first}
    assert bytes1 == bytes2


# --- Fatal validation tests (reason/severity table) ---


def test_duplicate_checksum_primary_key_exits_nonzero_without_outputs(tmp_path):
    """Duplicate checksum coord:version rows are fatal and must not create outputs."""
    data, outs = _minimal_bundle(tmp_path)
    _prepare_clean_direct_bundle(data)
    (data / "checksums.csv").write_text(
        "coord,version,sha256\n"
        "org.demo:api,1.2.3,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        "org.demo:api,1.2.3,bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n",
        encoding="utf-8",
    )
    _assert_fatal_without_outputs(data, outs)


def test_duplicate_version_in_local_repo_exits_nonzero_without_outputs(tmp_path):
    """Duplicate artifact versions in local_repo.edn are fatal per fixtures/malformed_duplicate_artifact.edn."""
    data, outs = _minimal_bundle(tmp_path)
    _prepare_clean_direct_bundle(data)
    shutil.copy(APP / "fixtures" / "malformed_duplicate_artifact.edn", data / "local_repo.edn")
    _assert_fatal_without_outputs(data, outs)


def test_invalid_range_in_roots_exits_nonzero_without_outputs(tmp_path):
    """Invalid root version ranges are fatal per fixtures/malformed_bad_range.edn."""
    data, outs = _minimal_bundle(tmp_path)
    _prepare_clean_direct_bundle(data)
    shutil.copy(APP / "fixtures" / "malformed_bad_range.edn", data / "roots.edn")
    _assert_fatal_without_outputs(data, outs)


def test_invalid_version_in_local_repo_exits_nonzero_without_outputs(tmp_path):
    """Invalid semver keys in local_repo.edn are fatal per fixtures/malformed_bad_version.edn."""
    data, outs = _minimal_bundle(tmp_path)
    _prepare_clean_direct_bundle(data)
    shutil.copy(APP / "fixtures" / "malformed_bad_version.edn", data / "local_repo.edn")
    _assert_fatal_without_outputs(data, outs)


def test_unknown_checksum_row_exits_nonzero_without_outputs(tmp_path):
    """Checksum rows for missing artifacts are fatal per fixtures/malformed_unknown_checksum.csv."""
    data, outs = _minimal_bundle(tmp_path)
    _prepare_clean_direct_bundle(data)
    shutil.copy(APP / "fixtures" / "malformed_unknown_checksum.csv", data / "checksums.csv")
    _assert_fatal_without_outputs(data, outs)


def test_schema_invalid_config_exits_nonzero_without_outputs(tmp_path):
    """Missing required mediation_config keys are fatal schema_invalid errors."""
    data, outs = _minimal_bundle(tmp_path)
    _prepare_clean_direct_bundle(data)
    (data / "mediation_config.edn").write_text("{:checksum-mode :report}", encoding="utf-8")
    _assert_fatal_without_outputs(data, outs)


def test_relocation_cycle_exits_nonzero_without_outputs(tmp_path):
    """Relocation cycles are fatal and must not create output files."""
    data, outs = _minimal_bundle(tmp_path)
    shutil.copy(APP / "fixtures" / "malformed_relocation_cycle.csv", data / "relocations.csv")
    shutil.copy(APP / "examples" / "clean-direct" / "roots.edn", data / "roots.edn")
    shutil.copy(APP / "examples" / "clean-direct" / "local_repo.edn", data / "local_repo.edn")
    (data / "checksums.csv").write_text(
        "coord,version,sha256\norg.demo:api,1.2.3,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n",
        encoding="utf-8",
    )
    result = _run(data, outs)
    assert result.returncode != 0
    assert not any(outs[k].exists() for k in outs)


def test_unresolved_required_artifact_exits_nonzero_without_outputs(tmp_path):
    """Missing required artifacts are fatal and must not create output files."""
    data, outs = _minimal_bundle(tmp_path)
    roots = '[{:coord "org.demo:api" :version "1.0.0" :scope :compile :optional false :exclusions []}]'
    repo = (
        '{"org.demo:api" {"1.0.0" {:jar "repo/api.jar" :sha256 "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" '
        ':license "MIT" :deps [{:coord "org.demo:missing" :version "9.9.9" :scope :compile :optional false}]}}}'
    )
    (data / "roots.edn").write_text(roots, encoding="utf-8")
    (data / "local_repo.edn").write_text(repo, encoding="utf-8")
    (data / "bom.edn").write_text("{}", encoding="utf-8")
    (data / "checksums.csv").write_text(
        "coord,version,sha256\norg.demo:api,1.0.0,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n",
        encoding="utf-8",
    )
    result = _run(data, outs)
    assert result.returncode != 0
    assert not any(outs[k].exists() for k in outs)
