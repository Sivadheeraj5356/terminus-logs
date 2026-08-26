"""Verifier for wireguard-preshared-rotate handshake reconcile pipeline (wg_run driver)."""

from __future__ import annotations

import json
import os
import pwd
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

import pytest

APP = Path("/app")
ENV = APP / "environment"
OUT = APP / "output" / "psk_rotate_report.json"
TRACE = APP / "output" / "run_traces" / "phase.jsonl"
WITNESS = ENV / "w8g" / "staged" / "w8_chain.bin"
PEER_IDS = ENV / "docs" / "peer_ids.txt"
DRIVER = APP / "bin" / "wg_run"
# Ablation fixtures live outside /tests so the submitted binary cannot read them.
STOCK = Path("/opt/tb_verifier/stock_broken")
PERM_TBL = ENV / "data" / "perm_tbl.toml"
DURABLE = ENV / "w8g" / "durable"
WIT_STOCK = STOCK / "w8b.bin"

K7_MUX = ENV / "k7m" / "src" / "k7_mux.cpp"
F3_MUX = ENV / "f3p" / "src" / "f3_mux.cpp"
P5_MUX = ENV / "p5k" / "src" / "p5_mux.cpp"
H9_MUX = ENV / "h9w" / "src" / "h9_mux.cpp"

BROKEN_K7 = (STOCK / "k7b.cpp").read_text(encoding="utf-8")
BROKEN_F3 = (STOCK / "f3b.cpp").read_text(encoding="utf-8")
BROKEN_P5 = (STOCK / "p5b.cpp").read_text(encoding="utf-8")
BROKEN_H9 = (STOCK / "h9b.cpp").read_text(encoding="utf-8")

SHADOW_PAIRS = [("peer_a", "peer_a_m"), ("peer_b", "peer_b_m")]

_WG_DRIVER = pwd.getpwnam("wgdriver")
WG_UID = _WG_DRIVER.pw_uid
WG_GID = _WG_DRIVER.pw_gid


def _wg_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update({"WG_ENV_ROOT": str(ENV), "HOME": "/tmp"})
    return env


def _own_for_driver(path: Path) -> None:
    if not path.exists():
        return
    os.chown(path, WG_UID, WG_GID)
    if path.is_dir():
        os.chmod(path, 0o775)
    else:
        os.chmod(path, 0o664)


def _driver_cmd(*extra: str) -> list[str]:
    """Run wg_run as wgdriver so /tests and /opt/tb_verifier stay unreadable."""
    return [
        "setpriv",
        f"--reuid={WG_UID}",
        f"--regid={WG_GID}",
        "--clear-groups",
        "--",
        str(DRIVER),
        *extra,
    ]


@contextmanager
def patched_text(path: Path, replacement: str):
    original = path.read_text(encoding="utf-8")
    path.write_text(replacement, encoding="utf-8")
    rebuild_wg_run()
    try:
        yield
    finally:
        path.write_text(original, encoding="utf-8")
        rebuild_wg_run()


def rebuild_wg_run() -> None:
    subprocess.run(["bash", str(ENV / "scripts" / "pack_wg.sh")], check=True, env=_wg_env())
    assert DRIVER.is_file(), "pack_wg.sh did not produce wg_run driver"
    os.chmod(DRIVER, 0o755)
    _own_for_driver(OUT.parent)
    _own_for_driver(TRACE.parent)
    _own_for_driver(Path("/app/state/wg"))
    _own_for_driver(WITNESS.parent)
    _own_for_driver(DURABLE)


@pytest.fixture(scope="module")
def built_driver() -> None:
    rebuild_wg_run()


def digest16(text: str) -> str:
    h1 = 1469598103934665603
    h2 = 1099511628211
    for ch in text.encode("utf-8"):
        h1 ^= ch
        h1 = (h1 * 1099511628211) & ((1 << 64) - 1)
        h2 ^= ch + 17
        h2 = (h2 * 1469598103934665603) & ((1 << 64) - 1)
    mixed = h1 ^ (h2 >> 7)
    return f"{mixed:016x}"[:16]


