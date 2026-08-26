#!/usr/bin/env python3
"""Domain verifier for k9 annex witness/replay matrix artifacts."""

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

WIT = Path("/app/output/replay_witness.json")
SPEC = Path("/app/output/inferred_spec.json")
STAGE = Path("/app/output/stage/hud.json")
BATCH = Path("/app/environment/data/p39/batch.jsonl")
ROT = Path("/app/environment/data/p39/rot.log")
CTRL = Path("/app/environment/docs/ctrl_k84.md")
SCRATCH = Path("/app/environment/r43/.scratch/cur.json")
FOLD_CACHE = Path("/app/environment/r43/.scratch/fold_cache.json")
PIN = Path("/app/environment/data/p39/pin_table.toml")


def _run_matrix() -> int:
    os.makedirs("/app/output/stage", exist_ok=True)
    subprocess.run(["bash", "/app/environment/scripts/build_lab.sh"], check=True, cwd="/app")
    proc = subprocess.run(
        [
            "/app/environment/tools/k9_verify",
            "--matrix",
            "all",
            "--witness-out",
            "/app/output/replay_witness.json",
            "--spec-out",
            "/app/output/inferred_spec.json",
        ],
        cwd="/app",
    )
    return int(proc.returncode)


def _load_wit() -> dict:
    assert WIT.exists(), "missing replay_witness.json"
    return json.loads(WIT.read_text(encoding="utf-8"))


def _cells(doc: dict):
    for g, profiles in (doc.get("grids") or {}).items():
        for pid, cell in profiles.items():
            yield g, pid, cell


def _sha(s: str) -> str:
    tool = "sha" + "256" + "sum"
    proc = subprocess.run([tool], input=s.encode("utf-8"), check=True, capture_output=True)
    return proc.stdout.decode().split()[0]


def _pins() -> dict:
    sections = {}
    cur = None
    for line in PIN.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = line[1:-1]
            sections[cur] = {}
            continue
        if "=" in line and cur:
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if v.startswith("["):
                items = [x.strip().strip('"') for x in v.strip("[]").split(",") if x.strip()]
                sections[cur][k] = items
            else:
                sections[cur][k] = v.strip('"')
    return sections


def _expected_eff_keys(grid: str) -> list:
    sc = json.loads(Path(f"/app/environment/scenarios/{grid}.json").read_text(encoding="utf-8"))
    base = dict(sc["base_cfg"])
    overlay = dict(sc["overlay"])
    keys = set(base) | {k for k in overlay if not str(k).startswith("__") and k != "x_def"}
    return sorted(keys)


@pytest.fixture(scope="module", autouse=True)
def _ensure_graded():
    rc = _run_matrix()
    assert rc == 0, "graded matrix must exit 0"


def test_annex_eff_keys_clean():
    """pollution keys absent from effective cfg keys across the matrix."""
    doc = _load_wit()
    assert set(doc.get("grids") or {}) >= {"pocket", "ridge", "slate", "marsh"}
    banned = {"__p", "x_def"}
    for g, pid, cell in _cells(doc):
        keys = set(cell.get("eff_keys") or [])
        assert not (keys & banned), (g, pid, keys)


def test_annex_cfg_fingerprint():
    """cfg_fp matches sha256 over sorted eff_keys; keys match clean bind set."""
    doc = _load_wit()
    for g, pid, cell in _cells(doc):
        keys = list(cell.get("eff_keys") or [])
        assert keys == _expected_eff_keys(g), (g, pid, keys)
        assert cell.get("cfg_fp") == _sha(",".join(keys)), (g, pid)


def test_annex_pri_lo_epoch():
    """pri_lo ok rows bind e_tag to e_lo."""
    doc = _load_wit()
    saw = 0
    for g, pid, cell in _cells(doc):
        if pid != "pri_lo":
            continue
        ok_rows = [r for r in cell.get("rows") or [] if r.get("plan") == "ok"]
        assert ok_rows, (g, pid)
        for r in ok_rows:
            assert r.get("e_tag") == "e_lo", (g, pid, r)
            kid = str(r.get("kid", ""))
            assert not kid.startswith("k_evil")
            assert kid != "k_root"
        saw += 1
    assert saw >= 4


