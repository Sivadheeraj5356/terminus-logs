"""Behavioral checks for the sealed PKI timeline ledger."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/app/tools")
import digest_pack as dp  # noqa: E402

CORP = Path("/app/corp")
OUT = Path("/app/output/tl.json")
STAGE = Path("/app/output/stage")
HEX_RE = re.compile(r"^[0-9a-f]{64}$")

FIXTURE_ISSUE = {
    "j_a.db": [
        ("p_alpha", 1, 4000, "mtls:client", "svc.mesh.east"),
        ("p_beta", 1, 4010, "mtls:client", "svc.mesh.west"),
        ("p_gamma", 1, 4020, "mtls:server", "svc.mesh.core"),
        ("p_alpha", 2, 3000, "mtls:stale", "svc.mesh.east"),
        ("p_beta", 2, 3010, "mtls:stale", "svc.mesh.west"),
        ("p_gamma", 2, 3020, "mtls:stale", "svc.mesh.core"),
        ("p_alpha", 3, 2000, "mtls:client", "svc.mesh.east"),
        ("p_beta", 3, 2010, "mtls:client", "svc.mesh.west"),
        ("p_gamma", 3, 2020, "mtls:server", "svc.mesh.core"),
        ("p_alpha", 2, 9999, "mtls:client", "svc.mesh.east"),
        ("p_beta", 2, 9999, "mtls:client", "svc.mesh.west"),
        ("p_gamma", 2, 9999, "mtls:server", "svc.mesh.core"),
        ("p_alpha", 99, 50, "mtls:ghost", "svc.mesh.east"),
        ("p_beta", 99, 51, "mtls:ghost", "svc.mesh.west"),
    ],
    "j_b.db": [
        ("p_alpha", 1, 2050, "mtls:client", "svc.mesh.east"),
        ("p_beta", 1, 2051, "mtls:client", "svc.mesh.west"),
        ("p_gamma", 1, 2052, "mtls:server", "svc.mesh.core"),
        ("p_alpha", 2, 1800, "mtls:legacy", "svc.mesh.east"),
        ("p_beta", 2, 1801, "mtls:legacy", "svc.mesh.west"),
        ("p_gamma", 2, 1802, "mtls:legacy", "svc.mesh.core"),
        ("p_alpha", 2, 9100, "mtls:client", "svc.mesh.east"),
        ("p_beta", 2, 9101, "mtls:client", "svc.mesh.west"),
        ("p_gamma", 2, 9102, "mtls:server", "svc.mesh.core"),
        ("p_alpha", 3, 2150, "mtls:client", "svc.mesh.east"),
        ("p_beta", 3, 2151, "mtls:client", "svc.mesh.west"),
        ("p_gamma", 3, 2152, "mtls:server", "svc.mesh.core"),
        ("p_gamma", 99, 10, "mtls:ghost", "svc.mesh.core"),
    ],
}

FIXTURE_REVOKE = {
    "j_a.db": [
        ("p_alpha", 1, 0),
        ("p_beta", 1, 0),
        ("p_gamma", 1, 0),
        ("p_alpha", 2, 0),
        ("p_beta", 2, 0),
        ("p_gamma", 2, 0),
        ("p_alpha", 3, 0),
        ("p_beta", 3, 0),
        ("p_gamma", 3, 0),
        ("p_alpha", 99, 1),
        ("p_beta", 0, 1),
        ("p_gamma", 7, 1),
    ],
    "j_b.db": [
        ("p_alpha", 1, 0),
        ("p_beta", 1, 0),
        ("p_gamma", 1, 0),
        ("p_alpha", 2, 0),
        ("p_beta", 2, 0),
        ("p_gamma", 2, 0),
        ("p_alpha", 3, 0),
        ("p_beta", 3, 0),
        ("p_gamma", 3, 0),
        ("p_gamma", 99, 1),
        ("p_alpha", 0, 1),
    ],
}

REQUIRED_ARMS = {
    "base",
    "reorder_j",
    "drop_snap",
    "reenc_pem",
    "perm_a",
    "perm_b",
    "hostile_role",
    "alt_base",
    "alt_reorder",
    "alt_drop",
    "alt_perm",
}


def rebuild_emit(dest: Path = OUT) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    STAGE.mkdir(parents=True, exist_ok=True)
    subprocess.run(["bash", "/app/environment/tools/build_x7.sh"], check=True)
    out_path = "/app/output/tl.json" if dest == OUT else str(dest)
    subprocess.run(
        ["/app/bin/x7", "--evidence", "/app/corp", "--out", out_path],
        check=True,
    )


def load_ledger() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8"))


def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def _parse_sections(path: Path, header: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    cur: dict[str, str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s == header:
            if cur:
                rows.append(cur)
            cur = {}
            continue
        if cur is None or "=" not in s:
            continue
        left, _sep, right = s.partition("=")
        cur[left.strip()] = _unquote(right.strip())
    if cur:
        rows.append(cur)
    return rows


def arms_and_packs() -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    text = (CORP / "arms.toml").read_text(encoding="utf-8")
    arms: list[dict[str, str]] = []
    packs: dict[str, dict[str, str]] = {}
    section = ""
    cur: dict[str, str] = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s == "[[arm]]":
            if section == "arm" and cur.get("id"):
                arms.append(dict(cur))
            if section == "pack" and cur.get("id"):
                packs[cur["id"]] = dict(cur)
            cur = {}
            section = "arm"
            continue
        if s == "[[pack]]":
            if section == "arm" and cur.get("id"):
                arms.append(dict(cur))
            if section == "pack" and cur.get("id"):
                packs[cur["id"]] = dict(cur)
            cur = {}
            section = "pack"
            continue
        if "=" not in s:
            continue
        left, _sep, right = s.partition("=")
        k, v = left.strip(), _unquote(right.strip())
        cur[k] = v
    if section == "arm" and cur.get("id"):
        arms.append(dict(cur))
    if section == "pack" and cur.get("id"):
        packs[cur["id"]] = dict(cur)
    return arms, packs


def anchors() -> list[int]:
    return [int(r["gen"]) for r in _parse_sections(CORP / "anchors.toml", "[[anchor]]")]


def mats(transform: str) -> list[dict]:
    rows = _parse_sections(CORP / "mat" / "inventory_index.toml", "[[mat]]")
    out = []
    for r in rows:
        role = remap_role(r["pid"], r["role"], transform)
        out.append(
            {
                "pid": r["pid"],
                "gen": int(r["gen"]),
                "fp": r["fp"],
                "role": role,
            }
        )
    return out


def remap_role(pid: str, role: str, transform: str) -> str:
    if transform == "perm_roles_a":
        return {
            "p_alpha": "svc.mesh.west",
            "p_beta": "svc.mesh.core",
            "p_gamma": "svc.mesh.east",
        }.get(pid, role)
    if transform == "perm_roles_b":
        return {
            "p_alpha": "svc.mesh.core",
            "p_beta": "svc.mesh.east",
            "p_gamma": "svc.mesh.west",
        }.get(pid, role)
    if transform == "hostile_role_widen" and pid == "p_beta":
        return "svc.mesh.escalate"
    return role


def load_issue(db_path: Path, transform: str) -> list[dict]:
    rows = [
        {"pid": a, "gen": b, "ts": c, "scp": d, "role": e}
        for a, b, c, d, e in FIXTURE_ISSUE[db_path.name]
    ]
    if transform == "reorder_journals":
        rows = sorted(rows, key=lambda r: -r["ts"])
    elif transform == "drop_redundant_snap":
        best: dict[str, dict] = {}
        for r in rows:
            k = f"{r['pid']}:{r['gen']}"
            prev = best.get(k)
            if prev is None or r["ts"] > prev["ts"]:
                best[k] = r
        rows = list(best.values())
    return rows


def load_revoke(db_path: Path) -> dict[tuple[str, int], bool]:
    return {(a, b): bool(c) for a, b, c in FIXTURE_REVOKE[db_path.name]}


def load_hs(path: Path) -> dict[tuple[str, int], bool]:
    out: dict[tuple[str, int], bool] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        obj = json.loads(s)
        out[(obj["pid"], int(obj["gen"]))] = bool(obj["ok"])
    return out


def fold_cands(issue: list[dict], gens: list[int]) -> list[dict]:
    allowed = set(gens)
    best: dict[str, dict] = {}
    for r in issue:
        if r["gen"] not in allowed:
            continue
        k = f"{r['pid']}:{r['gen']}"
        prev = best.get(k)
        if prev is None or r["ts"] > prev["ts"]:
            best[k] = r
    out = []
    for r in best.values():
        tag = dp.tag_of(r["pid"], r["scp"], r["role"], r["gen"])
        out.append(
            {
                "pid": r["pid"],
                "gen": r["gen"],
                "scp": r["scp"],
                "role": r["role"],
                "tag": tag,
            }
        )
    return sorted(out, key=lambda x: (x["pid"], x["gen"]))


def bind_views(cands: list[dict], mat_rows: list[dict], gens: list[int]) -> list[dict]:
    allowed = set(gens)
    by = {(m["pid"], m["gen"]): m for m in mat_rows}
    out = []
    for c in cands:
        if c["gen"] not in allowed:
            continue
        m = by.get((c["pid"], c["gen"]))
        if m is None:
            continue
        tag = dp.tag_of(c["pid"], c["scp"], m["role"], c["gen"])
        out.append(
            {
                "pid": c["pid"],
                "gen": c["gen"],
                "scp": c["scp"],
                "role": m["role"],
                "fp": m["fp"],
                "tag": tag,
            }
        )
    return sorted(out, key=lambda x: (x["pid"], x["gen"]))


def sync_wins(
    views: list[dict],
    rev: dict[tuple[str, int], bool],
    hs: dict[tuple[str, int], bool],
) -> list[dict]:
    out = []
    for v in views:
        key = (v["pid"], v["gen"])
        revoked = rev.get(key, False)
        ok = hs.get(key)
        hs_fail = ok is None or not ok
        out.append(
            {
                "pid": v["pid"],
                "gen": v["gen"],
                "role": v["role"],
                "tag": v["tag"],
                "revoked": revoked,
                "hs_fail": hs_fail,
            }
        )
    return sorted(out, key=lambda x: (x["pid"], x["gen"]))


def count_viol(views: list[dict], wins: list[dict], mat_rows: list[dict]) -> int:
    expect = {(m["pid"], m["gen"]): m["role"] for m in mat_rows}
    n = 0
    for w in wins:
        if w["revoked"]:
            n += 1
        if w["hs_fail"]:
            n += 1
    for v in views:
        exp = expect.get((v["pid"], v["gen"]))
        if exp is not None and exp != v["role"]:
            n += 1
    return n


def ref_ledger() -> dict:
    arms, packs = arms_and_packs()
    gens = anchors()
    rows = []
    lanes = []
    total_viol = 0
    for arm in arms:
        pack = packs[arm["pack"]]
        transform = arm.get("transform", "none")
        db = CORP / "sql" / pack["journal"]
        issue = load_issue(db, transform)
        rev = load_revoke(db)
        hs = load_hs(CORP / "hs" / pack["hs"])
        mat_rows = mats(transform)
        cands = fold_cands(issue, gens)
        views = bind_views(cands, mat_rows, gens)
        wins = sync_wins(views, rev, hs)
        viol = count_viol(views, wins, mat_rows)
        lane = dp.hex_lane(pack["id"], arm["id"], wins)
        rows.append(
            {
                "pack_id": pack["id"],
                "arm_id": arm["id"],
                "hex_lane": lane,
                "viol_n": viol,
                "seal_ok": 1,
                "stage_mark": 1,
            }
        )
        lanes.append(lane)
        total_viol += viol
    seal = dp.seal_hex(lanes, total_viol)
    closed = 1 if all(r["viol_n"] == 0 and r["seal_ok"] == 1 for r in rows) else 0
    return {
        "schema_ver": 1,
        "rows": rows,
        "seal_hex": seal,
        "closed_ok": closed,
    }


def by_arm(led: dict) -> dict[str, dict]:
    return {r["arm_id"]: r for r in led["rows"]}


def test_k01_field_rows():
    """Ledger field layout matches schema home."""
    rebuild_emit()
    led = load_ledger()
    assert "schema_ver" in led and "rows" in led and "seal_hex" in led and "closed_ok" in led
    assert isinstance(led["rows"], list) and led["rows"]
    for row in led["rows"]:
        assert set(row) >= {"pack_id", "arm_id", "hex_lane", "viol_n", "seal_ok", "stage_mark"}
        assert isinstance(row["pack_id"], str)
        assert isinstance(row["arm_id"], str)
        assert isinstance(row["viol_n"], int)
        assert row["seal_ok"] in (0, 1)
        assert row["stage_mark"] in (0, 1)


def test_k02_hex_lane():
    """Digest hex class matches contract formulas for every arm."""
    rebuild_emit()
    led = load_ledger()
    ref = ref_ledger()
    by_ref = {(r["pack_id"], r["arm_id"]): r for r in ref["rows"]}
    for row in led["rows"]:
        assert HEX_RE.match(row["hex_lane"])
        key = (row["pack_id"], row["arm_id"])
        assert row["hex_lane"] == by_ref[key]["hex_lane"]


def test_k03_hostile_suite():
    """Hostile and metamorphic base-pack arms survive closed algebra."""
    rebuild_emit()
    led = load_ledger()
    ref = ref_ledger()
    want = {"reorder_j", "drop_snap", "reenc_pem", "hostile_role"}
    bl = by_arm(led)
    br = by_arm(ref)
    for arm in want:
        assert bl[arm]["viol_n"] == 0
        assert bl[arm]["hex_lane"] == br[arm]["hex_lane"]
    assert led["closed_ok"] == 1


def test_k04_perm_table():
    """Principal/authority window permutations remain sealed."""
    rebuild_emit()
    led = load_ledger()
    ref = ref_ledger()
    bl = by_arm(led)
    br = by_arm(ref)
    for arm in ("perm_a", "perm_b", "base"):
        assert bl[arm]["viol_n"] == 0
        assert bl[arm]["hex_lane"] == br[arm]["hex_lane"]
    assert led["seal_hex"] == ref["seal_hex"]


def test_k05_early_bypass():
    """Stage tips are ignored; sealed hex_lane is authoritative."""
    rebuild_emit()
    led = load_ledger()
    assert STAGE.exists()
    marks = list(STAGE.glob("*.mark")) + list(STAGE.glob("*.tip"))
    assert marks
    tip = STAGE / "early.tip"
    tip_bytes = tip.read_bytes() if tip.exists() else b""
    for row in led["rows"]:
        assert row["stage_mark"] == 1
        if tip_bytes:
            assert row["hex_lane"] != tip_bytes.decode("utf-8", errors="ignore").strip()
            assert len(row["hex_lane"]) == 64


def test_k06_double_emit():
    """Idempotent regenerate yields stable seal_hex."""
    rebuild_emit()
    a = load_ledger()["seal_hex"]
    rebuild_emit()
    b = load_ledger()["seal_hex"]
    assert a == b
    assert HEX_RE.match(a)


def test_k07_flip_lna():
    """Lane fold must agree with reference digests on base pack."""
    rebuild_emit()
    led = load_ledger()
    ref = ref_ledger()
    bl = by_arm(led)
    br = by_arm(ref)
    assert bl["base"]["hex_lane"] == br["base"]["hex_lane"]
    assert bl["reorder_j"]["hex_lane"] == br["reorder_j"]["hex_lane"]
    assert all(r["viol_n"] == 0 for r in led["rows"])


def test_k08_flip_fld():
    """Material bind must agree on perm arms across packs."""
    rebuild_emit()
    led = load_ledger()
    ref = ref_ledger()
    bl = by_arm(led)
    br = by_arm(ref)
    for arm in ("perm_a", "perm_b", "alt_perm"):
        assert bl[arm]["hex_lane"] == br[arm]["hex_lane"]
        assert bl[arm]["viol_n"] == 0


def test_k09_flip_snc():
    """Sync path must keep seal agreement and stage_mark."""
    rebuild_emit()
    led = load_ledger()
    ref = ref_ledger()
    assert led["seal_hex"] == ref["seal_hex"]
    assert all(r["stage_mark"] == 1 for r in led["rows"])
    assert all(r["viol_n"] == 0 for r in led["rows"])


def test_k10_noop_ops():
    """Fixed kit clears every required arm with zero violations."""
    rebuild_emit()
    led = load_ledger()
    assert led["closed_ok"] == 1
    assert all(r["viol_n"] == 0 for r in led["rows"])
    arms = {r["arm_id"] for r in led["rows"]}
    assert REQUIRED_ARMS <= arms


def test_k11_wipe_emit():
    """Wiped output regenerates through x7 to the same seal."""
    rebuild_emit()
    first = load_ledger()["seal_hex"]
    if OUT.exists():
        OUT.unlink()
    rebuild_emit()
    assert load_ledger()["seal_hex"] == first


def test_k12_cls_band():
    """Policy/digest class agrees with cq_w3 contract."""
    rebuild_emit()
    led = load_ledger()
    ref = ref_ledger()
    assert led["schema_ver"] == ref["schema_ver"]
    assert led["seal_hex"] == ref["seal_hex"]
    assert led["closed_ok"] == 1
    cq = Path("/app/docs/cq_w3.md").read_text(encoding="utf-8")
    assert "hex_lane" in cq and "seal_hex" in cq and "closed_ok" in cq


def test_k13_alt_pack():
    """Secondary journal pack arms seal to reference digests."""
    rebuild_emit()
    led = load_ledger()
    ref = ref_ledger()
    bl = by_arm(led)
    br = by_arm(ref)
    for arm in ("alt_base", "alt_reorder", "alt_drop", "alt_perm"):
        assert bl[arm]["pack_id"] == "alt"
        assert bl[arm]["viol_n"] == 0
        assert bl[arm]["hex_lane"] == br[arm]["hex_lane"]


def test_k14_metamorphic_equal():
    """Reorder and drop_snap arms clear the same closed algebra as baseline."""
    rebuild_emit()
    led = load_ledger()
    ref = ref_ledger()
    bl = by_arm(led)
    br = by_arm(ref)
    for arm in ("base", "reorder_j", "drop_snap", "alt_base", "alt_reorder", "alt_drop"):
        assert bl[arm]["viol_n"] == 0
        assert bl[arm]["hex_lane"] == br[arm]["hex_lane"]
    # Digests embed arm_id, so sibling arms must not share hex_lane strings.
    assert bl["base"]["hex_lane"] != bl["reorder_j"]["hex_lane"]
    assert bl["alt_base"]["hex_lane"] != bl["alt_drop"]["hex_lane"]


def test_k15_perm_divergence():
    """Role permutation arms must diverge from baseline hex_lane."""
    rebuild_emit()
    led = load_ledger()
    bl = by_arm(led)
    assert bl["perm_a"]["hex_lane"] != bl["base"]["hex_lane"]
    assert bl["perm_b"]["hex_lane"] != bl["base"]["hex_lane"]
    assert bl["perm_a"]["hex_lane"] != bl["perm_b"]["hex_lane"]
    assert bl["alt_perm"]["hex_lane"] != bl["alt_base"]["hex_lane"]


def test_k16_hostile_digest():
    """Hostile role widen changes hex_lane while keeping viol_n cleared."""
    rebuild_emit()
    led = load_ledger()
    ref = ref_ledger()
    bl = by_arm(led)
    br = by_arm(ref)
    assert bl["hostile_role"]["hex_lane"] != bl["base"]["hex_lane"]
    assert bl["hostile_role"]["hex_lane"] == br["hostile_role"]["hex_lane"]
    assert bl["hostile_role"]["viol_n"] == 0


def test_k17_seal_formula():
    """Top-level seal_hex matches digest_pack over arm lanes."""
    rebuild_emit()
    led = load_ledger()
    ref = ref_ledger()
    lanes = [r["hex_lane"] for r in led["rows"]]
    total = sum(r["viol_n"] for r in led["rows"])
    assert dp.seal_hex(lanes, total) == led["seal_hex"]
    assert led["seal_hex"] == ref["seal_hex"]


def test_k18_row_count():
    """Ledger emits one row per arms.toml arm in file order."""
    rebuild_emit()
    led = load_ledger()
    arms, _packs = arms_and_packs()
    assert len(led["rows"]) == len(arms)
    assert [r["arm_id"] for r in led["rows"]] == [a["id"] for a in arms]


def test_k19_zero_viol_all():
    """Every arm reports cleared violation count after repair."""
    rebuild_emit()
    led = load_ledger()
    assert all(r["viol_n"] == 0 for r in led["rows"])
    assert all(r["seal_ok"] == 1 for r in led["rows"])


def test_k20_reenc_stable():
    """PEM re-encode arm matches its reference (index remains authoritative)."""
    rebuild_emit()
    led = load_ledger()
    ref = ref_ledger()
    bl = by_arm(led)
    br = by_arm(ref)
    assert bl["reenc_pem"]["hex_lane"] == br["reenc_pem"]["hex_lane"]
    assert bl["reenc_pem"]["viol_n"] == 0
    # arm_id is part of hex_lane material, so reenc cannot equal base.
    assert bl["reenc_pem"]["hex_lane"] != bl["base"]["hex_lane"]


def test_k21_pack_isolation():
    """Base and alt packs must not share hex_lane values."""
    rebuild_emit()
    led = load_ledger()
    bl = by_arm(led)
    assert bl["base"]["hex_lane"] != bl["alt_base"]["hex_lane"]
    assert bl["perm_a"]["hex_lane"] != bl["alt_perm"]["hex_lane"]


def test_k22_stage_mark_hygiene():
    """stage_mark stays set for every sealed arm after regenerate."""
    rebuild_emit()
    led = load_ledger()
    assert all(r["stage_mark"] == 1 for r in led["rows"])
    assert led["closed_ok"] == ref_ledger()["closed_ok"]
