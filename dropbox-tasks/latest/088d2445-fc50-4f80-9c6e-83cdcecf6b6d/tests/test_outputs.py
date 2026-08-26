"""Verifier for audit-report-json-satellite-crop-stress (Go HARD redesign)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
OUT = Path("/app/output")
REPORT = OUT / "audit_report.json"
CACHE = OUT / "stage" / "digest_cache.json"
STAGE = OUT / "stage"
STAGE_SUMMARY = STAGE / "summary.json"
HS = "/app/environment/tools/hs_run.sh"
WAL = ENV / "data" / "wal44" / "events.jl"
IDX = ENV / "data" / "wal44" / "ckpt_idx.toml"
ROT = ENV / "docs" / "rot_d.toml"
ROT_PATH = "/app/environment/docs/rot_d.toml"
SQLITE_PATH = "/app/environment/data/store_q.sqlite"


def _clear_outputs() -> None:
    if REPORT.exists():
        REPORT.unlink()
    for name in (
        "summary.json",
        "digest_cache.json",
        "gen_stamp.txt",
        "resume.flag",
        "mat_echo.json",
    ):
        p = STAGE / name
        if p.exists():
            p.unlink()


def _run_hs(warm: bool = False) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cmd = [HS, "--all-lanes", "--rotations", ROT_PATH]
    if warm:
        cmd.append("--warm")
    subprocess.run(
        cmd,
        check=True,
        cwd="/app",
        env={**os.environ, "DRV_ROOT": str(ENV), "DRV_OUT": str(OUT)},
    )


def _load_report() -> dict:
    assert REPORT.exists(), f"missing {REPORT}"
    return json.loads(REPORT.read_text())


def _keyset() -> list[int]:
    out = subprocess.check_output(
        [
            "sqlite3",
            SQLITE_PATH,
            "SELECT row_id FROM " + "pair" + "_tab ORDER BY row_id ASC;",
        ],
        text=True,
    )
    return [int(x) for x in out.splitlines() if x.strip()]


def _bind_map() -> dict[int, str]:
    out = subprocess.check_output(
        [
            "sqlite3",
            "-separator",
            "|",
            SQLITE_PATH,
            "SELECT row_id, bind_ref FROM " + "pair" + "_tab ORDER BY row_id ASC;",
        ],
        text=True,
    )
    m = {}
    for ln in out.splitlines():
        if not ln.strip():
            continue
        a, b = ln.split("|", 1)
        m[int(a)] = b
    return m


def _u64_le(k: int) -> bytes:
    out = bytearray(8)
    for i in range(8):
        out[i] = (k >> (8 * i)) & 0xFF
    return bytes(out)


def _sha256_hex(data: bytes) -> str:
    tool = "sha" + "256sum"
    out = subprocess.check_output([tool], input=data)
    return out.decode().split()[0].strip()


def _materialize_from(text: str) -> tuple[dict[int, bytes], str]:
    """Replay wal44 WATERMARK rules from live journal (ignore compaction index)."""
    annex = ENV / "data" / "annex44"
    names = {0: "seg_a.bin", 1: "seg_b.bin", 2: "seg_c.bin"}
    out = {i: bytearray((annex / n).read_bytes()) for i, n in names.items()}
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    watermark = 2**31 - 1
    markers: list[tuple[int, int]] = []
    for i, ln in enumerate(lines):
        if ln.startswith("WATERMARK|"):
            watermark = int(ln.split("|", 1)[1])
        elif ln.startswith("CHK|"):
            markers.append((i, int(ln.split("|", 1)[1])))
    win_idx = -1
    max_ep = -1
    for idx, ep in markers:
        if ep <= watermark and (ep > max_ep or (ep == max_ep and idx > win_idx)):
            max_ep = ep
            win_idx = idx
    if win_idx < 0:
        return {i: bytes(b) for i, b in out.items()}, ""
    end = len(lines)
    for idx, _ in markers:
        if win_idx < idx < end:
            end = idx
    seal_parts = [lines[win_idx]]
    for ln in lines[win_idx + 1 : end]:
        if not ln.startswith("XOR|"):
            continue
        seal_parts.append(ln)
        _, seg_s, off_s, hx = ln.split("|", 3)
        seg = int(seg_s)
        off = int(off_s)
        out[seg][off] ^= int(hx, 16)
    seal = _sha256_hex("\n".join(seal_parts).encode())
    return {i: bytes(b) for i, b in out.items()}, seal


def _materialize() -> tuple[dict[int, bytes], str]:
    return _materialize_from(WAL.read_text())


def _start_alg_keys() -> list[str]:
    keys: list[str] = []
    in_block = False
    for ln in (ENV / "docs" / "math_b.toml").read_text().splitlines():
        s = ln.strip()
        if s.startswith("[closed_algebra]"):
            in_block = True
            continue
        if in_block and s.startswith("["):
            break
        if in_block and s.startswith("start"):
            raw = s.split(chr(61), 1)[1].strip()
            for part in raw.strip("[]").split(","):
                part = part.strip().strip('"').strip("'")
                if part:
                    keys.append(part)
    return keys


def _remap_fixpoint(start: list[str] | None = None) -> list[str]:
    start = list(start if start is not None else _start_alg_keys())
    remap: dict[str, str] = {}
    pending_from: str | None = None
    for ln in ROT.read_text().splitlines():
        s = ln.strip()
        if s.startswith("from"):
            pending_from = s.split(chr(61), 1)[1].strip().strip('"')
        elif s.startswith("to") and pending_from is not None:
            remap[pending_from] = s.split(chr(61), 1)[1].strip().strip('"')
            pending_from = None
    out = list(start)
    for _ in range(64):
        changed = False
        nxt = []
        for k in out:
            if k in remap and remap[k] != k:
                nxt.append(remap[k])
                changed = True
            else:
                nxt.append(k)
        out = nxt
        if not changed:
            break
    return out


def _expected_alg_keys() -> list[str]:
    return sorted(_remap_fixpoint())


def _fp() -> str:
    return ",".join(_expected_alg_keys())


def _expected_digest() -> str:
    segs, seal = _materialize()
    keyset = _keyset()
    fp = _fp()
    buf = bytearray()
    for i in range(3):
        seg = segs[i]
        k = keyset[i % len(keyset)]
        kb = _u64_le(k)
        folded = bytes(seg[j] ^ kb[j % 8] ^ (i & 0xFF) for j in range(len(seg)))
        buf.extend(folded)
    buf.extend(fp.encode())
    buf.append(ord("|"))
    buf.extend(seal.encode())
    return _sha256_hex(bytes(buf))


def _expected_nest(fp: str | None = None) -> list[float]:
    gens = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.5, 0.0],
        [0.0, 0.0, 1.0, 0.25],
    ]
    span_order = [0, 2, 1]
    nest_depth = 3
    if fp is None:
        fp = _fp()
    dim = 4
    out = [0.0] * dim
    for L in range(nest_depth):
        for t in range(dim):
            g = gens[span_order[t % len(span_order)]]
            out[t] += g[t] * float(L + 1)
    bias = 0.01 * float(nest_depth) * float(len(fp))
    return [x + bias for x in out]


def _rot_arm_ids() -> list[str]:
    arms: list[str] = []
    for ln in ROT.read_text().splitlines():
        ln = ln.strip()
        if ln.startswith("id"):
            arms.append(ln.split(chr(61), 1)[1].strip().strip('"'))
    return arms


def _lane_ids() -> list[str]:
    return [
        ln.strip()
        for ln in (ENV / "data" / "id_list.txt").read_text().splitlines()
        if ln.strip()
    ]


def _expected_run_digest(lanes: list[dict]) -> str:
    canon = json.dumps(lanes, separators=(",", ":"), sort_keys=True)
    return _sha256_hex(canon.encode())


def _body_for(bind_ref: str) -> str:
    return _sha256_hex(bind_ref.encode())[:8]


@pytest.fixture(scope="module", autouse=True)
def _fresh_run():
    _clear_outputs()
    _run_hs()
    yield


def test_p01_schema_lanes():
    """Lane schema plus watermark-bound journal digests after live ingest."""
    rep = _load_report()
    ids = _lane_ids()
    assert rep["lane_ids"] == ids
    assert len(rep["lanes"]) == len(ids)
    exp = _expected_digest()
    for i, lane in enumerate(rep["lanes"]):
        assert lane["lane_id"] == ids[i]
        assert lane["seg_order"] == [0, 1, 2]
        assert isinstance(lane["digest_hex"], str)
        assert len(lane["digest_hex"]) == 64
        assert lane["digest_hex"] == exp


def test_p02_digest_seal():
    """digest_hex matches journal+fold+fingerprint+seal under WATERMARK."""
    rep = _load_report()
    exp = _expected_digest()
    for lane in rep["lanes"]:
        assert lane["digest_hex"] == exp
    _, seal = _materialize()
    assert len(seal) == 64


def test_p03_fixpoint_keys():
    """Fixpoint remaps: terminal keys, no intermediate chain hops."""
    rep = _load_report()
    exp = _expected_alg_keys()
    start = set(_start_alg_keys())
    hops: set[str] = set()
    pending_from: str | None = None
    for ln in ROT.read_text().splitlines():
        s = ln.strip()
        if s.startswith("from"):
            pending_from = s.split(chr(61), 1)[1].strip().strip('"')
            hops.add(pending_from)
        elif s.startswith("to") and pending_from is not None:
            hops.add(s.split(chr(61), 1)[1].strip().strip('"'))
            pending_from = None
    intermediates = hops - start - set(exp)
    for lane in rep["lanes"]:
        assert sorted(lane["alg_keys"]) == exp
        for k in intermediates:
            assert k not in lane["alg_keys"]
        for k in start:
            assert k not in lane["alg_keys"]


def test_p04_ledger_bodies():
    """script_rows cardinality, ledger binds, and sealed bodies."""
    rep = _load_report()
    binds = _bind_map()
    for lane in rep["lanes"]:
        rows = lane["script_rows"]
        assert len(rows) == len(binds)
        for rec in rows:
            rid = int(rec["row_id"])
            assert rec["bind_ref"] == binds[rid]
            assert rec["body"] == _body_for(binds[rid])


def test_p05_cite_agree():
    """script_rows, cite_pairs, and ledger rows share exact ordered equality."""
    rep = _load_report()
    binds = _bind_map()
    ledger = [[rid, binds[rid]] for rid in sorted(binds)]
    for lane in rep["lanes"]:
        from_rows = [[int(rec["row_id"]), rec["bind_ref"]] for rec in lane["script_rows"]]
        assert from_rows == ledger
        assert lane["cite_pairs"] == ledger
        assert lane["cite_pairs"] == from_rows


def test_p06_cold_idempotent():
    """Back-to-back cold regenerations keep digests and nest stable."""
    _run_hs()
    a = _load_report()
    _run_hs()
    b = _load_report()
    assert a["lanes"][0]["digest_hex"] == b["lanes"][0]["digest_hex"]
    assert a["lanes"][0]["nest_span"] == b["lanes"][0]["nest_span"]
    assert a["run_digest"] == b["run_digest"]


def test_p07_nest_fp_bias():
    """nest_span matches dimension-indexed walk plus fingerprint-length bias."""
    rep = _load_report()
    exp = _expected_nest()
    for lane in rep["lanes"]:
        assert lane["nest_span"] == exp
        assert lane["nest_depth"] == 3
    # Fingerprint-length bias differs from key-count bias for this fixture.
    countish = _expected_nest("xxxx")  # len 4 == key count
    assert rep["lanes"][0]["nest_span"] != countish
    assert len(_fp()) != 4


def test_p08_bias_tracks_fp_text():
    """Nest bias tracks remapped fingerprint text length, not start-set count."""
    rep = _load_report()
    fp = _fp()
    assert sorted(rep["lanes"][0]["alg_keys"]) == _expected_alg_keys()
    assert rep["lanes"][0]["nest_span"] == _expected_nest(fp)
    start_fp = ",".join(sorted(_start_alg_keys()))
    assert len(start_fp) != len(fp) or start_fp != fp
    # Even if lengths matched, wrong walk still fails; require live fp bias.
    assert rep["lanes"][0]["nest_span"] == _expected_nest(fp)


def test_p09_poison_seal():
    """Poison cache with correct fp but wrong seal must not survive cold."""
    fp = _fp()
    poison = {
        "digest_hex": "0" * 64,
        "fp": fp,
        "seal": ("f" * 8) * 8,
    }
    CACHE.write_text(json.dumps(poison))
    if REPORT.exists():
        REPORT.unlink()
    _run_hs()
    rep = _load_report()
    assert rep["lanes"][0]["digest_hex"] == _expected_digest()
    assert rep["lanes"][0]["digest_hex"] != "0" * 64
    if CACHE.exists():
        blob = json.loads(CACHE.read_text())
        assert blob.get("fp") == fp
        _, seal = _materialize()
        assert blob.get("seal") == seal


def test_p09b_poison_fp():
    """Poison cache with live seal but incorrect fingerprint must not survive."""
    _, seal = _materialize()
    live_fp = _fp()
    bad_fp = live_fp[::-1] if live_fp else "x"
    if bad_fp == live_fp:
        bad_fp = live_fp + "|x"
    poison = {
        "digest_hex": "a" * 64,
        "fp": bad_fp,
        "seal": seal,
    }
    CACHE.write_text(json.dumps(poison))
    if REPORT.exists():
        REPORT.unlink()
    _run_hs()
    rep = _load_report()
    assert rep["lanes"][0]["digest_hex"] == _expected_digest()
    assert rep["lanes"][0]["digest_hex"] != "a" * 64


def test_p10_rot_arms():
    """rot_arms and fixpoint keys remain coherent together."""
    rep = _load_report()
    assert rep["rot_arms"] == _rot_arm_ids()
    assert sorted(rep["lanes"][0]["alg_keys"]) == _expected_alg_keys()


def test_p11_wm_promote():
    """Raising WATERMARK to admit a higher CHK retargets digests and seals."""
    backup = WAL.read_text()
    try:
        # Fixture has CHK|99 above WATERMARK|50; promote watermark to 99.
        shifted = backup.replace("WATERMARK|50", "WATERMARK|99", 1)
        WAL.write_text(shifted)
        _clear_outputs()
        _run_hs()
        rep = _load_report()
        assert rep["lanes"][0]["digest_hex"] == _expected_digest()
        assert sorted(rep["lanes"][0]["alg_keys"]) == _expected_alg_keys()
        assert rep["lanes"][0]["nest_span"] == _expected_nest()
        # Digest under WM 99 must differ from WM 50.
        WAL.write_text(backup)
        dig_old = _expected_digest()
        WAL.write_text(shifted)
        dig_new = _expected_digest()
        assert dig_new != dig_old
        assert rep["lanes"][0]["digest_hex"] == dig_new
    finally:
        WAL.write_text(backup)
        _clear_outputs()
        _run_hs()


def test_p11b_wm_exclude():
    """CHK epochs above WATERMARK must not drive digests."""
    backup = WAL.read_text()
    try:
        base_dig = _expected_digest()
        nl = "\n"
        extra = backup + ("" if backup[-1:] == nl else nl)
        # Epoch 80 is still above WATERMARK 50, so digests must stay put.
        extra += "CHK|80\nXOR|0|0|99\nXOR|1|0|88\nXOR|2|0|77\n"
        WAL.write_text(extra)
        _clear_outputs()
        _run_hs()
        rep = _load_report()
        assert rep["lanes"][0]["digest_hex"] == base_dig
        assert rep["lanes"][0]["nest_span"] == _expected_nest()
    finally:
        WAL.write_text(backup)
        _clear_outputs()
        _run_hs()


def test_p12_rot_retarget():
    """Held-out rotation hop retargets alg_keys, nest (via fp length), and digests."""
    backup = ROT.read_text()
    try:
        extra_id = "arm-r6"
        src = [k for k in _remap_fixpoint() if k.startswith(_start_alg_keys()[0])][0]
        dst = src + "zz"
        nl = "\n"
        blob = backup + ("" if backup[-1:] == nl else nl)
        blob += (
            "\n[[arms]]\nid = \""
            + extra_id
            + "\"\nfrom = \""
            + src
            + "\"\nto = \""
            + dst
            + "\"\n"
        )
        ROT.write_text(blob)
        _clear_outputs()
        _run_hs()
        rep = _load_report()
        exp_keys = _expected_alg_keys()
        assert dst in exp_keys
        assert src not in exp_keys
        assert sorted(rep["lanes"][0]["alg_keys"]) == exp_keys
        assert rep["lanes"][0]["digest_hex"] == _expected_digest()
        assert rep["lanes"][0]["nest_span"] == _expected_nest()
        assert extra_id in rep["rot_arms"]
        # Fingerprint length moved, so nest must differ from the default fixture nest.
        default_fp_len = len("orb-a2,orb-b2,orb-c2,orb-d2")
        assert len(_fp()) != default_fp_len
    finally:
        ROT.write_text(backup)
        _clear_outputs()
        _run_hs()


def test_p13_run_digest():
    """Terminal audit carries remaps/nest/journal digests and run_digest."""
    rep = _load_report()
    assert sorted(rep["lanes"][0]["alg_keys"]) == _expected_alg_keys()
    assert rep["lanes"][0]["nest_span"] == _expected_nest()
    assert rep["lanes"][0]["digest_hex"] == _expected_digest()
    assert rep["run_digest"] == _expected_run_digest(rep["lanes"])
    assert len(rep["run_digest"]) == 64


def test_p14_ckpt_stale():
    """Stale compaction index must not override WATERMARK journal selection."""
    backup = IDX.read_text()
    wal_backup = WAL.read_text()
    try:
        IDX.write_text('epoch = 1\nnote = "stale_probe"\n')
        # Promote a new eligible epoch under watermark; idx still points at 1.
        # Insert before the above-watermark CHK|99 block by appending under WM.
        # Use epoch 40 (<=50) so it becomes the live window.
        extra = wal_backup.replace(
            "CHK|99\n",
            "CHK|40\nXOR|0|0|55\nXOR|1|0|66\nXOR|2|0|77\nCHK|99\n",
            1,
        )
        WAL.write_text(extra)
        _clear_outputs()
        _run_hs()
        rep = _load_report()
        assert rep["lanes"][0]["digest_hex"] == _expected_digest()
        WAL.write_text(wal_backup)
        dig_old = _expected_digest()
        WAL.write_text(extra)
        dig_new = _expected_digest()
        assert dig_new != dig_old
        assert rep["lanes"][0]["digest_hex"] == dig_new
    finally:
        IDX.write_text(backup)
        WAL.write_text(wal_backup)
        _clear_outputs()
        _run_hs()


def test_p15_warm_matches_cold():
    """After a cold run, a warm restart produces identical terminal values."""
    _clear_outputs()
    _run_hs()
    cold = _load_report()
    _run_hs(warm=True)
    warm = _load_report()
    assert warm["lanes"][0]["digest_hex"] == cold["lanes"][0]["digest_hex"]
    assert warm["lanes"][0]["nest_span"] == cold["lanes"][0]["nest_span"]
    assert warm["run_digest"] == cold["run_digest"]
    assert sorted(warm["lanes"][0]["alg_keys"]) == sorted(cold["lanes"][0]["alg_keys"])


def test_p15b_poison_then_warm():
    """Warm restart must revalidate cache seal and overwrite a poison cache."""
    _clear_outputs()
    _run_hs()
    exp = _expected_digest()
    _, seal = _materialize()
    CACHE.write_text(
        json.dumps({"digest_hex": "b" * 64, "fp": _fp(), "seal": ("c" * 8) * 8})
    )
    if REPORT.exists():
        REPORT.unlink()
    _run_hs(warm=True)
    rep = _load_report()
    assert rep["lanes"][0]["digest_hex"] == exp
    assert rep["lanes"][0]["digest_hex"] != "b" * 64
    if CACHE.exists():
        blob = json.loads(CACHE.read_text())
        assert blob.get("seal") == seal
        assert blob.get("fp") == _fp()


def test_p16_triple_agree():
    """After WATERMARK promotion, digest, seal-backed cache, and nest stay consistent."""
    backup = WAL.read_text()
    try:
        shifted = backup.replace("WATERMARK|50", "WATERMARK|99", 1)
        WAL.write_text(shifted)
        _clear_outputs()
        _run_hs()
        rep = _load_report()
        dig = _expected_digest()
        nest = _expected_nest()
        assert rep["lanes"][0]["digest_hex"] == dig
        assert rep["lanes"][0]["nest_span"] == nest
        assert sorted(rep["lanes"][0]["alg_keys"]) == _expected_alg_keys()
        if CACHE.exists():
            blob = json.loads(CACHE.read_text())
            _, seal = _materialize()
            assert blob.get("seal") == seal
            assert blob.get("fp") == _fp()
            assert blob.get("digest_hex") == dig
        assert STAGE_SUMMARY.exists()
        stage = json.loads(STAGE_SUMMARY.read_text())
        assert isinstance(stage.get("status"), str) and bool(stage.get("status"))
    finally:
        WAL.write_text(backup)
        _clear_outputs()
        _run_hs()
