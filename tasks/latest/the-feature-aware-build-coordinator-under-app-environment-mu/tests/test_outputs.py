"""Outcome checks for bp_run cert report."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
ENV = APP / "environment"
OUT = APP / "output"
REPORT = OUT / "cert_report.json"
TRACES = OUT / "run_traces"
META = OUT / "witness_meta"
BP = ENV / "scripts" / "bp_run"
ARM_TABLE = ENV / "docs" / "primary_flags.txt"
HOOKS = ENV / "docs" / "operator_cmds.txt"
HOLD_DATA = ENV / "data" / "extra_flags.toml"
LEDGER = ENV / "state" / "k3_ledger.tsv"
LATTICE = ENV / "data" / "flag_lattice.toml"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

SITE_A = ENV / "h2k" / "flag_mux.ts"
SITE_B = ENV / "n6p" / "merge_mux.ts"
SITE_C = ENV / "w3q" / "topo_mux.ts"
SITE_D = ENV / "r7t" / "cert_mux.ts"
SITE_E = ENV / "tools" / "gauge_mux.ts"


def broken_text(tag: str) -> str:
    return (FIXTURES / ("broken_" + tag + ".ts")).read_text(encoding="utf-8")


def is_lower_hex16(text: str) -> bool:
    if len(text) != 16:
        return False
    for ch in text:
        code = ord(ch)
        if 48 <= code <= 57 or 97 <= code <= 102:
            continue
        return False
    return True


def fnv1a_64(text: str) -> str:
    h = 0xCBF29CE484222325
    for b in text.encode("utf-8"):
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def reduce_rows(rows: list[dict]) -> str:
    parts = sorted(r["facet_material"] for r in rows)
    return fnv1a_64(",".join(parts))


def load_primary() -> list[str]:
    return [ln.strip() for ln in ARM_TABLE.read_text(encoding="utf-8").splitlines() if ln.strip()]


def load_hold_slugs() -> list[str]:
    slugs = []
    sep = chr(61)
    for line in HOLD_DATA.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("slug"):
            slugs.append(line.partition(sep)[2].strip().strip('"'))
    return slugs


def proof_tail(seed: int) -> bytes:
    buf = bytearray(4)
    buf[0] = (seed >> 24) & 0xFF
    buf[1] = (seed >> 16) & 0xFF
    buf[2] = (seed >> 8) & 0xFF
    buf[3] = seed & 0xFF
    return bytes(buf)


def proof_from_facet(facet_hex: str) -> int:
    return int(facet_hex, 16) & 0xFFFF


def hook_argv() -> list[str]:
    tokens = [
        ln.strip()
        for ln in HOOKS.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    return tokens


def rebuild_driver() -> None:
    proc = subprocess.run(
        ["make", "-C", "/app/environment", "bp_run"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout


def run_bp(extra: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    cmd = ["bash", "/app/environment/scripts/bp_run", *(extra or ["--phase", "all", "--emit", str(REPORT)])]
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def run_checked(extra: list[str] | None = None) -> dict:
    proc = run_bp(extra)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return json.loads(REPORT.read_text(encoding="utf-8"))


def pair_map(rows: list[dict]) -> dict[str, dict]:
    return {r["arm_id"]: r for r in rows}


def coherent_row(row: dict) -> bool:
    return (
        row["lag"] == 0
        and row["expand_rc"] == 1
        and row["merge_rc"] == 1
        and row["proof_rc"] == 1
    )


def echo_pairs(primary: list[str]) -> list[tuple[str, str]]:
    return [(aid, f"{aid}_echo") for aid in primary]


def wipe_output_dir() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="module", autouse=True)
def _fresh_report() -> None:
    wipe_output_dir()
    rebuild_driver()
    run_checked()


def test_t1_layout() -> None:
    """Report uses row_v4 schema and lists every primary arm id."""
    doc = run_checked()
    assert doc["schema_version"] == "row_v4"
    prim = load_primary()
    seen = {r["arm_id"] for r in doc["rows"]}
    for aid in prim:
        assert aid in seen


def test_t2_pair_hex() -> None:
    """Echo rows agree on facet material and rc fields when sound."""
    doc = run_checked()
    by = pair_map(doc["rows"])
    for base, echo in echo_pairs(load_primary()):
        b = by[base]
        e = by[echo]
        if coherent_row(b) and coherent_row(e):
            assert b["facet_material"] == e["facet_material"]
            assert b["expand_rc"] == e["expand_rc"]
            assert b["merge_rc"] == e["merge_rc"]
            assert b["proof_rc"] == e["proof_rc"]


def test_t3_rc_fields() -> None:
    """Sound terminal rows keep lag zero and all rc fields at one."""
    doc = run_checked()
    for row in doc["rows"]:
        assert row["lag"] == 0
        assert row["expand_rc"] == 1
        assert row["merge_rc"] == 1
        assert row["proof_rc"] == 1


def test_t4_label_text() -> None:
    """Summary sync_label reads steady when the report is coherent."""
    doc = run_checked()
    assert doc["summary"]["sync_label"] == "steady"


def test_t5_width_max() -> None:
    """span_band equals the maximum absolute lag magnitude."""
    doc = run_checked()
    lags = [abs(r["lag"]) for r in doc["rows"]]
    assert doc["summary"]["span_band"] == max(lags)


def test_t6_reduce_hex() -> None:
    """Summary cert_digest matches the entry.ts reduction over rows."""
    doc = run_checked()
    assert doc["summary"]["cert_digest"] == reduce_rows(doc["rows"])


def test_t7_known_good() -> None:
    """Terminal cert_digest is sixteen lowercase hex digits and self-consistent."""
    doc = run_checked()
    expected = reduce_rows(doc["rows"])
    digest = doc["summary"]["cert_digest"]
    assert digest == expected
    assert is_lower_hex16(digest)


def test_t8_lower_fmt() -> None:
    """Each row facet_material uses sixteen lowercase hex characters."""
    doc = run_checked()
    for row in doc["rows"]:
        assert is_lower_hex16(row["facet_material"])


def test_t9_total_count() -> None:
    """rows_total equals the row vector length."""
    doc = run_checked()
    assert doc["summary"]["rows_total"] == len(doc["rows"])


def test_t10_fresh_emit() -> None:
    """Hand-written report JSON is replaced by a pipeline rerun."""
    REPORT.write_text('{"schema_version":"row_v4","summary":{},"rows":[]}\n', encoding="utf-8")
    doc = run_checked()
    assert len(doc["rows"]) > 0
    assert doc["summary"]["rows_total"] == len(doc["rows"])


def test_t11_twice_same() -> None:
    """Consecutive pipeline runs produce identical reports."""
    first = run_checked()
    second = run_checked()
    assert first == second


def test_t12_sens_steps() -> None:
    """Mutating flag_lattice data changes facet material and digest."""
    before = run_checked()
    original = LATTICE.read_text(encoding="utf-8")
    try:
        lines = original.splitlines()
        new_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("floor"):
                eq_idx = stripped.find("=")
                key = stripped[:eq_idx].strip()
                bumped = int(stripped[eq_idx + 1 :].strip()) + 6
                new_lines.append(f"{key} = {bumped}")
            else:
                new_lines.append(line)
        LATTICE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        rebuild_driver()
        after = run_checked()
        assert after["summary"]["cert_digest"] != before["summary"]["cert_digest"]
    finally:
        LATTICE.write_text(original, encoding="utf-8")
        rebuild_driver()
        run_checked()


def test_t13_flip_h2() -> None:
    """Broken flag expansion bridge breaks expand_rc coherence."""
    baseline = run_checked()
    path = SITE_A
    saved = path.read_text(encoding="utf-8")
    try:
        path.write_text(broken_text("h2"), encoding="utf-8")
        rebuild_driver()
        doc = run_checked()
        assert doc["summary"]["cert_digest"] != baseline["summary"]["cert_digest"]
        assert any(r["expand_rc"] != 1 for r in doc["rows"])
    finally:
        path.write_text(saved, encoding="utf-8")
        rebuild_driver()
        run_checked()


def test_t14_flip_both() -> None:
    """Broken expansion and merge wiring together break pipeline coherence."""
    h2_path = SITE_A
    n6_path = SITE_B
    saved_h2 = h2_path.read_text(encoding="utf-8")
    saved_n6 = n6_path.read_text(encoding="utf-8")
    try:
        h2_path.write_text(broken_text("h2"), encoding="utf-8")
        n6_path.write_text(broken_text("n6"), encoding="utf-8")
        rebuild_driver()
        doc = run_checked()
        assert doc["summary"]["sync_label"] != "steady"
        assert any(r["lag"] != 0 or r["merge_rc"] != 1 for r in doc["rows"])
    finally:
        h2_path.write_text(saved_h2, encoding="utf-8")
        n6_path.write_text(saved_n6, encoding="utf-8")
        rebuild_driver()
        run_checked()


def test_t15_flip_n6() -> None:
    """Broken merge injection fails held-out extra_flags rows."""
    path = SITE_B
    saved = path.read_text(encoding="utf-8")
    try:
        path.write_text(broken_text("n6"), encoding="utf-8")
        rebuild_driver()
        doc = run_checked()
        slugs = load_hold_slugs()
        hold_rows = [r for r in doc["rows"] if any(f"~{s}" in r["arm_id"] for s in slugs)]
        assert any(r["merge_rc"] != 1 or not coherent_row(r) for r in hold_rows)
    finally:
        path.write_text(saved, encoding="utf-8")
        rebuild_driver()
        run_checked()


def test_t16_all_extras() -> None:
    """Every held-out extra_flags scenario row is coherent after repair."""
    doc = run_checked()
    slugs = load_hold_slugs()
    for slug in slugs:
        rows = [r for r in doc["rows"] if f"~{slug}" in r["arm_id"]]
        assert rows, f"missing hold slug {slug}"
        for row in rows:
            assert coherent_row(row)


def test_t17_flip_w3() -> None:
    """Broken topo emitter leaves proof_rc incoherent with witness bytes."""
    path = SITE_C
    saved = path.read_text(encoding="utf-8")
    try:
        path.write_text(broken_text("w3"), encoding="utf-8")
        rebuild_driver()
        doc = run_checked()
        assert any(r["proof_rc"] != 1 for r in doc["rows"])
        if META.exists():
            short = [p for p in META.glob("*.bin") if len(p.read_bytes()) != 8]
            assert short, "broken topo should emit truncated witness sidecars"
    finally:
        path.write_text(saved, encoding="utf-8")
        rebuild_driver()
        run_checked()


def test_t21_witness_bytes() -> None:
    """Witness sidecars bind each base row's proof head and seed tail bijectively."""
    doc = run_checked()
    base_rows = [
        r for r in doc["rows"]
        if not r["arm_id"].endswith("_echo") and coherent_row(r)
    ]
    files = sorted(META.glob("*.bin"), key=lambda p: int(p.stem))
    assert len(files) == len(base_rows)
    row_heads = {proof_from_facet(r["facet_material"]) for r in base_rows}
    seen_heads: set[int] = set()
    for path in files:
        seed = int(path.stem)
        disk = path.read_bytes()
        assert len(disk) == 8
        assert disk[4:8] == proof_tail(seed)
        head = int.from_bytes(disk[0:4], "big") & 0xFFFF
        assert head in row_heads
        assert head not in seen_heads
        seen_heads.add(head)
    assert seen_heads == row_heads


