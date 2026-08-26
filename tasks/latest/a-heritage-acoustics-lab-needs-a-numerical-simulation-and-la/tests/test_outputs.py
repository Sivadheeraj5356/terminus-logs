"""Numeric verifier for CT violin FDTD calibration closure, mesh staging, and spectral formants."""
from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
from pathlib import Path

import pytest

REPORTS = Path("/app/output/reports")
STATE = Path("/app/state")
CT_DIR = Path("/app/data/ct")
APP_REPORTS_ROOT = "/app/output/reports/"
APP_SUMMARY_JSON = "/app/output/reports/summary.json"
TOL_HZ = 5
PROFILES = ["amati_ct", "guarneri_ct"]
REFERENCE_FORMANTS = {
    "amati_ct": [895.179, 1180.008, 1586.908, 2075.187],
    "guarneri_ct": [935.869, 1302.078, 1790.357, 2360.017],
}
MIN_PROMINENCE = {"amati_ct": 6.0, "guarneri_ct": 6.0}
C_AIR = 343.0
C_WOOD = 1200.0
NX = 48
NY = 24


def _run_fdtd_assay(ct_dir: Path = CT_DIR, out_dir: Path = REPORTS) -> None:
    subprocess.run(["make", "-C", "/app/environment"], check=True)
    if out_dir.exists():
        for child in out_dir.iterdir():
            if child.is_dir():
                for f in child.glob("*"):
                    f.unlink()
            elif child.is_file():
                child.unlink()
    subprocess.run(
        [
            "/app/bin/reso_sim",
            "batch",
            "--ct",
            str(ct_dir),
            "--out",
            str(out_dir),
        ],
        check=True,
    )


@pytest.fixture(scope="session", autouse=True)
def _rebuild_and_simulate() -> None:
    Path("/app/state").mkdir(parents=True, exist_ok=True)
    _run_fdtd_assay()


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _sorted_formants(values: list[float]) -> list[float]:
    return sorted(float(v) for v in values)


def _formants_match(reported: list[float], reference: list[float]) -> bool:
    rep = _sorted_formants(reported)
    ref = _sorted_formants(reference)
    if len(rep) != len(ref):
        return False
    return all(abs(a - b) <= TOL_HZ for a, b in zip(rep, ref, strict=True))


