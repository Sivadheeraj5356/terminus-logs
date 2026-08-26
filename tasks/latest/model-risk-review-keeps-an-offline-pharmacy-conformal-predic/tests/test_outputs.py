#!/usr/bin/env python3
"""Domain checks for pharmacy jurisdiction readiness brief rebuild."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
OUT = Path("/app/output/readiness_gonogo_brief.json")
RUN = ENV / "scripts" / "run_k4.sh"
BUILD = ENV / "scripts" / "build_k4.sh"
OBS = ENV / "tools" / "obs_k4"

FRONT_A = ENV / "k4" / "x2" / ("x2_" + "mux.ts")
FRONT_B = ENV / "k4" / "x3" / ("frag" + "_buf.ts")
FRONT_C = ENV / "n8" / "q1" / ("ops" + "_mux.ts")
FRONT_D = ENV / "n8" / "q4" / ("pack" + "_emit.ts")

ABL_A = """export function weave_q(stamp: number, prev: string[], key: number): string[] {
  void stamp;
  void key;
  return prev.slice().sort();
}
"""

ABL_B = """export function span_q(totals: number[], stamp: number, fam: number): number[] {
  void stamp;
  void fam;
  return totals.slice();
}
"""

ABL_C = """export function latch_d(pairId: string, clauses: string[]): string[] {
  const left = pairId.split("|")[0] || "";
  const pref = left.toLowerCase();
  const out: string[] = [];
  for (const c of clauses) {
    const board = c.split(".")[0] || "";
    if (board.toLowerCase() === pref) out.push(c);
  }
  return Array.from(new Set(out)).sort();
}
"""

ABL_D = """export function emit_v(
  rows: object[],
  fam: number,
  digest: string
): object[] {
  void fam;
  const out: object[] = [];
  for (let i = 0; i < rows.length; i++) {
    out.push({
      trig_id: `t${i}`,
      metric_fam: 1,
      bind_stamp: 0,
      hx_ref: digest,
    });
  }
  return out;
}
"""


def _run(cmd: list[str], env: dict | None = None) -> subprocess.CompletedProcess[str]:
    base = os.environ.copy()
    base["K4" + "_ROOT"] = str(ENV)
    if env:
        base.update(env)
    return subprocess.run(
        cmd,
        cwd=str(ENV),
        env=base,
        text=True,
        capture_output=True,
        check=False,
    )


def _build() -> None:
    r = _run(["bash", str(BUILD)])
    assert r.returncode == 0, r.stderr + r.stdout


def _emit(root: Path | None = None, out: Path | None = None) -> Path:
    root = root or (ENV / "data" / "pack_tr")
    out = out or OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    r = _run(
        [
            "bash",
            str(RUN),
            "--root",
            str(root),
            "--out",
            str(out),
        ]
    )
    assert r.returncode == 0, r.stderr + r.stdout
    return out


def _load(path: Path | None = None) -> dict:
    path = path or OUT
    return json.loads(path.read_text())


def _binds() -> list[dict]:
    cal = ENV / "data" / "cal"
    rows = []
    for p in sorted(cal.glob("bind_*.json")):
        rows.append(json.loads(p.read_text()))
    return rows


def _win_bind() -> dict:
    binds = _binds()
    return max(binds, key=lambda b: b["stamp"])


def _ledger_cids_for(boards: set[str]) -> list[str]:
    text = (ENV / "data" / "long_ctx" / "ledger_mfest.toml").read_text()
    cids: list[str] = []
    cur_board = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("board"):
            cur_board = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("cids") and cur_board in boards:
            cids.extend(json.loads(line.split("=", 1)[1].strip()))
    return cids


def _swap_and_run(path: Path, body: str) -> dict:
    original = path.read_text()
    try:
        path.write_text(body)
        _build()
        _emit()
        return _load()
    finally:
        path.write_text(original)
        _build()
        _emit()


@pytest.fixture(scope="module", autouse=True)
def _module_build() -> None:
    _build()
    _emit()


def test_w01_stable() -> None:
    """Training pack rebuild is schema-valid with stable brief_digest across consecutive runs."""
    _emit()
    a = _load()
    assert a["schema_ver"] == 1
    digest = a["brief_digest"]
    assert isinstance(digest, str) and len(digest) == 64
    assert all(ch in "0123456789abcdef" for ch in digest)
    assert a["gate_rows"] and a["rb_rows"] and a["seg_trace"]
    d1 = a["brief_digest"]
    _emit()
    b = _load()
    assert b["brief_digest"] == d1


def test_w02_repeat() -> None:
    """Annex rebind updates seg_trace when bind_b stamp and vector advance."""
    bind_b = ENV / "data" / "cal" / "bind_b.json"
    original = bind_b.read_text()
    try:
        doc = json.loads(original)
        before = _emit()
        before_doc = _load(before)
        doc["stamp"] = int(doc["stamp"]) + 50
        doc["vec"] = [v + 3 for v in doc["vec"]]
        bind_b.write_text(json.dumps(doc, indent=2) + "\n")
        after = _load(_emit())
        assert after["seg_trace"]["vec"] != before_doc["seg_trace"]["vec"]
        assert after["seg_trace"]["stamp"] == doc["stamp"]
    finally:
        bind_b.write_text(original)
        _emit()


def test_w03_join() -> None:
    """Lattice join yields ledger clause ids and active-board disc_bind projection."""
    doc = _load(_emit())
    row = doc["gate_rows"][0]
    expected = sorted(
        set(
            json.loads((ENV / "data" / "pack_tr" / "wk" / "net_a.json").read_text())[
                "seed_" + "cids"
            ]
            + json.loads((ENV / "data" / "pack_tr" / "wk" / "net_b.json").read_text())[
                "seed_" + "cids"
            ]
            + _ledger_cids_for({"CA", "OR"})
        )
    )
    assert row["clause_ids"] == expected
    projected = sorted(
        c for c in row["clause_ids"] if c.split(".", 1)[0].upper() == "OR"
    )
    assert row["disc_bind"] == projected


def test_w04_auth() -> None:
    """Disclosure binding keeps only the active board authority clauses."""
    doc = _load(_emit())
    row = doc["gate_rows"][0]
    for cid in row["disc_bind"]:
        assert cid.split(".", 1)[0].upper() == "OR"
    assert row["disc_bind"]
    assert all(c.split(".", 1)[0].upper() != "CA" for c in row["disc_bind"])


def test_w05_rows() -> None:
    """Rollback trigger rows carry required fields bound to seg_trace and brief_digest."""
    doc = _load(_emit())
    assert len(doc["rb_rows"]) == len(doc["gate_rows"])
    for i, rb in enumerate(doc["rb_rows"]):
        assert rb["trig_id"] == f"t{i}"
        assert "metric_fam" in rb
        assert "bind_stamp" in rb
        assert rb["hx_ref"] == doc["brief_digest"]
        assert rb["bind_stamp"] == doc["seg_trace"]["stamp"]


def test_w06_fam() -> None:
    """Post-selection metric_fam matches the winning calibration sheet, not training-era 1."""
    doc = _load(_emit())
    win = _win_bind()
    assert doc["seg_trace"]["fam"] == win["fam"]
    assert win["fam"] != 1
    for rb in doc["rb_rows"]:
        assert rb["metric_fam"] == win["fam"]
        assert rb["metric_fam"] != 1


def test_w07_front_a() -> None:
    """Ablating the lattice-join module incoheres clause id lists vs the repaired build."""
    broken = _swap_and_run(FRONT_A, ABL_A)
    good = _load()
    assert broken["gate_rows"][0]["clause_ids"] != good["gate_rows"][0]["clause_ids"]


def test_w08_front_b() -> None:
    """Ablating the annex-rebind module breaks seg_trace vector alignment."""
    broken = _swap_and_run(FRONT_B, ABL_B)
    good = _load()
    assert broken["seg_trace"]["vec"] != good["seg_trace"]["vec"]


def test_w09_front_c() -> None:
    """Ablating the authority-latch module breaks disc_bind under the training pair."""
    broken = _swap_and_run(FRONT_C, ABL_C)
    good = _load()
    assert broken["gate_rows"][0]["disc_bind"] != good["gate_rows"][0]["disc_bind"]


def test_w10_cohort() -> None:
    """All xp pair packs report zero obligation_violations via obs_k4."""
    _build()
    _emit()
    r = _run(["node", str(OBS), "--env", str(ENV)])
    assert r.returncode == 0, r.stderr + r.stdout
    m = re.search(r"obligation_violations=(\d+)", r.stdout)
    assert m is not None
    assert int(m.group(1)) == 0


def test_w11_lock() -> None:
    """Manual JSON overwrite is replaced by a regenerated brief on rerun."""
    OUT.write_text(json.dumps({"schema_ver": 1, "brief_digest": "0" * 64}) + "\n")
    doc = _load(_emit())
    assert doc["brief_digest"] != "0" * 64
    assert doc["gate_rows"] and doc["rb_rows"]


def test_w12_clean() -> None:
    """Ablating the rollback-emit module breaks metric_fam lineage binding."""
    broken = _swap_and_run(FRONT_D, ABL_D)
    good = _load()
    assert broken["rb_rows"][0]["metric_fam"] != good["rb_rows"][0]["metric_fam"]
    assert good["rb_rows"][0]["metric_fam"] == good["seg_trace"]["fam"]