def flow_digest(rows: list[dict]) -> str:
    parts = [
        "|".join(
            [
                str(row["peer_id"]),
                str(row["bind_hex"]),
                str(int(row["mux_rc"])),
                str(int(row["mark_rc"])),
                str(int(row["ov_rc"])),
                str(int(row["seal_rc"])),
            ]
        )
        for row in rows
    ]
    return digest16("|".join(sorted(parts)))


def range_band(rows: list[dict]) -> int:
    return max(abs(int(row["shift_code"])) for row in rows)


def reset_outputs() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.unlink(missing_ok=True)
    if TRACE.parent.exists():
        for child in TRACE.parent.iterdir():
            child.unlink()
    WITNESS.parent.mkdir(parents=True, exist_ok=True)
    WITNESS.write_text(WIT_STOCK.read_text(encoding="utf-8"), encoding="utf-8")
    probe = ENV / "w8g" / "staged" / "local_mux.token"
    if probe.exists():
        probe.unlink()
    alt = ENV / "w8g" / "staged" / "dual_alt.bin"
    if alt.exists():
        alt.unlink()
    stage = Path("/app/state/wg/stage_mux.txt")
    stage.parent.mkdir(parents=True, exist_ok=True)
    if stage.exists():
        stage.unlink()
    for path in (OUT.parent, TRACE.parent, Path("/app/state/wg"), WITNESS.parent, DURABLE, WITNESS):
        _own_for_driver(path)


def run_wg_run(*extra: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _driver_cmd(*extra),
        check=check,
        capture_output=True,
        text=True,
        env=_wg_env(),
    )


def run_workflow(variant_seed: int = 0) -> None:
    run_wg_run("--profile", "stage", "--out", str(OUT))
    run_wg_run(
        "--profile",
        "apply",
        "--hook",
        "replay",
        "--variant-seed",
        str(variant_seed),
        "--out",
        str(OUT),
    )


def run_pipeline(variant_seed: int = 0, *, rebuild: bool = False, built_driver: object | None = None) -> dict:
    _ = built_driver
    reset_outputs()
    if rebuild:
        rebuild_wg_run()
    run_workflow(variant_seed)
    return load_report()


def load_report() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8"))


def load_peer_ids() -> list[str]:
    return [
        line.strip()
        for line in PEER_IDS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def call_status_view() -> tuple[str, bool]:
    proc = run_wg_run("--status-view", check=False)
    label, ok_raw = proc.stdout.strip().split()
    return label, ok_raw == "1"


def rows_by_id(report: dict) -> dict[str, dict]:
    return {str(row["peer_id"]): row for row in report["rows"]}


def valid_bind_hex(value: str) -> bool:
    if len(value) != 16:
        return False
    try:
        parsed = int(value, 16)
    except ValueError:
        return False
    return f"{parsed:016x}" == value


def assert_rc_fields(report: dict) -> None:
    for row in report["rows"]:
        assert int(row["shift_code"]) == 0
        assert int(row["mux_rc"]) == 1
        assert int(row["mark_rc"]) == 1
        assert int(row["ov_rc"]) == 1
        assert int(row["seal_rc"]) == 1


def assert_shadow_pairs(report: dict) -> None:
    by_id = rows_by_id(report)
    for left, right in SHADOW_PAIRS:
        assert by_id[left]["bind_hex"] == by_id[right]["bind_hex"]
        assert int(by_id[left]["mux_rc"]) == int(by_id[right]["mux_rc"])
        assert int(by_id[left]["mark_rc"]) == int(by_id[right]["mark_rc"])
        assert int(by_id[left]["ov_rc"]) == int(by_id[right]["ov_rc"])
        assert int(by_id[left]["seal_rc"]) == int(by_id[right]["seal_rc"])


def assert_coherent(report: dict) -> None:
    rows = report["rows"]
    assert report["summary"]["conv_label"] == "settled"
    assert int(report["summary"]["range_band"]) == 0
    assert int(report["summary"]["rows_total"]) == len(rows)
    assert_rc_fields(report)
    for row in rows:
        assert valid_bind_hex(row["bind_hex"])
    assert_shadow_pairs(report)
    assert report["summary"]["flow_digest"] == flow_digest(rows)
    assert int(report["summary"]["range_band"]) == range_band(rows)
    assert WITNESS.is_file()
    witness = WITNESS.read_text(encoding="utf-8")
    for row in rows:
        if int(row["seal_rc"]) == 1:
            assert row["bind_hex"] in witness
    assert TRACE.is_file()


def assert_not_coherent(report: dict) -> None:
    try:
        assert_coherent(report)
    except AssertionError:
        return
    raise AssertionError("expected incoherent report after ablation")


def save_durable_snapshot() -> None:
    DURABLE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT, DURABLE / "psk_rotate_report.json")
    shutil.copy2(WITNESS, DURABLE / "w8_snapshot.bin")