def load_ledger() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("aid"):
            continue
        aid, hx = line.split("\t", 1)
        out[aid.strip()] = hx.strip()
    return out


def test_t23_ledger_proof_hex_aligns() -> None:
    """Ledger proof_hex matches each arm's folded facet proof contribution."""
    doc = run_checked()
    by = pair_map(doc["rows"])
    ledger = load_ledger()
    assert ledger
    for aid, proof_hex in ledger.items():
        row = by[aid]
        assert int(proof_hex, 16) == proof_from_facet(row["facet_material"])


def test_t22_flip_r7() -> None:
    """Broken materialization cross-check clears proof_rc on an otherwise sound emit."""
    baseline = run_checked()
    assert all(r["proof_rc"] == 1 for r in baseline["rows"])
    path = SITE_D
    saved = path.read_text(encoding="utf-8")
    try:
        path.write_text(broken_text("r7"), encoding="utf-8")
        rebuild_driver()
        doc = run_checked()
        assert doc["summary"]["cert_digest"] == baseline["summary"]["cert_digest"]
        assert any(r["proof_rc"] != 1 for r in doc["rows"])
        assert doc["summary"]["sync_label"] != "steady"
    finally:
        path.write_text(saved, encoding="utf-8")
        rebuild_driver()
        run_checked()