def test_annex_pri_hi_epoch():
    """pri_hi ok rows bind e_tag to e_hi."""
    doc = _load_wit()
    saw = 0
    for g, pid, cell in _cells(doc):
        if pid != "pri_hi":
            continue
        ok_rows = [r for r in cell.get("rows") or [] if r.get("plan") == "ok"]
        assert ok_rows, (g, pid)
        for r in ok_rows:
            assert r.get("e_tag") == "e_hi", (g, pid, r)
            assert r.get("kid") != "k_root"
        saw += 1
    assert saw >= 4


def test_annex_epoch_isolation():
    """east/west grids enforce epoch-isolated gate outcomes from folded journal bands."""
    doc = _load_wit()
    pins = _pins()
    hi_allow = set(pins["e_hi"]["allow"])
    lo_allow = set(pins["e_lo"]["allow"])
    hi_only = sorted(hi_allow - lo_allow)
    lo_only = sorted(lo_allow - hi_allow)
    assert hi_only and lo_only

    def rows(grid, profile):
        return {r["tid"]: r for r in doc["grids"][grid][profile]["rows"]}

    slate_lo = rows("slate", "pri_lo")
    assert slate_lo["s01"]["plan"] == "ok" and slate_lo["s01"]["gate"] == "pass"
    assert slate_lo["s02"]["kid"] == hi_only[0] and slate_lo["s02"]["gate"] == "hold"

    marsh_lo = rows("marsh", "pri_lo")
    assert marsh_lo["m01"]["gate"] == "pass" and marsh_lo["m01"]["plan"] == "ok"
    assert marsh_lo["m02"]["kid"] == lo_only[0] and marsh_lo["m02"]["gate"] == "pass" and marsh_lo["m02"]["plan"] == "ok"

    marsh_hi = rows("marsh", "pri_hi")
    assert marsh_hi["m02"]["kid"] == lo_only[0] and marsh_hi["m02"]["gate"] == "hold"

    ridge_lo = rows("ridge", "pri_lo")
    assert ridge_lo["r02"]["kid"] == hi_only[0] and ridge_lo["r02"]["gate"] == "hold"

    ridge_hi = rows("ridge", "pri_hi")
    assert ridge_hi["r02"]["kid"] == hi_only[0] and ridge_hi["r02"]["gate"] == "pass"


def test_annex_meta_digest():
    """clean bind fingerprint and metamorphic alignment on north/south grids."""
    doc = _load_wit()
    for g in ("pocket", "ridge"):
        for pid in ("pri_hi", "pri_lo"):
            cell = doc["grids"][g][pid]
            assert cell.get("meta_state") == "aligned", (g, pid)
            keys = list(cell.get("eff_keys") or [])
            assert keys == _expected_eff_keys(g), (g, pid, keys)
            assert cell.get("cfg_fp") == _sha(",".join(keys))
            dig = cell.get("instance_digest") or ""
            assert len(dig) == 64


def test_annex_hud_not_graded():
    """stage HUD tallies are not a substitute for terminal witness digests."""
    doc = _load_wit()
    assert STAGE.exists()
    hud = json.loads(STAGE.read_text(encoding="utf-8"))
    assert hud.get("hud_only") is True
    blob = STAGE.read_text(encoding="utf-8")
    assert "instance_digest" not in blob
    assert "cfg_fp" not in blob
    pins = _pins()
    lo_only = sorted(set(pins["e_lo"]["allow"]) - set(pins["e_hi"]["allow"]))[0]
    marsh_lo = {r["tid"]: r for r in doc["grids"]["marsh"]["pri_lo"]["rows"]}
    assert marsh_lo["m02"]["kid"] == lo_only and marsh_lo["m02"]["gate"] == "pass"
    for g, pid, cell in _cells(doc):
        assert cell.get("instance_digest")


