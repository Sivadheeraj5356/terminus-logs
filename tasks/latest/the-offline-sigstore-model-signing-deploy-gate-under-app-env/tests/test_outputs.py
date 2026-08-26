#!/usr/bin/env python3
"""Domain verifier for model-sigstore-deploy-gate (Go redesign)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
OUT = Path("/app/output/mx_pack.json")
SIGN = ENV / "fixtures" / "sign"
XROWS = ENV / "fixtures" / "xrows"
CACHE = ENV / "fixtures" / "cache_stale"

HOME = {"ca": "pH", "cb": "qH", "cc": "tH"}
RANK = {
    "p1": 1,
    "p2": 2,
    "pH": 3,
    "q1": 1,
    "q2": 2,
    "qH": 3,
    "t1": 1,
    "t2": 2,
    "tH": 3,
    "xF": 0,
    "xG": 0,
}
ALIAS = {"pX": "p2", "qX": "q2", "tX": "t2"}


def _resolve(p: str) -> str:
    return ALIAS.get(p, p)


def _rank(p: str) -> int:
    return RANK.get(_resolve(p), 0)


def _covers(have: str, need: str) -> bool:
    h, n = _resolve(have), _resolve(need)
    if _rank(h) == 0 or _rank(n) == 0:
        return False
    if h[0] != n[0]:
        return False
    return _rank(h) >= _rank(n)


def _join(a: str, b: str) -> str:
    a, b = _resolve(a), _resolve(b)
    return a if _rank(a) >= _rank(b) else b


def _fnv1a64(data: bytes) -> str:
    h = 14695981039346656037
    for b in data:
        h ^= b
        h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def _seal_hex(gate: str, n_home: int) -> str:
    return _fnv1a64(f"run0|{gate}|{n_home}".encode("utf-8"))


def _read_rows(path: Path) -> dict[str, dict]:
    m: dict[str, dict] = {}
    if not path.is_file():
        return m
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 4:
            m[parts[0]] = {
                "id": parts[0],
                "cloud": parts[1],
                "actor": parts[2],
                "gen": int(parts[3]),
                "touch": 0,
            }
    return m


def _cut_floor() -> int:
    floor = 0
    path = SIGN / "meta" / "cut.cfg"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("cut_floor="):
                floor = int(line.split("=", 1)[1])
    return floor


def _quorum_min() -> int:
    path = SIGN / "meta" / "quorum.cfg"
    q = 1
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("min_touches="):
                q = int(line.split("=", 1)[1])
    return q


def _certs() -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    path = SIGN / "certs.d" / "windows.crt"
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = line.split()
        if len(p) >= 3:
            out[p[0]] = (int(p[1]), int(p[2]))
    return out


def _times() -> dict[str, int]:
    out: dict[str, int] = {}
    path = SIGN / "log.d" / "times.jnl"
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = line.split()
        if len(p) >= 2:
            out[p[0]] = int(p[1])
    return out


def _cert_ok(mid: str) -> bool:
    c, t = _certs(), _times()
    if mid not in c or mid not in t:
        return False
    nb, na = c[mid]
    return nb <= t[mid] <= na


def _expected_fold() -> dict[str, dict]:
    m = _read_rows(SIGN / "core.d" / "models.w")
    nodes: dict[str, tuple[str, str]] = {}
    for line in (SIGN / "sig.d" / "manifest.sx").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, file_name, parent = line.split("|")
        nodes[name] = (file_name, parent)
    done: set[str] = set()

    def expand(name: str) -> None:
        if name in done:
            return
        file_name, parent = nodes[name]
        if parent != "-" and parent in nodes and parent not in done:
            expand(parent)
        for mid, row in _read_rows(SIGN / "sig.d" / file_name).items():
            if mid in m:
                m[mid]["cloud"] = row["cloud"]
                m[mid]["actor"] = _join(m[mid]["actor"], row["actor"])
                m[mid]["gen"] = max(m[mid]["gen"], row["gen"])
                m[mid]["touch"] = m[mid].get("touch", 0) + 1
            else:
                row = dict(row)
                row["touch"] = 1
                m[mid] = row
        done.add(name)

    for n in list(nodes):
        expand(n)

    bump = SIGN / "appr.d" / "bump.aw"
    for line in bump.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 3 and parts[0] in m:
            m[parts[0]]["actor"] = parts[1]
            m[parts[0]]["gen"] = int(parts[2])

    floor = 0
    active: list[int] = []
    for line in (SIGN / "meta" / "epochs.cfg").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("floor="):
            floor = int(line.split("=", 1)[1])
        elif line.startswith("active="):
            active = [int(x) for x in line.split("=", 1)[1].split(",") if x.strip()]
    revoked: set[tuple[str, int]] = set()
    for line in (SIGN / "meta" / "revoke.jnl").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "@" in line:
            mid, ep = line.rsplit("@", 1)
            revoked.add((mid, int(ep)))
    for e in sorted(a for a in active if a >= floor):
        ov = SIGN / "ovl.d" / f"e{e}.ov"
        for line in ov.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            if (parts[0], e) in revoked:
                continue
            if parts[0] in m:
                m[parts[0]]["cloud"] = parts[1]
                m[parts[0]]["actor"] = parts[2]
    return m


def _home_bound(fold: dict[str, dict]) -> dict[str, dict]:
    cut = _cut_floor()
    qmin = _quorum_min()
    out = {}
    for mid, row in fold.items():
        actor = _resolve(row["actor"])
        if actor != HOME.get(row["cloud"]):
            continue
        if row["gen"] < cut:
            continue
        if row.get("touch", 0) < qmin:
            continue
        if not _cert_ok(mid):
            continue
        out[mid] = {
            "id": row["id"],
            "cloud": row["cloud"],
            "actor": actor,
            "gen": row["gen"],
            "touch": row.get("touch", 0),
        }
    return out


def _digest_of(bound: dict[str, dict]) -> str:
    rows = [
        f"{mid}|{bound[mid]['cloud']}|{bound[mid]['actor']}|{bound[mid]['gen']}"
        for mid in bound
    ]
    rows.sort()
    text = "\n".join(rows) + ("\n" if rows else "")
    return _fnv1a64(text.encode("utf-8"))


def _parse_xrow(path: Path):
    rid = path.stem
    span = 0
    min_g = 0
    leaves: list[tuple[str, str]] = []
    cur_id = None
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("span:"):
            span = int(s.split(":", 1)[1].strip())
        elif s.startswith("min_g:"):
            min_g = int(s.split(":", 1)[1].strip())
        elif s.startswith("- id:"):
            cur_id = s.split(":", 1)[1].strip()
        elif s.startswith("need:") and cur_id:
            leaves.append((cur_id, s.split(":", 1)[1].strip()))
            cur_id = None
    return rid, span, min_g, leaves


def _expected_fresh(row_id: str, bound: dict[str, dict]):
    path = XROWS / f"{row_id}.yaml"
    _rid, span, min_g, leaves = _parse_xrow(path)
    touch = 0
    gen_n = 0
    for lid, need in leaves:
        row = bound.get(lid)
        if not row:
            continue
        if row["gen"] < min_g:
            continue
        if not _covers(row["actor"], need):
            continue
        touch += 1
        gen_n += row["gen"]
    skew = abs(touch - span)
    return {
        "id": row_id,
        "skew": skew,
        "gen_n": gen_n,
        "span": span,
        "touch": touch,
    }


def _stale_mix() -> str:
    for p in CACHE.glob("*"):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("mix:"):
                return line.split(":", 1)[1].strip()
    return ""


def _rebuild_gate():
    subprocess.run(
        ["bash", "/app/environment/scripts/weld_bin.sh"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "bash",
            "/app/environment/tools/mx_run.sh",
            "gate",
            "--out",
            "/app/output/mx_pack.json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(OUT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pack():
    return _rebuild_gate()


def test_mx_r01(pack):
    """rebuild + gate emits schema-valid mx_pack.json."""
    assert pack.get("schema_version") == 1
    assert pack.get("pack_id") == "mx_pack_v1"
    assert isinstance(pack.get("runs"), list) and pack["runs"]
    bound = _home_bound(_expected_fold())
    assert pack["asset_counts"]["nodes"] == len(bound)
    assert pack["runs"][0]["n_home"] == len(bound)
    assert pack["annex_note"] == "live"
    assert pack["asset_counts"]["cache_hits"] == 0


def test_mx_r02(pack):
    """package satisfies zero foreign-root deploy on published algebra."""
    hits = pack["asset_counts"]["foreign_hits"]
    assert hits == pack["runs"][0]["n_foreign"]
    assert hits == 0
    bound = _home_bound(_expected_fold())
    assert "m09" not in bound
    assert "m10" not in bound
    assert "m13" not in bound
    assert pack["runs"][0]["n_home"] >= 10
    assert pack["runs"][0]["n_probe"] == pack["runs"][0]["n_home"]


def test_mx_r03(pack):
    """independent deploy-probe replay agrees with package (not witness-only)."""
    bound = _home_bound(_expected_fold())
    expected = _digest_of(bound)
    assert pack["gate_digest"] == expected
    assert pack["replay_digest"] == expected
    assert pack["replay_digest"] == pack["gate_digest"]
    # trailing LF: empty-set path would differ; seed is non-empty
    assert bound


def test_mx_r04(pack):
    """revoke-window freshness holds on stress instances from xrows h1."""
    bound = _home_bound(_expected_fold())
    exp = _expected_fresh("h1", bound)
    rows = {r["id"]: r for r in pack["freshness"]}
    got = rows["h1"]
    assert got["skew"] == exp["skew"] == 0
    assert got["span"] == exp["span"]
    assert got["touch"] == exp["touch"]
    assert got["gen_n"] == exp["gen_n"]


def test_mx_r05(pack):
    """freshness / classify correct on xrows h2."""
    bound = _home_bound(_expected_fold())
    exp = _expected_fresh("h2", bound)
    rows = {r["id"]: r for r in pack["freshness"]}
    got = rows["h2"]
    assert got["skew"] == exp["skew"] == 0
    assert got["touch"] == exp["touch"]
    bands = {c["id"]: c["band"] for c in pack["classify"]}
    assert bands["h2"] == "steady"


def test_mx_r06(pack):
    """lattice-sensitive classify on xrows h3 (poison leaf excluded)."""
    bound = _home_bound(_expected_fold())
    exp = _expected_fresh("h3", bound)
    rows = {r["id"]: r for r in pack["freshness"]}
    got = rows["h3"]
    assert got["skew"] == exp["skew"] == 0
    assert got["touch"] == exp["touch"] == 2
    bands = {c["id"]: c["band"] for c in pack["classify"]}
    assert bands["h3"] == "steady"


def test_mx_r07(pack):
    """stage-digest false-green trap (settled stage insufficient)."""
    stage_dir = Path("/app/output/stage")
    assert stage_dir.is_dir(), "pack path must leave /app/output/stage present"
    stage = stage_dir / "gauge.json"
    poison = ("f" * 8) + ("e" * 8)
    decoy = ("a" * 8) + ("b" * 8)
    stage.write_text(json.dumps({"mode": "SETTLED", "seal_hex": poison}) + "\n", encoding="utf-8")
    rebuilt = _rebuild_gate()
    assert stage_dir.is_dir(), "re-gate must leave /app/output/stage present and empty of authority"
    bound = _home_bound(_expected_fold())
    gate = _digest_of(bound)
    expect_seal = _seal_hex(gate, len(bound))
    assert rebuilt["runs"][0]["seal_hex"] == expect_seal
    assert rebuilt["runs"][0]["seal_hex"] != poison
    assert rebuilt["runs"][0]["seal_hex"] != decoy
    _ = pack


def test_mx_r08(pack):
    """counter-sign JOIN then approval bump then overlay wins; revoke skips poison; cut_floor holds."""
    fold = _expected_fold()
    assert fold["m01"]["actor"] == HOME["ca"]
    assert fold["m01"]["gen"] == 2
    assert fold["m04"]["actor"] == HOME["cb"]
    assert fold["m09"]["actor"] == "xF"
    assert fold["m10"]["actor"] == "xG"
    bound = _home_bound(fold)
    assert "m01" in bound
    assert "m09" not in bound
    assert all(bound[k]["gen"] >= _cut_floor() for k in bound)
    assert pack["asset_counts"]["nodes"] == len(bound)
    assert pack["gate_digest"] == _digest_of(bound)


def test_mx_r09(pack):
    """live seal_hex bound to gate_digest and n_home; stale cache ignored."""
    bound = _home_bound(_expected_fold())
    gate = _digest_of(bound)
    expect_seal = _seal_hex(gate, len(bound))
    assert pack["runs"][0]["seal_hex"] == expect_seal
    assert pack["annex_note"] == "live"
    assert pack["asset_counts"]["cache_hits"] == 0
    mix = _stale_mix()
    assert mix
    poisoned = _fnv1a64(f"{gate}|{mix}".encode("utf-8"))
    assert pack["gate_digest"] != poisoned
    assert mix not in pack["gate_digest"]


def test_mx_r10():
    """pipeline overwrite rejects static hand-written mx_pack."""
    planted_seal = ("de" * 4) + ("ad" * 4)
    bogus = ("fe" * 4) + ("ed" * 4)
    planted = {
        "schema_version": 1,
        "pack_id": "mx_pack_v1",
        "asset_counts": {"nodes": 1, "edges": 1, "foreign_hits": 0, "cache_hits": 0},
        "runs": [
            {
                "id": "run0",
                "n_probe": 1,
                "n_home": 1,
                "n_foreign": 0,
                "seal_hex": planted_seal,
            }
        ],
        "replay_digest": bogus,
        "gate_digest": bogus,
        "freshness": [],
        "classify": [],
        "annex_note": "static",
    }
    OUT.write_text(json.dumps(planted, indent=2) + "\n", encoding="utf-8")
    rebuilt = _rebuild_gate()
    assert rebuilt["annex_note"] == "live"
    assert rebuilt["runs"][0]["seal_hex"] != planted_seal
    bound = _home_bound(_expected_fold())
    assert rebuilt["gate_digest"] == _digest_of(bound)


def test_mx_r11_cert_window_expiry():
    """expiring one cert must drop that model and recompute digests/freshness."""
    crt = SIGN / "certs.d" / "windows.crt"
    original = crt.read_text(encoding="utf-8")
    try:
        lines = []
        for line in original.splitlines():
            if line.startswith("m06 "):
                lines.append("m06 10 20")  # times.jnl has m06=25 → fail
            else:
                lines.append(line)
        crt.write_text("\n".join(lines) + "\n", encoding="utf-8")
        rebuilt = _rebuild_gate()
        bound = _home_bound(_expected_fold())
        assert "m06" not in bound
        assert rebuilt["gate_digest"] == _digest_of(bound)
        assert rebuilt["asset_counts"]["nodes"] == len(bound)
        rows = {r["id"]: r for r in rebuilt["freshness"]}
        assert rows["h2"]["touch"] == 2
        assert rows["h2"]["skew"] == 1
        bands = {c["id"]: c["band"] for c in rebuilt["classify"]}
        assert bands["h2"] == "drift"
    finally:
        crt.write_text(original, encoding="utf-8")
        _rebuild_gate()


def test_mx_r12_quorum_raise():
    """raising min_touches drops single-touch models."""
    qpath = SIGN / "meta" / "quorum.cfg"
    original = qpath.read_text(encoding="utf-8")
    try:
        qpath.write_text("min_touches=2\n", encoding="utf-8")
        rebuilt = _rebuild_gate()
        bound = _home_bound(_expected_fold())
        # seed models each appear in exactly one manifest file → all drop
        assert len(bound) == 0
        assert rebuilt["asset_counts"]["nodes"] == 0
        assert rebuilt["gate_digest"] == _digest_of(bound) == _fnv1a64(b"")
        assert rebuilt["runs"][0]["seal_hex"] == _seal_hex(rebuilt["gate_digest"], 0)
    finally:
        qpath.write_text(original, encoding="utf-8")
        _rebuild_gate()


def test_mx_r13_cut_floor_raise():
    """raising cut_floor above gen excludes otherwise home models."""
    cpath = SIGN / "meta" / "cut.cfg"
    original = cpath.read_text(encoding="utf-8")
    try:
        cpath.write_text("cut_floor=3\n", encoding="utf-8")
        rebuilt = _rebuild_gate()
        bound = _home_bound(_expected_fold())
        assert len(bound) == 0
        assert rebuilt["gate_digest"] == _digest_of(bound)
    finally:
        cpath.write_text(original, encoding="utf-8")
        _rebuild_gate()


def test_mx_r14_revoke_clear_launders_poison():
    """clearing revoke.jnl must still keep poison out via lattice (xF/xG)."""
    jnl = SIGN / "meta" / "revoke.jnl"
    original = jnl.read_text(encoding="utf-8")
    try:
        jnl.write_text("# cleared\n", encoding="utf-8")
        rebuilt = _rebuild_gate()
        fold = _expected_fold()
        # without revoke, e1 launders m09/m10 to home principals
        assert fold["m09"]["actor"] == "pH"
        assert fold["m10"]["actor"] == "qH"
        bound = _home_bound(fold)
        # but cert+quorum may admit them — they have touch 0 from DAG
        assert "m09" not in bound or bound["m09"]["actor"] == "pH"
        # touch stays 0 → quorum rejects
        assert "m09" not in bound
        assert "m10" not in bound
        assert rebuilt["gate_digest"] == _digest_of(bound)
    finally:
        jnl.write_text(original, encoding="utf-8")
        _rebuild_gate()


def test_mx_r15_epoch_floor_skips_e1():
    """raising epoch floor skips e1 overlays; home actors may not promote."""
    epath = SIGN / "meta" / "epochs.cfg"
    original = epath.read_text(encoding="utf-8")
    try:
        epath.write_text("floor=2\nactive=1,2\n", encoding="utf-8")
        rebuilt = _rebuild_gate()
        fold = _expected_fold()
        # m01 only got e1 overlay to pH; with floor=2 only e2 applies
        # m01 not in e2 → stays at bump actor p2 → not home-bound
        assert fold["m01"]["actor"] == "p2"
        bound = _home_bound(fold)
        assert "m01" not in bound
        assert "m03" in bound  # e2 promotes m03
        assert rebuilt["gate_digest"] == _digest_of(bound)
        rows = {r["id"]: r for r in rebuilt["freshness"]}
        assert rows["h1"]["touch"] == 1  # only m03 promoted when e1 skipped
    finally:
        epath.write_text(original, encoding="utf-8")
        _rebuild_gate()


def test_mx_r16_log_time_shift():
    """shifting integrated_time outside cert window drops the model."""
    tpath = SIGN / "log.d" / "times.jnl"
    original = tpath.read_text(encoding="utf-8")
    try:
        lines = []
        for line in original.splitlines():
            if line.startswith("m12 "):
                lines.append("m12 99")
            else:
                lines.append(line)
        tpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
        rebuilt = _rebuild_gate()
        bound = _home_bound(_expected_fold())
        assert "m12" not in bound
        assert rebuilt["gate_digest"] == _digest_of(bound)
    finally:
        tpath.write_text(original, encoding="utf-8")
        _rebuild_gate()


def test_mx_r17_witness_poison_ignored():
    """local.obs must never admit m13 or inflate generations."""
    bound = _home_bound(_expected_fold())
    assert "m13" not in bound
    fold = _expected_fold()
    assert fold["m01"]["gen"] == 2
    rebuilt = _rebuild_gate()
    assert rebuilt["gate_digest"] == _digest_of(bound)


def test_mx_r18_decoy_sx_ignored():
    """unmanifested federate/bundle/counter sx must not demote or insert."""
    fold = _expected_fold()
    assert "m14" not in fold
    assert fold["m01"]["actor"] == "pH"  # not federate pH gen3 path via flat replace
    bound = _home_bound(fold)
    assert "m14" not in bound
    rebuilt = _rebuild_gate()
    assert rebuilt["asset_counts"]["nodes"] == len(bound)


def test_mx_r19_trailing_lf_digest_contract():
    """digest must include trailing LF; no-LF digest must not match."""
    bound = _home_bound(_expected_fold())
    rows = [
        f"{mid}|{bound[mid]['cloud']}|{bound[mid]['actor']}|{bound[mid]['gen']}"
        for mid in bound
    ]
    rows.sort()
    with_lf = "\n".join(rows) + "\n"
    without = "\n".join(rows)
    assert _fnv1a64(with_lf.encode("utf-8")) == _digest_of(bound)
    assert _fnv1a64(without.encode("utf-8")) != _digest_of(bound)
    rebuilt = _rebuild_gate()
    assert rebuilt["gate_digest"] == _fnv1a64(with_lf.encode("utf-8"))


def test_mx_r20_xrow_mutation_live_recompute():
    """mutating xrows span forces live freshness recompute (no hardcoded skew)."""
    h1 = XROWS / "h1.yaml"
    original = h1.read_text(encoding="utf-8")
    try:
        h1.write_text(
            "id: h1\nspan: 2\nmin_g: 2\nleaves:\n"
            "  - id: m01\n    need: p2\n"
            "  - id: m02\n    need: p2\n"
            "  - id: m03\n    need: p2\n",
            encoding="utf-8",
        )
        rebuilt = _rebuild_gate()
        bound = _home_bound(_expected_fold())
        exp = _expected_fresh("h1", bound)
        rows = {r["id"]: r for r in rebuilt["freshness"]}
        assert rows["h1"]["span"] == 2
        assert rows["h1"]["touch"] == exp["touch"] == 3
        assert rows["h1"]["skew"] == 1
        bands = {c["id"]: c["band"] for c in rebuilt["classify"]}
        assert bands["h1"] == "drift"
    finally:
        h1.write_text(original, encoding="utf-8")
        _rebuild_gate()


def test_mx_r21_overlay_alias_resolution():
    """alias principals in bump must resolve before home match."""
    bump = SIGN / "appr.d" / "bump.aw"
    ov1 = SIGN / "ovl.d" / "e1.ov"
    ov2 = SIGN / "ovl.d" / "e2.ov"
    original = bump.read_text(encoding="utf-8")
    o1 = ov1.read_text(encoding="utf-8")
    o2 = ov2.read_text(encoding="utf-8")
    try:
        ov1.write_text(
            "\n".join(
                line for line in o1.splitlines() if not line.startswith("m02 ")
            )
            + "\n",
            encoding="utf-8",
        )
        ov2.write_text(
            "\n".join(
                line for line in o2.splitlines() if not line.startswith("m02 ")
            )
            + "\n",
            encoding="utf-8",
        )
        bump.write_text(
            original.replace("m02 p2 2", "m02 pX 2"),
            encoding="utf-8",
        )
        rebuilt = _rebuild_gate()
        fold = _expected_fold()
        assert fold["m02"]["actor"] == "pX"
        bound = _home_bound(fold)
        assert "m02" not in bound  # pX→p2 != pH
        assert rebuilt["gate_digest"] == _digest_of(bound)
    finally:
        bump.write_text(original, encoding="utf-8")
        ov1.write_text(o1, encoding="utf-8")
        ov2.write_text(o2, encoding="utf-8")
        _rebuild_gate()


def test_mx_r22_cache_mix_file_injection():
    """planting cache.mix under scratch must not alter digests after recover."""
    scratch = ENV / ".scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    mix_path = scratch / "cache.mix"
    mix_path.write_text("mix:ffffffffffffeeee\n", encoding="utf-8")
    rebuilt = _rebuild_gate()
    bound = _home_bound(_expected_fold())
    assert rebuilt["gate_digest"] == _digest_of(bound)
    assert rebuilt["asset_counts"]["cache_hits"] == 0
    assert not mix_path.exists() or rebuilt["annex_note"] == "live"


def test_mx_r23_dual_rerun_stage_and_static():
    """combined stage poison + static pack must both be overwritten."""
    stage = Path("/app/output/stage/gauge.json")
    stage.parent.mkdir(parents=True, exist_ok=True)
    stage.write_text(
        json.dumps({"mode": "SETTLED", "seal_hex": "ffffffffffffffff"}) + "\n",
        encoding="utf-8",
    )
    OUT.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pack_id": "mx_pack_v1",
                "asset_counts": {
                    "nodes": 1,
                    "edges": 1,
                    "foreign_hits": 0,
                    "cache_hits": 9,
                },
                "runs": [
                    {
                        "id": "run0",
                        "n_probe": 1,
                        "n_home": 1,
                        "n_foreign": 0,
                        "seal_hex": "1111111111111111",
                    }
                ],
                "replay_digest": "0" * 16,
                "gate_digest": "0" * 16,
                "freshness": [],
                "classify": [],
                "annex_note": "static",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    rebuilt = _rebuild_gate()
    bound = _home_bound(_expected_fold())
    gate = _digest_of(bound)
    assert rebuilt["gate_digest"] == gate
    assert rebuilt["runs"][0]["seal_hex"] == _seal_hex(gate, len(bound))
    assert rebuilt["annex_note"] == "live"
    assert rebuilt["asset_counts"]["cache_hits"] == 0


def test_mx_r24_manifest_parent_order():
    """ring depends on core; JOIN must see core restatement before ring."""
    fold = _expected_fold()
    # m01 appears in core then may be touched only once; actor ends pH via overlay
    assert fold["m01"]["touch"] == 1
    assert fold["m04"]["touch"] == 1
    rebuilt = _rebuild_gate()
    bound = _home_bound(fold)
    assert rebuilt["runs"][0]["n_home"] == len(bound) >= 10


def test_mx_r25_home_set_membership():
    """exact seed home-bound membership under full filter stack."""
    bound = _home_bound(_expected_fold())
    expect = {"m01", "m02", "m03", "m04", "m05", "m06", "m07", "m08", "m11", "m12"}
    assert set(bound) == expect
    rebuilt = _rebuild_gate()
    assert rebuilt["asset_counts"]["nodes"] == 10
    assert rebuilt["replay_digest"] == _digest_of(bound)
