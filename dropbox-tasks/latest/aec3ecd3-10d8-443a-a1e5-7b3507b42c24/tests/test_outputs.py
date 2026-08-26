#!/usr/bin/env python3
"""Domain verifier for sparse CSR SpMV budget task."""

import json
import os
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
OUT = Path("/app/output")
DRIVE = ENV / "tools" / "drive_a.mjs"

STUB_P3 = '''export function fn_p3(view, perm) {
  void perm;
  return {
    dim: view.dim,
    half: view.half,
    vals: Float64Array.from(view.vals),
    cols: Uint32Array.from(view.cols),
    rp: Uint32Array.from(view.rp),
    abs_band: view.abs_band,
    rel_band: view.rel_band,
    x_seed: view.x_seed,
    pack_id: view.pack_id,
  };
}
'''

STUB_W8 = '''export function fn_w8(halfView, dim) {
  void dim;
  return {
    dim: halfView.dim,
    half: halfView.half,
    vals: Float64Array.from(halfView.vals),
    cols: Uint32Array.from(halfView.cols),
    rp: Uint32Array.from(halfView.rp),
    abs_band: halfView.abs_band,
    rel_band: halfView.rel_band,
    x_seed: halfView.x_seed,
    pack_id: halfView.pack_id,
  };
}
'''

STUB_Q5 = '''export function fn_q5(view, x, tiles) {
  const n = view.dim;
  const y = new Float64Array(n);
  const t = Math.max(1, tiles | 0);
  const end = Math.min(n, t);
  for (let r = 0; r < end; r++) {
    let s = 0;
    for (let p = view.rp[r]; p < view.rp[r + 1]; p++) {
      s += view.vals[p] * x[view.cols[p]];
    }
    y[r] = s;
  }
  return y;
}
'''

STUB_Z2 = '''import fs from "node:fs";

let mono = 0;

export function fn_z2(view, caps, outPaths) {
  const slot = {
    pack_id: view.pack_id,
    dim: view.dim,
    nz_live: caps.nz_cap,
    nz_cap: caps.nz_cap,
    view_digest: "0".repeat(64),
  };
  const band = {
    pack_id: view.pack_id,
    r_abs: 0,
    r_rel: 0,
    abs_band: view.abs_band,
    rel_band: view.rel_band,
    trace_digest: "1".repeat(64),
  };
  fs.writeFileSync(outPaths.slot, JSON.stringify(slot, null, 2));
  fs.writeFileSync(outPaths.band, JSON.stringify(band, null, 2));
  mono += 1;
  const line = {
    pack_id: view.pack_id,
    nz_live: slot.nz_live,
    r_abs: band.r_abs,
    r_rel: band.r_rel,
    trace_digest: band.trace_digest,
    ts_mono: mono,
  };
  fs.appendFileSync(outPaths.log, JSON.stringify(line) + "\\n");
  return { slot, band };
}
'''

PATHS = {
    "p3": ENV / "p3k/src/lane_a.mjs",
    "w8": ENV / "w8n/src/lane_b.mjs",
    "q5": ENV / "q5r/src/lane_c.mjs",
    "z2": ENV / "z2m/src/lane_d.mjs",
}

_PROBE_DIGEST_SCRIPT = """
import { loadView, makeX, readNlim, viewDigest, traceDigest } from "/app/environment/common/view.mjs";
import { stage_ab } from "/app/environment/tools/pipe_ab.mjs";
import { fn_q5 } from "/app/environment/q5r/src/lane_c.mjs";

const pack = process.argv[2];
const envRoot = "/app/environment";
const raw = loadView(`${envRoot}/suite/${pack}`);
const nlim = readNlim(envRoot);
const { live, perm } = stage_ab(raw);
const xOld = makeX(raw.dim, raw.x_seed);
const x = new Float64Array(raw.dim);
for (let i = 0; i < raw.dim; i++) x[i] = xOld[perm[i]];
const y = fn_q5(live, x, nlim.tile_rows);
console.log(JSON.stringify({
  view_digest: viewDigest(live),
  trace_digest: traceDigest(y),
}));
"""