def restore_durable_snapshot() -> None:
    shutil.copy2(DURABLE / "w8_snapshot.bin", WITNESS)


@pytest.fixture(autouse=True)
def _fresh_output():
    reset_outputs()
    yield
    reset_outputs()


def test_wg_01(built_driver: None) -> None:
    """JSON layout; primary slots match listed order."""
    report = run_pipeline(built_driver=built_driver)
    assert "rows" in report and "summary" in report
    mirror_ids = {right for _, right in SHADOW_PAIRS}
    primaries = [row["peer_id"] for row in report["rows"] if row["peer_id"] not in mirror_ids]
    assert primaries == [sid for sid in load_peer_ids() if sid not in mirror_ids]
    assert_coherent(report)


def test_wg_02(built_driver: None) -> None:
    """Shadow slot pairs agree on facet and rc fields."""
    report = run_pipeline(built_driver=built_driver)
    assert_shadow_pairs(report)
    assert_coherent(report)


def test_wg_03(built_driver: None) -> None:
    """Apply-only pass without stage remains incoherent."""
    _ = built_driver
    reset_outputs()
    run_wg_run("--profile", "apply", "--hook", "replay", "--variant-seed", "0", "--out", str(OUT))
    assert_not_coherent(load_report())


def test_wg_23(built_driver: None) -> None:
    """Stage-only pass must not claim settled via --status-view."""
    _ = built_driver
    reset_outputs()
    run_wg_run("--profile", "stage", "--out", str(OUT))
    label, ok = call_status_view()
    assert label != "settled" or not ok


def test_wg_04(built_driver: None) -> None:
    """Summary conv_label reads settled when matrix coherent."""
    report = run_pipeline(built_driver=built_driver)
    assert report["summary"]["conv_label"] == "settled"
    assert_rc_fields(report)
    label, ok = call_status_view()
    assert label == "settled" and ok


def test_wg_05(built_driver: None) -> None:
    """range_band equals max abs shift_code magnitude."""
    report = run_pipeline(built_driver=built_driver)
    assert_coherent(report)
    assert int(report["summary"]["range_band"]) == range_band(report["rows"])


def test_wg_06(built_driver: None) -> None:
    """summary flow_digest matches wg_run reduction from rows."""
    report = run_pipeline(built_driver=built_driver)
    assert_coherent(report)
    assert report["summary"]["flow_digest"] == flow_digest(report["rows"])


def test_wg_07(built_driver: None) -> None:
    """Witness artifact exists and embeds facet bytes when seal_rc passes."""
    report = run_pipeline(built_driver=built_driver)
    assert_coherent(report)
    witness = WITNESS.read_text(encoding="utf-8")
    for row in report["rows"]:
        if int(row["seal_rc"]) == 1:
            assert row["bind_hex"] in witness