def test_t18_durable_first() -> None:
    """Profile drill updates ledger trace metadata after durable emit."""
    if TRACES.exists():
        for child in TRACES.glob("*"):
            if child.is_file():
                child.unlink()
    proc = run_bp(["--phase", "all", "--drill", "profile_a", "--emit", str(REPORT)])
    assert proc.returncode == 0, proc.stderr + proc.stdout
    trace = json.loads((TRACES / "last.json").read_text(encoding="utf-8"))
    assert trace["drill"] == "profile_a"
    assert trace["ledger_mtime"] > 0
    assert LEDGER.exists()
    doc = json.loads(REPORT.read_text(encoding="utf-8"))
    assert all(coherent_row(r) for r in doc["rows"])


def test_t19_premature() -> None:
    """Premature steady gauge label cannot mask disagreeing echo pairs."""
    n6_path = SITE_B
    gauge_path = SITE_E
    saved_n6 = n6_path.read_text(encoding="utf-8")
    saved_gauge = gauge_path.read_text(encoding="utf-8")
    try:
        n6_path.write_text(broken_text("n6"), encoding="utf-8")
        gauge_path.write_text(broken_text("e"), encoding="utf-8")
        rebuild_driver()
        run_checked()
        gauge = subprocess.run(
            ["bash", "/app/environment/scripts/bp_run", "--gauge"],
            text=True,
            capture_output=True,
            check=False,
        )
        assert gauge.returncode == 0
        gauge_doc = json.loads(gauge.stdout.strip())
        doc = json.loads(REPORT.read_text(encoding="utf-8"))
        disagree = any(
            pair_map(doc["rows"]).get(base, {}).get("facet_material")
            != pair_map(doc["rows"]).get(echo, {}).get("facet_material")
            for base, echo in echo_pairs(load_primary())
        )
        gauge_key = "la" + "bel"
        steady_text = "st" + "eady"
        if gauge_doc.get(gauge_key) == steady_text and disagree:
            assert doc["summary"]["sync_label"] != "steady"
    finally:
        n6_path.write_text(saved_n6, encoding="utf-8")
        gauge_path.write_text(saved_gauge, encoding="utf-8")
        rebuild_driver()
        run_checked()


def test_t20_cmd_seq() -> None:
    """Operator argv sequence from operator_cmds.txt succeeds end to end."""
    wipe_output_dir()
    proc = run_bp(hook_argv())
    assert proc.returncode == 0, proc.stderr + proc.stdout
    doc = json.loads(REPORT.read_text(encoding="utf-8"))
    assert doc["summary"]["sync_label"] == "steady"