def _is_lower_hex64(value: str) -> bool:
    return len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _expected_probe_digests(pack: str) -> dict:
    proc = subprocess.run(
        ["node", "--input-type=module", "-", pack],
        input=_PROBE_DIGEST_SCRIPT,
        capture_output=True,
        text=True,
        cwd="/app",
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip())


def _read_nlim() -> dict:
    out: dict = {}
    for line in (ENV / "docs/nlim.toml").read_text().splitlines():
        if "=" not in line:
            continue
        if "=" not in line:
            continue
        k, v = line[: line.index("=")], line[line.index("=") + 1 :]
        out[k.strip()] = float(v.strip()) if "." in v or "e" in v.lower() else int(v.strip())
    return out


def _run_pack(pack: str, reload: bool = False) -> subprocess.CompletedProcess:
    os.makedirs(OUT, exist_ok=True)
    cmd = ["node", "/app/environment/tools/drive_a.mjs", "--pack", pack]
    if reload:
        cmd.append("--reload")
    return subprocess.run(cmd, capture_output=True, text=True, cwd="/app")


def _load_slot() -> dict:
    return json.loads((OUT / "slot_map.json").read_text())


def _load_band() -> dict:
    return json.loads((OUT / "band_tbl.json").read_text())


def _backup_and_set(key: str, body: str) -> str:
    path = PATHS[key]
    original = path.read_text()
    path.write_text(body)
    return original


def _restore(key: str, body: str) -> None:
    PATHS[key].write_text(body)


@pytest.fixture(scope="module")
def nlim():
    return _read_nlim()


def test_q01_line_shape():
    """Slot map and band table expose the required field layout."""
    proc = _run_pack("s1")
    assert proc.returncode == 0, proc.stderr
    slot = _load_slot()
    band = _load_band()
    for key in ("pack_id", "dim", "nz_live", "nz_cap", "view_digest"):
        assert key in slot
    for key in ("pack_id", "r_abs", "r_rel", "abs_band", "rel_band", "trace_digest"):
        assert key in band
    assert isinstance(slot["dim"], int)
    assert isinstance(slot["nz_live"], int)
    assert _is_lower_hex64(slot["view_digest"])
    assert _is_lower_hex64(band["trace_digest"])
    expected = _expected_probe_digests("s1")
    assert slot["view_digest"] == expected["view_digest"]
    assert band["trace_digest"] == expected["trace_digest"]


def test_q02_hold_eps():
    """Residual norms for suite packs stay inside published abs and rel bands."""
    for pack in ("s1", "s2", "s3"):
        proc = _run_pack(pack)
        assert proc.returncode == 0, proc.stderr
        band = _load_band()
        assert band["r_abs"] <= band["abs_band"]
        assert band["r_rel"] <= band["rel_band"]


def test_q03_digest_match():
    """Trace and view digests are lowercase sha256 of the live probe state."""
    proc = _run_pack("s3")
    assert proc.returncode == 0, proc.stderr
    slot = _load_slot()
    band = _load_band()
    assert _is_lower_hex64(slot["view_digest"])
    assert _is_lower_hex64(band["trace_digest"])
    assert band["trace_digest"] != "1" * 64
    expected = _expected_probe_digests("s3")
    assert slot["view_digest"] == expected["view_digest"]
    assert band["trace_digest"] == expected["trace_digest"]