def test_wg_08(built_driver: None) -> None:
    """bind_hex uses exactly sixteen lowercase hex digits."""
    report = run_pipeline(built_driver=built_driver)
    assert_coherent(report)
    for row in report["rows"]:
        assert valid_bind_hex(row["bind_hex"])


def test_wg_09(built_driver: None) -> None:
    """rows_total integer equals row vector length."""
    report = run_pipeline(built_driver=built_driver)
    assert_coherent(report)
    assert int(report["summary"]["rows_total"]) == len(report["rows"])


def test_wg_10(built_driver: None) -> None:
    """Tampered hand-written JSON replaced by pipeline rerun."""
    _ = built_driver
    run_workflow(0)
    assert_coherent(load_report())
    tampered = {
        "rows": [],
        "summary": {
            "rows_total": 0,
            "conv_label": "drift",
            "range_band": 9,
            "flow_digest": "0" * 16,
        },
    }
    OUT.write_text(json.dumps(tampered), encoding="utf-8")
    run_workflow(0)
    rerun = load_report()
    assert rerun != tampered
    assert_coherent(rerun)


def test_wg_11(built_driver: None) -> None:
    """Consecutive pipeline runs produce identical reports."""
    first = run_pipeline(built_driver=built_driver)
    second = run_pipeline(built_driver=built_driver)
    assert_coherent(first)
    assert_coherent(second)
    assert first["summary"]["flow_digest"] == flow_digest(first["rows"])
    assert second["summary"]["flow_digest"] == flow_digest(second["rows"])
    assert first["summary"]["flow_digest"] == second["summary"]["flow_digest"]


def test_wg_12(built_driver: None) -> None:
    """Mutating perm table data changes facet material and digest."""
    _ = built_driver
    before_report = run_pipeline(built_driver=built_driver)
    assert_coherent(before_report)
    before_digest = before_report["summary"]["flow_digest"]
    before_facet = rows_by_id(before_report)["peer_a"]["bind_hex"]
    original = PERM_TBL.read_text(encoding="utf-8")
    mutated = original.replace("peer_a = 0.100", "peer_a = 0.150", 1)
    assert mutated != original, "perm_tbl.toml missing peer_a weight row for seed 0"
    PERM_TBL.write_text(mutated, encoding="utf-8")
    try:
        after_digest = run_pipeline(rebuild=True)["summary"]["flow_digest"]
        after_facet = rows_by_id(load_report())["peer_a"]["bind_hex"]
        assert after_digest != before_digest
        assert after_facet != before_facet
    finally:
        PERM_TBL.write_text(original, encoding="utf-8")
        rebuild_wg_run()


def test_wg_13(built_driver: None) -> None:
    """Reverting k7 mux must break coherence even when dual_alt.bin is staged."""
    _ = built_driver
    with patched_text(K7_MUX, BROKEN_K7):
        report = run_pipeline(rebuild=False)
        assert_not_coherent(report)


def test_wg_14(built_driver: None) -> None:
    """Reverting frontier B breaks route-mark coherence."""
    _ = built_driver
    with patched_text(F3_MUX, BROKEN_F3):
        report = run_pipeline(rebuild=False)
        assert any(int(row["mark_rc"]) == 0 for row in report["rows"])


def test_wg_15(built_driver: None) -> None:
    """Reverting frontier C breaks overlap coherence."""
    _ = built_driver
    with patched_text(P5_MUX, BROKEN_P5):
        report = run_pipeline(rebuild=False)
        assert any(int(row["ov_rc"]) == 0 for row in report["rows"])


def test_wg_16(built_driver: None) -> None:
    """Reverting frontier D breaks terminal status convergence."""
    _ = built_driver
    with patched_text(H9_MUX, BROKEN_H9):
        run_pipeline(rebuild=False)
        label, ok = call_status_view()
        assert label != "settled" or not ok


