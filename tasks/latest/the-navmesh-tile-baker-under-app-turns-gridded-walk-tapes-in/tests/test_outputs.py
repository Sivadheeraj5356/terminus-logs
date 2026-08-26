"""Verifier for navmesh-border-weld-resume-skew nav audit report."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from expected_fingerprints import (
    HIDDEN_REPORT_FP,
    HIDDEN_ROW_FP,
    MANIFEST_REPORT_FP,
    MANIFEST_ROW_FP,
    PROBE_ROW_FP,
)
from hidden_fixtures import load_hidden_fixtures

APP = Path(os.environ.get("TASK_APP_ROOT", "/app")).resolve()
REPORT = APP / "output" / "nav_audit.json"
MANIFEST = APP / "data" / "scenarios" / "manifest.tsv"
CHECKSUM_MANIFEST = APP / "doc" / "input_checksums.txt"
_TESTS_ROOT = Path(__file__).resolve().parent
_HIDDEN = load_hidden_fixtures()
BUILD_HOOK = APP / "ci/build_and_load.sh"
SCHEMA_STUB = APP / "stubs/schema_anchor.txt"
FROZEN_MANIFEST = APP / "doc/frozen_sources.txt"

ROW_KEYS = frozenset(
    {
        "scenario_id",
        "mode",
        "polygon_count",
        "border_weld_count",
        "nav_digest",
        "portal_count",
        "link_digest",
        "link_ok",
        "area_overlay_ok",
        "seam_open_count",
        "pair_ok",
        "finish_reason",
    }
)

PARITY_KEYS = (
    "polygon_count",
    "border_weld_count",
    "nav_digest",
    "portal_count",
    "link_digest",
    "link_ok",
    "area_overlay_ok",
    "seam_open_count",
)

ROW_FP_KEYS = (
    "scenario_id",
    "mode",
    "polygon_count",
    "border_weld_count",
    "nav_digest",
    "portal_count",
    "link_digest",
    "link_ok",
    "area_overlay_ok",
    "seam_open_count",
    "finish_reason",
)

RESUME_STRESS_IDS = frozenset(
    {
        "t_pad_shift",
        "t_mid_pause",
        "t_double_pause",
        "t_thin_border",
        "t_oblique",
        "t_layer_stack",
        "t_dual_lane",
    }
)

BORDER_SHIFT_IDS = frozenset({"t_pad_shift", "t_thin_border", "t_layer_stack"})

PAD_WEIGHTED_IDS = frozenset({"t_pad_shift", "t_thin_border"})

HIDDEN_STRESS_IDS = frozenset(
    {
        "h_serial_pause",
        "h_pad_sphere",
        "h_stack_dual",
        "h_thin_resume",
        "h_triple_pause",
        "h_mid_pad_shift",
        "h_oblique_pad",
        "h_wedge_stack",
        "h_dp_p1",
        "h_iso_e1",
    }
)

DECOY_PATHS = frozenset(
    {
        "ridge_o/decoy_lane.c",
        "lattice_p/decoy_fold.c",
        "decoy/vis_weld.c",
    }
)


def _sha256_file(path: Path) -> str:
    proc = subprocess.run(
        ["sha256sum", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.split()[0]


def _load_sha256_manifest(manifest: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for ln in manifest.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        digest, rel = ln.split(None, 1)
        entries[rel.strip()] = digest.strip()
    return entries


def _load_manifest_rows_from_text(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        sid, tape = ln.split(None, 1)
        rows.append((sid.strip(), tape.strip()))
    return rows


def _load_manifest_rows() -> list[tuple[str, str]]:
    return _load_manifest_rows_from_text(MANIFEST.read_text(encoding="utf-8"))


def _manifest_scenario_ids() -> list[str]:
    return [sid for sid, _ in _load_manifest_rows()]


def _row_fp(row: dict[str, Any]) -> str:
    payload = {k: row[k] for k in ROW_FP_KEYS}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _report_fp(report: dict[str, Any]) -> str:
    body = {
        "scenarios": [{k: r[k] for k in ROW_FP_KEYS} for r in report["scenarios"]],
        "summary": {
            "scenario_count": report["summary"]["scenario_count"],
            "scenario_rows": report["summary"]["scenario_rows"],
            "pair_mismatch_count": report["summary"]["pair_mismatch_count"],
            "link_fail_total": report["summary"]["link_fail_total"],
            "seam_open_total": report["summary"]["seam_open_total"],
        },
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _assert_row_fp(row: dict[str, Any], expected: str, label: str) -> None:
    assert _row_fp(row) == expected, label


def _run_with_extra_scenarios(
    extra_manifest_text: str,
    extra_tapes: dict[str, str],
) -> dict[str, Any]:
    """Append verifier-only input tapes from in-memory fixtures, run the hook."""
    manifest_path = APP / "data" / "scenarios" / "manifest.tsv"
    tape_dir = APP / "data" / "tapes"
    orig_manifest = manifest_path.read_text(encoding="utf-8")
    copied_tapes: list[Path] = []
    try:
        extra_lines: list[str] = []
        for sid, tape_stem in _load_manifest_rows_from_text(extra_manifest_text):
            tape_name = f"{tape_stem}.tape"
            assert tape_name in extra_tapes, tape_name
            dst = tape_dir / tape_name
            dst.write_text(extra_tapes[tape_name], encoding="utf-8")
            copied_tapes.append(dst)
            extra_lines.append(f"{sid}\t{tape_stem}")
        manifest_path.write_text(
            orig_manifest.rstrip("\n") + "\n" + "\n".join(extra_lines) + "\n",
            encoding="utf-8",
        )
        subprocess.run([str(BUILD_HOOK)], check=True, cwd=APP)
        return json.loads(REPORT.read_text(encoding="utf-8"))
    finally:
        manifest_path.write_text(orig_manifest, encoding="utf-8")
        for tape_path in copied_tapes:
            if tape_path.exists():
                tape_path.unlink()
        subprocess.run([str(BUILD_HOOK)], check=True, cwd=APP)


def _filter_report_rows(report: dict[str, Any], scenario_ids: set[str]) -> dict[str, Any]:
    rows = [r for r in report["scenarios"] if r["scenario_id"] in scenario_ids]
    pair_fail = 0
    link_fail = sum(1 for r in rows if not r["link_ok"])
    seam_total = sum(r["seam_open_count"] for r in rows)
    for i in range(0, len(rows), 2):
        cont = rows[i]
        pause = rows[i + 1]
        ok = all(cont[k] == pause[k] for k in PARITY_KEYS)
        cont["pair_ok"] = ok
        pause["pair_ok"] = ok
        if not ok:
            pair_fail += 1
    return {
        "schema_anchor": report["schema_anchor"],
        "scenarios": rows,
        "summary": {
            "scenario_count": len(rows) // 2,
            "scenario_rows": len(rows),
            "pair_mismatch_count": pair_fail,
            "link_fail_total": link_fail,
            "seam_open_total": seam_total,
        },
    }


@pytest.fixture(scope="session")
def built_report() -> dict[str, Any]:
    """Build the matrix binary and load the emitted audit report."""
    subprocess.run([str(BUILD_HOOK)], check=True, cwd=APP)
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def hidden_report(built_report: dict[str, Any]) -> dict[str, Any]:
    """Execute verifier-only hidden input scenarios after the main manifest build."""
    _ = built_report
    full = _run_with_extra_scenarios(_HIDDEN["hidden_manifest"], _HIDDEN["hidden_tapes"])
    return _filter_report_rows(full, HIDDEN_STRESS_IDS)


def test_agent_tree_has_no_gold_answer_key() -> None:
    """The agent image must not ship verifier gold answer keys."""
    assert not (APP / "doc/gold_audit_rows.tsv").exists()
    assert not (APP / "doc/verifier_payload.py").exists()


def test_no_verifier_artifacts_in_agent_tree() -> None:
    """Verifier-only manifests must not be present under /app."""
    assert not (APP / "doc/shipped_impl_manifest.txt").exists()
    assert not (APP / "construction_manifest.json").exists()


def test_no_decodable_gold_preimages_on_tests_mount() -> None:
    """Decodable gold preimages must not sit on the verifier mount."""
    for name in (
        "gold_audit_rows.tsv",
        "hidden_gold_audit_rows.tsv",
        "probe_gold_audit_rows.tsv",
        "probe2_gold_audit_rows.tsv",
        "probe3_gold_audit_rows.tsv",
        "probe4_gold_audit_rows.tsv",
        "probe5_gold_audit_rows.tsv",
        "verifier_payload.py",
    ):
        assert not (_TESTS_ROOT / name).exists(), name
    assert not (_TESTS_ROOT / "hidden").exists()


def test_build_hook_exists() -> None:
    """The build hook path named in the instruction must exist."""
    assert BUILD_HOOK.is_file()


def test_frozen_inputs_unchanged() -> None:
    """Scenario tapes and checksum-pinned inputs must remain untouched."""
    expected = _load_sha256_manifest(CHECKSUM_MANIFEST)
    for rel, digest in expected.items():
        path = APP / rel
        assert path.is_file(), rel
        assert _sha256_file(path) == digest, rel


def test_frozen_sources_unchanged() -> None:
    """Frozen harness sources listed in doc/frozen_sources.txt must remain present."""
    for ln in FROZEN_MANIFEST.read_text(encoding="utf-8").splitlines():
        rel = ln.strip()
        if not rel or rel.startswith("#"):
            continue
        path = APP / rel
        assert path.is_file(), rel


def test_decoy_modules_unchanged() -> None:
    """Decoy helper modules outside the shipped manifest must remain untouched."""
    expected = _load_sha256_manifest(CHECKSUM_MANIFEST)
    for rel in DECOY_PATHS:
        assert rel in expected
        assert _sha256_file(APP / rel) == expected[rel], rel


def test_report_schema(built_report: dict[str, Any]) -> None:
    """The audit report must expose the documented top-level schema."""
    assert built_report["schema_anchor"] == int(SCHEMA_STUB.read_text(encoding="utf-8").strip())
    assert set(built_report.keys()) == {"schema_anchor", "scenarios", "summary"}
    for row in built_report["scenarios"]:
        assert set(row.keys()) == ROW_KEYS


def test_manifest_order(built_report: dict[str, Any]) -> None:
    """Scenario rows must follow manifest order with continuous then pause_resume pairs."""
    expected: list[str] = []
    for sid in _manifest_scenario_ids():
        expected.extend([sid, sid])
    got = [r["scenario_id"] for r in built_report["scenarios"]]
    assert got == expected
    modes = [r["mode"] for r in built_report["scenarios"]]
    assert modes.count("continuous") == modes.count("pause_resume")


def test_report_matches_gold(built_report: dict[str, Any]) -> None:
    """Built audit output must match the committed reference fingerprint."""
    assert _report_fp(built_report) == MANIFEST_REPORT_FP


def test_summary_counters(built_report: dict[str, Any]) -> None:
    """Summary counters must reflect a fully paired, link-clean audit."""
    summary = built_report["summary"]
    assert summary["scenario_count"] == len(_manifest_scenario_ids())
    assert summary["scenario_rows"] == len(built_report["scenarios"])
    assert summary["pair_mismatch_count"] == 0
    assert summary["link_fail_total"] == 0
    assert summary["seam_open_total"] == 0


@pytest.mark.parametrize("scenario_id", _manifest_scenario_ids())
def test_manifest_scenario_rows(built_report: dict[str, Any], scenario_id: str) -> None:
    """Every manifest scenario must match the committed row fingerprint for both modes."""
    for mode in ("continuous", "pause_resume"):
        built = next(
            r
            for r in built_report["scenarios"]
            if r["scenario_id"] == scenario_id and r["mode"] == mode
        )
        _assert_row_fp(built, MANIFEST_ROW_FP[scenario_id][mode], f"{scenario_id}/{mode}")


@pytest.mark.parametrize("scenario_id", sorted(RESUME_STRESS_IDS))
def test_resume_stress_scenarios(built_report: dict[str, Any], scenario_id: str) -> None:
    """Pause-resume stress tapes must stay paired and match committed fingerprints."""
    for mode in ("continuous", "pause_resume"):
        built = next(
            r
            for r in built_report["scenarios"]
            if r["scenario_id"] == scenario_id and r["mode"] == mode
        )
        _assert_row_fp(built, MANIFEST_ROW_FP[scenario_id][mode], f"{scenario_id}/{mode}")
        assert built["pair_ok"] is True
        assert built["link_ok"] is True
        assert built["area_overlay_ok"] is True


@pytest.mark.parametrize("scenario_id", sorted(BORDER_SHIFT_IDS))
def test_border_shift_scenarios_pair(built_report: dict[str, Any], scenario_id: str) -> None:
    """Pad-weighted or border-shifted scenarios must stay paired across both legs."""
    rows = [r for r in built_report["scenarios"] if r["scenario_id"] == scenario_id]
    assert len(rows) == 2
    assert rows[0]["pair_ok"] is True
    assert rows[1]["pair_ok"] is True
    for key in PARITY_KEYS:
        assert rows[0][key] == rows[1][key]


@pytest.mark.parametrize("scenario_id", sorted(PAD_WEIGHTED_IDS))
def test_pad_weighted_continuous_matches_gold(
    built_report: dict[str, Any], scenario_id: str
) -> None:
    """Pad-weighted continuous legs must match the committed fingerprint."""
    built = next(
        r
        for r in built_report["scenarios"]
        if r["scenario_id"] == scenario_id and r["mode"] == "continuous"
    )
    _assert_row_fp(built, MANIFEST_ROW_FP[scenario_id]["continuous"], f"{scenario_id}/continuous")


def test_pad_shift_link_digest_exact(built_report: dict[str, Any]) -> None:
    """Pad-shifted scenarios must match committed fingerprints on both legs."""
    for mode in ("continuous", "pause_resume"):
        built = next(
            r
            for r in built_report["scenarios"]
            if r["scenario_id"] == "t_pad_shift" and r["mode"] == mode
        )
        _assert_row_fp(built, MANIFEST_ROW_FP["t_pad_shift"][mode], f"t_pad_shift/{mode}")


def test_thin_border_absolute_digests(built_report: dict[str, Any]) -> None:
    """Pad=1 thin-border tapes must match committed fingerprints on both legs."""
    for mode in ("continuous", "pause_resume"):
        built = next(
            r
            for r in built_report["scenarios"]
            if r["scenario_id"] == "t_thin_border" and r["mode"] == mode
        )
        _assert_row_fp(built, MANIFEST_ROW_FP["t_thin_border"][mode], f"t_thin_border/{mode}")


def test_report_byte_stable(built_report: dict[str, Any]) -> None:
    """Repeated hook runs must emit byte-identical audit JSON."""
    first = REPORT.read_bytes()
    subprocess.run([str(BUILD_HOOK)], check=True, cwd=APP)
    second = REPORT.read_bytes()
    assert first == second


def test_matrix_binary_is_elf() -> None:
    """The matrix driver must build to a native executable image."""
    data = (APP / "bin" / "nav_matrix").read_bytes()
    assert data[:4] in (b"\x7fELF", b"\xcf\xfa\xed\xfe")


def test_pair_parity_fields(built_report: dict[str, Any]) -> None:
    """Continuous and pause_resume rows must agree on every parity field."""
    for i in range(0, len(built_report["scenarios"]), 2):
        cont = built_report["scenarios"][i]
        pause = built_report["scenarios"][i + 1]
        assert cont["scenario_id"] == pause["scenario_id"]
        for key in PARITY_KEYS:
            assert cont[key] == pause[key]
        assert cont["pair_ok"] is True
        assert pause["pair_ok"] is True


def test_finish_reason_ok(built_report: dict[str, Any]) -> None:
    """Every scenario row must finish with reason ok."""
    for row in built_report["scenarios"]:
        assert row["finish_reason"] == "ok"


def test_hidden_manifest_parity(hidden_report: dict[str, Any]) -> None:
    """Verifier-only hidden scenarios must match the committed fingerprint and stay paired."""
    assert _report_fp(hidden_report) == HIDDEN_REPORT_FP
    assert hidden_report["summary"]["pair_mismatch_count"] == 0


@pytest.mark.parametrize("scenario_id", sorted(HIDDEN_STRESS_IDS))
def test_hidden_scenario_rows(hidden_report: dict[str, Any], scenario_id: str) -> None:
    """Each hidden stress scenario must match committed fingerprints for both modes."""
    for mode in ("continuous", "pause_resume"):
        built = next(
            r
            for r in hidden_report["scenarios"]
            if r["scenario_id"] == scenario_id and r["mode"] == mode
        )
        _assert_row_fp(built, HIDDEN_ROW_FP[scenario_id][mode], f"hidden {scenario_id}/{mode}")
        assert built["pair_ok"] is True
        assert built["link_ok"] is True
        assert built["area_overlay_ok"] is True


def test_double_pause_seam_closed(built_report: dict[str, Any]) -> None:
    """t_double_pause must not leak seam gaps after resume repair."""
    rows = [r for r in built_report["scenarios"] if r["scenario_id"] == "t_double_pause"]
    for row in rows:
        assert row["seam_open_count"] == 0
        assert row["link_ok"] is True


def _assert_runtime_probe(scenario_id: str, tape_stem: str, tape_content: str) -> None:
    tape_dir = APP / "data" / "tapes"
    tape_path = tape_dir / f"{tape_stem}.tape"
    manifest_path = APP / "data" / "scenarios" / "manifest.tsv"
    orig_manifest = manifest_path.read_text(encoding="utf-8")
    try:
        tape_path.write_text(tape_content, encoding="utf-8")
        manifest_path.write_text(
            orig_manifest.rstrip("\n") + f"\n{scenario_id}\t{tape_stem}\n",
            encoding="utf-8",
        )
        subprocess.run([str(BUILD_HOOK)], check=True, cwd=APP)
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        probe_rows = [r for r in report["scenarios"] if r["scenario_id"] == scenario_id]
        assert len(probe_rows) == 2
        for mode in ("continuous", "pause_resume"):
            built = next(r for r in probe_rows if r["mode"] == mode)
            _assert_row_fp(built, PROBE_ROW_FP[scenario_id][mode], f"{scenario_id}/{mode}")
            assert built["pair_ok"] is True
            assert built["finish_reason"] == "ok"
    finally:
        manifest_path.write_text(orig_manifest, encoding="utf-8")
        if tape_path.exists():
            tape_path.unlink()
        subprocess.run([str(BUILD_HOOK)], check=True, cwd=APP)


def test_dynamic_tape_processing() -> None:
    """Binary must process a novel tape and match the committed probe fingerprint."""
    _assert_runtime_probe(
        "t_rt_p1",
        "t_rt_p1",
        (
            "# runtime-generated verification tape\n"
            "init nx=6 ny=6 nz=5 iso=50 pad=0\n"
            "box x0=1 y0=1 z0=1 x1=4 y1=4 z1=3 val=80\n"
            "slab z=2\n"
            "pause\n"
            "slab z=5\n"
        ),
    )


def test_dynamic_probe_pad_shift() -> None:
    """Runtime pad=1 sphere probe must match the committed fingerprint."""
    _assert_runtime_probe(
        "t_rt_p2",
        "t_rt_p2",
        (
            "# verifier-only pad-shift probe\n"
            "init nx=7 ny=7 nz=6 iso=60 pad=1\n"
            "sphere cx=3 cy=3 cz=3 r=2 val=60\n"
            "slab z=3\n"
            "pause\n"
            "slab z=6\n"
        ),
    )


def test_dynamic_probe_mid_pad() -> None:
    """Runtime probe with mid-tape pad change must match the committed fingerprint."""
    _assert_runtime_probe(
        "t_rt_p3",
        "t_rt_p3",
        (
            "# verifier-only mid-pad probe\n"
            "init nx=8 ny=8 nz=7 iso=110 pad=0\n"
            "box x0=2 y0=2 z0=1 x1=5 y1=5 z1=4 val=110\n"
            "slab z=3\n"
            "pad pad=1\n"
            "pause\n"
            "slab z=6\n"
        ),
    )


def test_dynamic_probe_triple_pause() -> None:
    """Runtime probe with chained pauses must match the committed fingerprint."""
    _assert_runtime_probe(
        "t_rt_p4",
        "t_rt_p4",
        (
            "# verifier-only triple-pause probe\n"
            "init nx=7 ny=7 nz=9 iso=85 pad=0\n"
            "sphere cx=3 cy=3 cz=4 r=2 val=130\n"
            "slab z=2\n"
            "pause\n"
            "slab z=5\n"
            "pause\n"
            "slab z=9\n"
        ),
    )


def test_dynamic_probe_pad_box() -> None:
    """Runtime pad-weighted box probe must match the committed fingerprint."""
    _assert_runtime_probe(
        "t_rt_p5",
        "t_rt_p5",
        (
            "# verifier-only pad-box probe\n"
            "init nx=9 ny=9 nz=8 iso=105 pad=1\n"
            "box x0=2 y0=2 z0=1 x1=6 y1=6 z1=5 val=105\n"
            "slab z=3\n"
            "pause\n"
            "slab z=7\n"
        ),
    )


def test_all_manifest_rows_seam_closed(built_report: dict[str, Any]) -> None:
    """Every manifest scenario row must close tile seams on both execution legs."""
    for row in built_report["scenarios"]:
        assert row["seam_open_count"] == 0, row["scenario_id"]
        assert row["area_overlay_ok"] is True