def _read_ctb(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    nx, ny = struct.unpack_from("<II", data, 0)
    voxels = data[8 : 8 + nx * ny]
    return nx, ny, voxels


def reference_air_wood_counts(voxels: bytes) -> tuple[int, int]:
    air = sum(1 for v in voxels if v == 0)
    wood = len(voxels) - air
    return air, wood


def reference_speed_digest(voxels: bytes, nx: int, ny: int) -> str:
    parts: list[str] = []
    for y in range(ny):
        for x in range(nx):
            c = C_AIR if voxels[y * nx + x] == 0 else C_WOOD
            parts.append(f"{c:.6f},")
    return hashlib.sha256("".join(parts).encode()).hexdigest()


def _write_ctb(path: Path, cavity_w: int, cavity_h: int, cx: int, cy: int) -> None:
    voxels = bytearray(NX * NY)
    for y in range(NY):
        for x in range(NX):
            inside = (
                2 < x < NX - 3
                and 2 < y < NY - 3
                and abs(x - cx) <= cavity_w // 2
                and abs(y - cy) <= cavity_h // 2
            )
            voxels[y * NX + x] = 0 if inside else 1
    path.write_bytes(struct.pack("<II", NX, NY) + bytes(voxels))


def test_teb21dc_ct_input_directory_has_required_volumes() -> None:
    """CT assay inputs under /app/data/ct include both cavity volumes."""
    assert CT_DIR.is_dir()
    stems = {p.stem for p in CT_DIR.glob("*.ctb")}
    for name in PROFILES:
        assert name in stems


def test_teb21dc_reports_output_directory_exists() -> None:
    """Calibration export root holds summary.json after numerical batch."""
    assert REPORTS.is_dir()
    assert APP_REPORTS_ROOT.startswith("/app/output/reports")
    assert (REPORTS / "summary.json").is_file()
    assert APP_SUMMARY_JSON == str(REPORTS / "summary.json")


def test_teb21dc_summary_lists_both_profiles() -> None:
    """Batch closure inventory lists every CT stem in sorted order."""
    summary = _read_json(REPORTS / "summary.json")
    assert summary["profiles"] == sorted(PROFILES)
    assert summary["batch_digest"] == ",".join(sorted(PROFILES))


def test_teb21dc_amati_formant_report_schema() -> None:
    """amati_ct formants.json matches the documented spectral certificate schema."""
    doc = _read_json(REPORTS / "amati_ct" / "formants.json")
    assert doc["profile"] == "amati_ct"
    assert doc["sample_rate_hz"] == 83333
    assert doc["formant_count"] == 4
    assert len(doc["formants_hz"]) == 4
    assert isinstance(doc["peak_prominence_db"], (int, float))
    assert len(doc["pressure_digest"]) == 64
    assert len(doc["cavity_speed_digest"]) == 64


def test_teb21dc_guarneri_formant_report_schema() -> None:
    """guarneri_ct formants.json matches the documented spectral certificate schema."""
    doc = _read_json(REPORTS / "guarneri_ct" / "formants.json")
    assert doc["profile"] == "guarneri_ct"
    assert doc["sample_rate_hz"] == 83333
    assert doc["formant_count"] == 4
    assert len(doc["formants_hz"]) == 4
    assert isinstance(doc["peak_prominence_db"], (int, float))
    assert len(doc["pressure_digest"]) == 64
    assert len(doc["cavity_speed_digest"]) == 64


def test_teb21dc_amati_formants_match_reference_recording() -> None:
    """amati_ct formants_hz close within five hertz of lab calibration targets."""
    doc = _read_json(REPORTS / "amati_ct" / "formants.json")
    assert _formants_match(doc["formants_hz"], REFERENCE_FORMANTS["amati_ct"])


def test_teb21dc_guarneri_formants_match_reference_recording() -> None:
    """guarneri_ct formants_hz close within five hertz of lab calibration targets."""
    doc = _read_json(REPORTS / "guarneri_ct" / "formants.json")
    assert _formants_match(doc["formants_hz"], REFERENCE_FORMANTS["guarneri_ct"])


def test_teb21dc_amati_peak_prominence_meets_lab_floor() -> None:
    """amati strongest accepted peak meets absolute-dB prominence floor."""
    doc = _read_json(REPORTS / "amati_ct" / "formants.json")
    assert doc["peak_prominence_db"] >= MIN_PROMINENCE["amati_ct"]


def test_teb21dc_guarneri_peak_prominence_meets_lab_floor() -> None:
    """guarneri strongest accepted peak meets absolute-dB prominence floor."""
    doc = _read_json(REPORTS / "guarneri_ct" / "formants.json")
    assert doc["peak_prominence_db"] >= MIN_PROMINENCE["guarneri_ct"]


def _pressure_wav_ok(path: Path) -> bool:
    try:
        data = path.read_bytes()
    except OSError:
        return False
    header_len = 44
    min_payload = 200
    return (
        len(data) >= header_len + min_payload
        and data[0:4] == b"RIFF"
        and data[8:12] == b"WAVE"
        and data[22:24] == b"\x01\x00"
        and data[34:36] == b"\x10\x00"
    )


def test_teb21dc_amati_pressure_wav_is_mono_pcm() -> None:
    """amati microphone pressure.wav is mono 16-bit PCM per format contract."""
    assert _pressure_wav_ok(REPORTS / "amati_ct" / "pressure.wav")


def test_teb21dc_guarneri_pressure_wav_is_mono_pcm() -> None:
    """guarneri microphone pressure.wav is mono 16-bit PCM per format contract."""
    assert _pressure_wav_ok(REPORTS / "guarneri_ct" / "pressure.wav")


def test_teb21dc_amati_lowest_formant_below_guarneri_third() -> None:
    """Cross-profile spectral ordering from lab-closure-calibration-contract.md."""
    amati = _read_json(REPORTS / "amati_ct" / "formants.json")
    guarneri = _read_json(REPORTS / "guarneri_ct" / "formants.json")
    amati_min = min(amati["formants_hz"])
    guarneri_third = _sorted_formants(guarneri["formants_hz"])[2]
    assert amati_min < guarneri_third


def test_teb21dc_batch_covers_required_ct_inputs() -> None:
    """Numerical batch closed both CT stems listed under /app/data/ct."""
    summary = _read_json(REPORTS / "summary.json")
    ct_names = {p.stem for p in CT_DIR.glob("*.ctb")}
    for name in PROFILES:
        assert name in ct_names
        assert name in summary["profiles"]


def test_mesh01_amati_cavity_staging_schema() -> None:
    """amati cavity_mesh.json staging schema from cavity-mesh-staging.md."""
    doc = _read_json(STATE / "amati_ct" / "cavity_mesh.json")
    assert doc["profile"] == "amati_ct"
    assert doc["nx"] == NX and doc["ny"] == NY
    assert doc["protocol_epoch"] == 1
    assert len(doc["speed_digest"]) == 64
    assert isinstance(doc["air_cells"], int)
    assert isinstance(doc["wood_cells"], int)


def test_mesh02_guarneri_cavity_staging_schema() -> None:
    """guarneri cavity_mesh.json staging schema from cavity-mesh-staging.md."""
    doc = _read_json(STATE / "guarneri_ct" / "cavity_mesh.json")
    assert doc["profile"] == "guarneri_ct"
    assert doc["nx"] == NX and doc["ny"] == NY
    assert doc["protocol_epoch"] == 1
    assert len(doc["speed_digest"]) == 64


def test_mesh03_amati_air_cells_match_voxel_reference() -> None:
    """amati air_cells equals voxel-0 count on the CT volume."""
    _nx, _ny, voxels = _read_ctb(CT_DIR / "amati_ct.ctb")
    air, wood = reference_air_wood_counts(voxels)
    doc = _read_json(STATE / "amati_ct" / "cavity_mesh.json")
    assert doc["air_cells"] == air
    assert doc["wood_cells"] == wood


def test_mesh04_guarneri_speed_digest_matches_reference_kernel() -> None:
    """guarneri staging speed_digest matches independent %.6f SHA-256 kernel."""
    nx, ny, voxels = _read_ctb(CT_DIR / "guarneri_ct.ctb")
    expected = reference_speed_digest(voxels, nx, ny)
    doc = _read_json(STATE / "guarneri_ct" / "cavity_mesh.json")
    assert doc["speed_digest"] == expected


def test_mesh05_amati_export_binds_staging_digest() -> None:
    """amati formants cavity_speed_digest equals staging speed_digest after ingest."""
    mesh = _read_json(STATE / "amati_ct" / "cavity_mesh.json")
    formants = _read_json(REPORTS / "amati_ct" / "formants.json")
    assert formants["cavity_speed_digest"] == mesh["speed_digest"]


def test_mesh06_guarneri_export_binds_staging_digest() -> None:
    """guarneri formants cavity_speed_digest equals staging speed_digest."""
    mesh = _read_json(STATE / "guarneri_ct" / "cavity_mesh.json")
    formants = _read_json(REPORTS / "guarneri_ct" / "formants.json")
    assert formants["cavity_speed_digest"] == mesh["speed_digest"]


def test_mesh07_second_batch_keeps_stable_staging_digest() -> None:
    """Re-running the assay keeps speed_digest stable for amati (cross-run)."""
    first = _read_json(STATE / "amati_ct" / "cavity_mesh.json")["speed_digest"]
    _run_fdtd_assay()
    second = _read_json(STATE / "amati_ct" / "cavity_mesh.json")["speed_digest"]
    assert first == second
    formants = _read_json(REPORTS / "amati_ct" / "formants.json")
    assert formants["cavity_speed_digest"] == second


@pytest.fixture(scope="module")
def tb3_strad_closed() -> Path:
    fixtures = Path(os.environ.get("TB3_FIXTURE_ROOT", "/opt/verifier-fixtures"))
    ct_dir = fixtures / "tb3_ct"
    out_dir = fixtures / "tb3_out"
    assert (ct_dir / "strad_ct.ctb").is_file()
    _run_fdtd_assay(ct_dir=ct_dir, out_dir=out_dir)
    return fixtures


def test_tb3_hidden_strad_staging_air_cells(tb3_strad_closed: Path) -> None:
    """Hidden strad CT: staging air_cells match voxel contract (independent of bundled)."""
    ct_dir = tb3_strad_closed / "tb3_ct"
    nx, ny, voxels = _read_ctb(ct_dir / "strad_ct.ctb")
    air, wood = reference_air_wood_counts(voxels)
    mesh = _read_json(STATE / "strad_ct" / "cavity_mesh.json")
    assert mesh["air_cells"] == air
    assert mesh["wood_cells"] == wood
    assert mesh["nx"] == nx and mesh["ny"] == ny


def test_tb3_hidden_strad_export_digest_bind(tb3_strad_closed: Path) -> None:
    """Hidden strad CT: export cavity_speed_digest binds staging (different failure mode)."""
    mesh = _read_json(STATE / "strad_ct" / "cavity_mesh.json")
    formants = _read_json(tb3_strad_closed / "tb3_out" / "strad_ct" / "formants.json")
    assert len(formants["cavity_speed_digest"]) == 64
    assert formants["cavity_speed_digest"] == mesh["speed_digest"]
    assert formants["formant_count"] == 4
    assert formants["peak_prominence_db"] >= 6.0