def test_annex_rst9_recovery():
    """documented recovery after rst9 preserves annex bytes and restores scratch."""
    before = BATCH.read_bytes()
    rot_before = ROT.read_bytes()
    subprocess.run(["bash", "/app/environment/migrations/rst9.sh"], check=True)
    assert not SCRATCH.exists()
    assert not FOLD_CACHE.exists()
    subprocess.run(
        [
            "bash",
            "/app/environment/migrations/rst9.sh",
            "--restore-from",
            "/app/environment/data/p39/pin_table.toml",
        ],
        check=True,
    )
    assert SCRATCH.exists()
    cur = json.loads(SCRATCH.read_text(encoding="utf-8"))
    pins = _pins()
    assert pins["e_hi"]["allow"][0] in (cur.get("allow") or [])
    assert BATCH.read_bytes() == before
    assert ROT.read_bytes() == rot_before
    assert CTRL.exists()
    assert _run_matrix() == 0
    doc = _load_wit()
    lo_only = sorted(set(pins["e_lo"]["allow"]) - set(pins["e_hi"]["allow"]))[0]
    marsh_lo = {r["tid"]: r for r in doc["grids"]["marsh"]["pri_lo"]["rows"]}
    assert marsh_lo["m02"]["kid"] == lo_only and marsh_lo["m02"]["gate"] == "pass"


def test_annex_rot_append_probe():
    """appending a journal rev flips gate without pin_table edits; cache must invalidate."""
    pins = _pins()
    sc = json.loads(Path("/app/environment/scenarios/pocket.json").read_text(encoding="utf-8"))
    lo_allow = set(pins["e_lo"]["allow"])
    target = None
    for tok in sc["tokens"]:
        if tok.get("kid") in lo_allow:
            target = tok
            break
    assert target is not None
    kid = str(target["kid"])
    tid = str(target["id"])
    backup = ROT.read_text(encoding="utf-8")
    pin_bytes = PIN.read_bytes()
    try:
        with ROT.open("a", encoding="utf-8") as fh:
            fh.write(f"\nevt=9999 epoch=e_lo kid={kid} op=rev ts=2099-01-01T00:00:00Z note=slot_0\n")
        # Ensure journal mtime is strictly newer than any fold cache from the prior matrix.
        now = time.time() + 5.0
        os.utime(ROT, (now, now))
        assert PIN.read_bytes() == pin_bytes
        assert _run_matrix() == 0
        doc = _load_wit()
        pocket_lo = {r["tid"]: r for r in doc["grids"]["pocket"]["pri_lo"]["rows"]}
        assert pocket_lo[tid]["kid"] == kid
        assert pocket_lo[tid]["gate"] == "hold", pocket_lo[tid]
        assert pocket_lo[tid]["plan"] == "skip", pocket_lo[tid]
    finally:
        ROT.write_text(backup, encoding="utf-8")
        if FOLD_CACHE.exists():
            FOLD_CACHE.unlink()
        assert _run_matrix() == 0
        doc = _load_wit()
        pocket_lo = {r["tid"]: r for r in doc["grids"]["pocket"]["pri_lo"]["rows"]}
        assert pocket_lo[tid]["gate"] == "pass" and pocket_lo[tid]["plan"] == "ok"


def test_annex_inferred_kinds():
    """inferred_spec documents cfg/witness/journal clause kinds and band map."""
    assert SPEC.exists()
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    assert spec.get("schema") == "k84-spec-v1"
    clauses = spec.get("clauses") or []
    assert isinstance(clauses, list)
    assert len(clauses) == 3
    kinds = {c.get("kind") for c in clauses}
    assert kinds == {"cfg_iso", "w_bind", "rev_iso"}
    for c in clauses:
        assert isinstance(c.get("note"), str) and len(c.get("note") or "") > 8
        assert isinstance(c.get("aid"), str) and len(c.get("aid") or "") >= 2
    assert spec.get("band_epoch") == {"pri_hi": "e_hi", "pri_lo": "e_lo"}
    assert SPEC.read_bytes()
    wit = _load_wit()
    assert set(wit.get("grids") or {}) >= {"pocket", "ridge", "slate", "marsh"}
    for g in ("pocket", "ridge", "slate", "marsh"):
        assert set(wit["grids"][g]) >= {"pri_hi", "pri_lo"}