def test_q04_rerun_flow():
    """Hand-written output JSON is overwritten by a real probe run."""
    # Ensure output dir exists via a throwaway probe first.
    assert _run_pack("s1").returncode == 0
    fake_slot = {
        "pack_id": "s1",
        "dim": 1,
        "nz_live": 999,
        "nz_cap": 1,
        "view_digest": "a" * 64,
    }
    fake_band = {
        "pack_id": "s1",
        "r_abs": 12.0,
        "r_rel": 12.0,
        "abs_band": 1e-9,
        "rel_band": 1e-6,
        "trace_digest": "b" * 64,
    }
    (OUT / "slot_map.json").write_text(json.dumps(fake_slot))
    (OUT / "band_tbl.json").write_text(json.dumps(fake_band))
    proc = _run_pack("s1")
    assert proc.returncode == 0, proc.stderr
    slot = _load_slot()
    band = _load_band()
    assert slot["nz_live"] != 999
    assert band["r_abs"] != 12.0
    assert slot["view_digest"] != "a" * 64


def test_q05_twice_same():
    """Consecutive probes after reload emit identical slot and band artifacts."""
    log = OUT / "run_log.jsonl"
    if log.exists():
        log.write_text("")
    assert _run_pack("s2", reload=True).returncode == 0
    slot_a = _load_slot()
    band_a = _load_band()
    assert _run_pack("s2", reload=True).returncode == 0
    slot_b = _load_slot()
    band_b = _load_band()
    assert slot_a == slot_b
    assert band_a == band_b


def test_q06_sens_mut():
    """Residual norms and view digests stay coherent after a live probe."""
    assert _run_pack("s1").returncode == 0
    slot = _load_slot()
    meta = (ENV / "suite/s1/meta.toml").read_text()
    stored = int([ln[ln.index("=") + 1 :] for ln in meta.splitlines() if ln.startswith("nz_stored")][0])
    assert slot["nz_live"] >= stored
    prev = slot["view_digest"]
    original = _backup_and_set("p3", STUB_P3)
    try:
        assert _run_pack("s1").returncode == 0
        slot2 = _load_slot()
        band2 = _load_band()
        # either digest changes or residual leaves the band
        changed = slot2["view_digest"] != prev
        bad_band = band2["r_abs"] > band2["abs_band"] or band2["r_rel"] > band2["rel_band"]
        assert changed or bad_band
    finally:
        _restore("p3", original)


def test_q07_flip_p3():
    """Ablating the layout permutation rebuild drives residuals outside published bands."""
    original = _backup_and_set("p3", STUB_P3)
    try:
        assert _run_pack("s2").returncode == 0
        band = _load_band()
        assert band["r_abs"] > band["abs_band"] or band["r_rel"] > band["rel_band"]
    finally:
        _restore("p3", original)


def test_q08_flip_w8():
    """Ablating half-pair materialization breaks agreement with full-storage residuals."""
    original = _backup_and_set("w8", STUB_W8)
    try:
        assert _run_pack("s2").returncode == 0
        band = _load_band()
        assert band["r_abs"] > band["abs_band"] or band["r_rel"] > band["rel_band"]
    finally:
        _restore("w8", original)


def test_q09_flip_q5():
    """Ablating blocked accumulation breaks long-horizon residual bands on s3."""
    original = _backup_and_set("q5", STUB_Q5)
    try:
        assert _run_pack("s3").returncode == 0
        band = _load_band()
        assert band["r_abs"] > band["abs_band"] or band["r_rel"] > band["rel_band"]
    finally:
        _restore("q5", original)


def test_q10_flip_z2():
    """Ablating ledger emit writes stub digests instead of live view values."""
    original = _backup_and_set("z2", STUB_Z2)
    try:
        assert _run_pack("s1").returncode == 0
        slot = _load_slot()
        band = _load_band()
        assert slot["view_digest"] == "0" * 64 or slot["nz_live"] == slot["nz_cap"]
        assert band["trace_digest"] == "1" * 64
    finally:
        _restore("z2", original)