def test_wg_17(built_driver: None) -> None:
    """Every held-out perm_tbl seed survives after fix."""
    _ = built_driver
    for seed in (0, 1, 2, 3):
        report = run_pipeline(seed, built_driver=built_driver)
        assert_coherent(report)


def test_wg_18(built_driver: None) -> None:
    """Recovery restore from durable state converges to a coherent terminal report."""
    _ = built_driver
    run_pipeline(built_driver=built_driver)
    save_durable_snapshot()
    reset_outputs()
    restore_durable_snapshot()
    rerun = run_pipeline(built_driver=built_driver)
    assert_coherent(rerun)


def test_wg_19(built_driver: None) -> None:
    """Sparse trace subset produces phase rows after workflow."""
    _ = built_driver
    report = run_pipeline(built_driver=built_driver)
    assert_coherent(report)
    assert TRACE.exists()
    phases = [json.loads(line)["phase"] for line in TRACE.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert "epoch" in phases
    assert "mux" in phases
    assert "mark" in phases


def test_wg_20(built_driver: None) -> None:
    """Cross-format witness, trace, and reconcile report stay consistent."""
    _ = built_driver
    report = run_pipeline(built_driver=built_driver)
    assert_coherent(report)
    witness = WITNESS.read_text(encoding="utf-8")
    for row in report["rows"]:
        if int(row["seal_rc"]) == 1:
            assert row["bind_hex"] in witness
    label, ok = call_status_view()
    assert label == "settled" and ok


def test_wg_21(built_driver: None) -> None:
    """Status view must reject settled JSON when witness or traces are corrupted."""
    _ = built_driver
    report = run_pipeline(built_driver=built_driver)
    assert_coherent(report)
    assert load_report()["summary"]["conv_label"] == "settled"
    label, ok = call_status_view()
    assert label == "settled" and ok

    original_witness = WITNESS.read_text(encoding="utf-8")
    WITNESS.write_text("tampered-witness-bytes\n", encoding="utf-8")
    try:
        label, ok = call_status_view()
        assert label != "settled" or not ok
        assert load_report()["summary"]["conv_label"] == "settled"
    finally:
        WITNESS.write_text(original_witness, encoding="utf-8")

    label, ok = call_status_view()
    assert label == "settled" and ok

    original_trace = TRACE.read_text(encoding="utf-8")
    TRACE.write_text(
        "\n".join(
            line
            for line in original_trace.splitlines()
            if '"phase": "epoch"' not in line
            and '"phase": "mux"' not in line
            and '"phase": "mark"' not in line
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        label, ok = call_status_view()
        assert label != "settled" or not ok
        assert load_report()["summary"]["conv_label"] == "settled"
    finally:
        TRACE.write_text(original_trace, encoding="utf-8")


def test_wg_22(built_driver: None) -> None:
    """Submitted wg_run identity cannot read verifier fixtures under /tests or /opt/tb_verifier."""
    _ = built_driver
    assert STOCK.is_dir()
    assert not (Path("/tests") / "stock_broken").exists()

    denied = [
        "/tests/test_outputs.py",
        "/opt/tb_verifier/stock_broken/k7b.cpp",
        str(STOCK / "w8b.bin"),
    ]
    for path in denied:
        proc = subprocess.run(
            [
                "setpriv",
                f"--reuid={WG_UID}",
                f"--regid={WG_GID}",
                "--clear-groups",
                "--",
                "python3",
                "-c",
                f"open({path!r}).read()",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode != 0, f"wgdriver unexpectedly read {path}"

    # Positive control: driver user can still execute the pipeline binary path.
    assert DRIVER.is_file()
    proc = subprocess.run(
        [
            "setpriv",
            f"--reuid={WG_UID}",
            f"--regid={WG_GID}",
            "--clear-groups",
            "--",
            "test",
            "-x",
            str(DRIVER),
        ],
        check=False,
    )
    assert proc.returncode == 0