def test_q11_bound_count(nlim):
    """Live nz counts stay at or under nlim.toml nz_cap for all packs."""
    for pack in ("s1", "s2", "s3"):
        assert _run_pack(pack).returncode == 0
        slot = _load_slot()
        assert slot["nz_live"] <= int(nlim["nz_cap"])
        assert slot["nz_cap"] == int(nlim["nz_cap"])
    # dense workspace for s3 would be 64 > cap
    meta = (ENV / "suite/s3/meta.toml").read_text()
    dim = int([ln[ln.index("=") + 1 :] for ln in meta.splitlines() if ln.startswith("dim")][0])
    assert dim * dim > int(nlim["nz_cap"])


def test_q12_span_pair():
    """Half packs expand so live nnz exceeds upper-only stored count."""
    assert _run_pack("s2").returncode == 0
    slot = _load_slot()
    band = _load_band()
    # half pack expands: live nnz exceeds stored upper-only count
    meta = (ENV / "suite/s2/meta.toml").read_text()
    stored = int([ln[ln.index("=") + 1 :] for ln in meta.splitlines() if ln.startswith("nz_stored")][0])
    assert slot["nz_live"] > stored
    assert band["r_abs"] <= band["abs_band"]


def test_q13_premature():
    """All packs including long-horizon s3 must stay inside residual bands."""
    # With stub q5 and tile_rows covering s1 fully, s1 can look fine while s3 fails.
    original = _backup_and_set("q5", STUB_Q5)
    try:
        assert _run_pack("s1").returncode == 0
        band_s1 = _load_band()
        assert _run_pack("s3").returncode == 0
        band_s3 = _load_band()
        s1_ok = band_s1["r_abs"] <= band_s1["abs_band"] and band_s1["r_rel"] <= band_s1["rel_band"]
        s3_bad = band_s3["r_abs"] > band_s3["abs_band"] or band_s3["r_rel"] > band_s3["rel_band"]
        assert s1_ok
        assert s3_bad
    finally:
        _restore("q5", original)
    assert _run_pack("s1").returncode == 0
    b1 = _load_band()
    assert _run_pack("s3").returncode == 0
    b3 = _load_band()
    assert b1["r_abs"] <= b1["abs_band"]
    assert b3["r_abs"] <= b3["abs_band"]


def test_q14_all_cases():
    """All suite packs pass residual bands after a coherent fix."""
    for pack in ("s1", "s2", "s3"):
        assert _run_pack(pack).returncode == 0
        band = _load_band()
        slot = _load_slot()
        assert band["pack_id"] == pack
        assert slot["pack_id"] == pack
        assert band["r_abs"] <= band["abs_band"]
        assert band["r_rel"] <= band["rel_band"]


def test_q15_hook_flow():
    """drive_a requires --pack and appends a schema-complete run_log row."""
    # argv without --pack must fail; with --pack must succeed
    bad = subprocess.run(
        ["node", "/app/environment/tools/drive_a.mjs"],
        capture_output=True,
        text=True,
        cwd="/app",
    )
    assert bad.returncode != 0
    good = _run_pack("s1")
    assert good.returncode == 0
    assert (OUT / "run_log.jsonl").exists()
    lines = [ln for ln in (OUT / "run_log.jsonl").read_text().splitlines() if ln.strip()]
    assert lines
    row = json.loads(lines[-1])
    for key in ("pack_id", "nz_live", "r_abs", "r_rel", "trace_digest", "ts_mono"):
        assert key in row


def test_q16_pair_fill():
    """Symmetric pack fill agrees with full-storage residual checks on s3."""
    assert _run_pack("s3").returncode == 0
    band = _load_band()
    slot = _load_slot()
    meta = (ENV / "suite/s3/meta.toml").read_text()
    stored = int([ln[ln.index("=") + 1 :] for ln in meta.splitlines() if ln.startswith("nz_stored")][0])
    assert slot["nz_live"] >= stored
    assert band["r_abs"] <= band["abs_band"]
    assert band["r_rel"] <= band["rel_band"]
