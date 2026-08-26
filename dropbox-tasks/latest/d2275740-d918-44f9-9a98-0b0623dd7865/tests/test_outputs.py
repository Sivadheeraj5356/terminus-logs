#!/usr/bin/env python3
"""Behavioral checks for wave feasibility certificates."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

CERT = Path("/app/output/feasibility_cert.json")
ENV = Path("/app/environment")
CAP = ENV / "pol" / "cap.toml"
FLOOR = ENV / "pol" / "q_floor.json"
M9 = ENV / "data" / "m9"
Z2 = ENV / "data" / "z2"

ROW_FIELDS = {
    "map_id",
    "wave_index",
    "spawn_hex",
    "pressure_score",
    "leftover_budget",
    "leak_margin",
}


def _run_emit() -> None:
    CERT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["/app/environment/drv/run_td.sh"], check=True, cwd="/app")


def _load_cert() -> dict:
    assert CERT.exists(), f"missing cert at {CERT}"
    return json.loads(CERT.read_text(encoding="utf-8"))


def _load_cap() -> dict:
    out: dict = {}
    for line in CAP.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        key = k.strip()
        raw = v.strip().strip('"')
        if key in {"max_cost"}:
            out[key] = int(raw)
        elif key in {"min_leftover", "max_amp"}:
            out[key] = float(raw)
        else:
            out[key] = raw
    return out


def _load_floor() -> dict:
    return json.loads(FLOOR.read_text(encoding="utf-8"))


def _child_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    out = []
    for name in sorted(os.listdir(root)):
        path = root / name
        if path.is_dir():
            out.append(path)
    return out


def _hex_to_bytes(hex_s: str) -> bytes:
    return bytes.fromhex(hex_s)


def _round(v: float, digits: int) -> float:
    return round(v + 0.0, digits)


def _fmt(v: float, digits: int) -> str:
    return f"{_round(v, digits):.{digits}f}"


def _canon_bag(bag: dict) -> dict:
    graph_in = bag.get("graph", {})
    graph = {}
    for nid in sorted(graph_in.keys()):
        cell = dict(graph_in[nid])
        if "e" in cell:
            cell["e"] = sorted(str(x) for x in cell["e"])
        graph[nid] = cell
    items = []
    for it in bag.get("items", []):
        row = dict(it)
        if "s" in row:
            row["s"] = sorted(str(x) for x in row["s"])
        items.append(row)
    items.sort(key=lambda r: int(r["i"]))
    return {"graph": graph, "items": items}


def _neighbors(graph: dict, cur: str) -> list[str]:
    nbrs: list[str] = []
    seen: set[str] = set()
    here = graph.get(cur, {})
    for x in here.get("e", []):
        s = str(x)
        if s not in seen:
            nbrs.append(s)
            seen.add(s)
    for oid, other in graph.items():
        for x in other.get("e", []):
            if str(x) == cur and oid not in seen:
                nbrs.append(oid)
                seen.add(oid)
    return nbrs


def _shortest_path(graph: dict, src: str) -> list[str] | None:
    """Classic BFS; neighbor order is presentation order (canon sorts first)."""
    if src not in graph:
        return None
    dist = {src: 0}
    prev: dict[str, str] = {}
    queue = [src]
    best_x = None
    best_d = 10**9
    while queue:
        cur = queue.pop(0)
        d = dist[cur]
        if graph[cur].get("t") == "X":
            if d < best_d:
                best_d = d
                best_x = cur
            continue
        if d >= best_d:
            continue
        for nb in _neighbors(graph, cur):
            if nb in dist:
                continue
            dist[nb] = d + 1
            prev[nb] = cur
            queue.append(nb)
    if best_x is None:
        return None
    path = [best_x]
    cur = best_x
    while cur != src:
        cur = prev.get(cur)
        if cur is None:
            return None
        path.append(cur)
    path.reverse()
    return path


def _eval_pulse(graph: dict, src: str, amp: float, cap: dict, floor: dict):
    if amp > cap["max_amp"]:
        return None
    path = _shortest_path(graph, src)
    if not path:
        return None
    residual = float(amp)
    for nid in path:
        cell = graph[nid]
        if cell.get("t") == "M":
            k = float(cell.get("k", 0.0))
            factor = float(floor["soft_floor"]) * max(0.05, 1.0 - k)
            residual *= factor
    leak = float(floor["egress_cap"]) - residual
    if not (leak > 0.0):
        return None
    return residual, leak


def _optimize_pack(bag: dict, mid: str, cap: dict, floor: dict) -> list[dict]:
    bag = _canon_bag(bag)
    graph = bag["graph"]
    pulses = []
    for it in bag["items"]:
        pulses.append(
            {
                "p_i": int(it["i"]),
                "amp": float(it["a"]),
                "cost": int(it["c"]),
                "allowed": list(it["s"]),
            }
        )
    n = len(pulses)
    budget = int(cap["max_cost"] - cap["min_leftover"])
    best = None
    for mask in range(1 << n):
        cost = 0
        ok = True
        for i in range(n):
            if (mask >> i) & 1:
                cost += pulses[i]["cost"]
                if cost > budget:
                    ok = False
                    break
        if not ok:
            continue
        chosen = []
        total = 0.0
        valid = True
        for i in range(n):
            if not ((mask >> i) & 1):
                continue
            p = pulses[i]
            pick = None
            for src in p["allowed"]:
                ev = _eval_pulse(graph, src, p["amp"], cap, floor)
                if ev is None:
                    continue
                press, leak = ev
                cand = (p["p_i"], src, press, leak)
                if pick is None or src < pick[1]:
                    pick = cand
            if pick is None:
                valid = False
                break
            chosen.append(pick)
            total += pick[2]
        if not valid:
            continue
        chosen.sort(key=lambda c: (c[0], c[1]))
        left = cap["max_cost"] - cost
        key = (total, tuple((c[0], c[1]) for c in chosen))
        if best is None or key[0] > best[0] + 1e-12 or (
            abs(key[0] - best[0]) <= 1e-12 and key[1] < best[1]
        ):
            best = (total, key[1], chosen, left)
    if best is None:
        return []
    digits = int(floor["digits"])
    rows = []
    for p_i, src, press, leak in best[2]:
        rows.append(
            {
                "map_id": mid,
                "wave_index": p_i,
                "spawn_hex": src,
                "pressure_score": _round(press, digits),
                "leftover_budget": _round(best[3], digits),
                "leak_margin": _round(leak, digits),
            }
        )
    return rows


def _expected_rows() -> list[dict]:
    cap = _load_cap()
    floor = _load_floor()
    rows: list[dict] = []
    for root in (M9, Z2):
        for d in _child_dirs(root):
            bag = json.loads((d / "bag.json").read_text(encoding="utf-8"))
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
            rows.extend(_optimize_pack(bag, str(meta["map_id"]), cap, floor))
    return rows


def _reseal(rows: list[dict], salt: bytes, digits: int) -> str:
    ordered = sorted(rows, key=lambda r: (r["map_id"], r["wave_index"], r["spawn_hex"]))
    body = "".join(
        f"{r['map_id']}|{r['wave_index']}|{r['spawn_hex']}|"
        f"{_fmt(r['pressure_score'], digits)}|{_fmt(r['leftover_budget'], digits)}|"
        f"{_fmt(r['leak_margin'], digits)}\n"
        for r in ordered
    )
    h = hashlib.sha256()
    h.update(salt)
    h.update(b"\n")
    h.update(body.encode("utf-8"))
    return h.hexdigest()


def _greedy_scores(bag: dict, mid: str, cap: dict, floor: dict) -> list[dict]:
    """Mirror LpQ2Greedy: amp-desc, no soft-floor path checks."""
    items = sorted(bag.get("items", []), key=lambda it: -float(it["a"]))
    spent = 0
    budget = cap["max_cost"] - cap["min_leftover"]
    rows = []
    for it in items:
        cost = int(it["c"])
        if spent + cost > budget:
            continue
        spent += cost
        srcs = it.get("s") or ["x"]
        rows.append(
            {
                "map_id": mid,
                "wave_index": int(it["i"]),
                "spawn_hex": str(srcs[0]),
                "pressure_score": float(it["a"]),
                "leftover_budget": float(cap["max_cost"] - spent),
                "leak_margin": float(floor["egress_cap"]),
            }
        )
    return rows


def test_wfc_a1_shape():
    """Emit must exist with typed row fields and a 64-char seal_hex."""
    _run_emit()
    cert = _load_cert()
    assert "rows" in cert and "seal_hex" in cert
    assert isinstance(cert["rows"], list) and cert["rows"]
    assert isinstance(cert["seal_hex"], str)
    assert len(cert["seal_hex"]) == 64
    for row in cert["rows"]:
        assert ROW_FIELDS <= set(row.keys())
        assert isinstance(row["map_id"], str)
        assert isinstance(row["wave_index"], int)
        assert isinstance(row["spawn_hex"], str)
        assert isinstance(row["pressure_score"], (int, float))
        assert isinstance(row["leftover_budget"], (int, float))
        assert isinstance(row["leak_margin"], (int, float))


def test_wfc_a2_digest():
    """seal_hex must equal an independent reseal of the emitted rows."""
    _run_emit()
    cert = _load_cert()
    cap = _load_cap()
    floor = _load_floor()
    salt = _hex_to_bytes(cap["salt_hex"])
    got = _reseal(cert["rows"], salt, int(floor["digits"]))
    assert got == cert["seal_hex"]


def test_wfc_b3_ord():
    """Scores and seal stay stable when bag JSON field order flips."""
    _run_emit()
    before = _load_cert()
    # Reorder bag field order for s02 (multi-path) and rerun.
    bag_path = M9 / "s02" / "bag.json"
    original = bag_path.read_text(encoding="utf-8")
    bag = json.loads(original)
    flipped = {"graph": bag["graph"], "items": list(reversed(bag["items"]))}
    g = flipped["graph"]
    flipped["graph"] = {k: g[k] for k in reversed(list(g.keys()))}
    # Flip neighbor list order on the source so non-canonical assembly diverges.
    if "a" in flipped["graph"] and "e" in flipped["graph"]["a"]:
        flipped["graph"]["a"] = dict(flipped["graph"]["a"])
        flipped["graph"]["a"]["e"] = list(reversed(list(flipped["graph"]["a"]["e"])))
    bag_path.write_text(json.dumps(flipped, separators=(",", ":")), encoding="utf-8")
    try:
        _run_emit()
        after = _load_cert()
    finally:
        bag_path.write_text(original, encoding="utf-8")
    def scores(cert: dict) -> list[tuple]:
        return sorted(
            (
                r["map_id"],
                r["wave_index"],
                r["spawn_hex"],
                r["pressure_score"],
                r["leftover_budget"],
                r["leak_margin"],
            )
            for r in cert["rows"]
        )
    assert scores(before) == scores(after)
    assert before["seal_hex"] == after["seal_hex"]


def test_wfc_b4_lim():
    """leftover_budget and maximizing pressure must honor hard limits."""
    _run_emit()
    cert = _load_cert()
    cap = _load_cap()
    by_map: dict[str, list[dict]] = {}
    for row in cert["rows"]:
        mid = row["map_id"]
        if mid not in by_map:
            by_map[mid] = []
        by_map[mid].append(row)
    for mid, rows in by_map.items():
        left = rows[0]["leftover_budget"]
        assert left >= cap["min_leftover"]
        for r in rows:
            assert r["leftover_budget"] == left
        expected = {r["wave_index"]: r for r in _expected_rows() if r["map_id"] == mid}
        assert set(expected) == {r["wave_index"] for r in rows}
        for r in rows:
            assert r["pressure_score"] == expected[r["wave_index"]]["pressure_score"]
            assert r["leftover_budget"] == expected[r["wave_index"]]["leftover_budget"]


def test_wfc_c5_path():
    """Stress packs must keep positive leak_margin (no egress breach)."""
    _run_emit()
    cert = _load_cert()
    z_ids = {d.name for d in _child_dirs(Z2)}
    # map_id for z2 packs equals folder meta map_id (t01/t02)
    stress_rows = [r for r in cert["rows"] if r["map_id"] in {"t01", "t02"} or any(
        (Z2 / z / "meta.json").exists()
        and json.loads((Z2 / z / "meta.json").read_text(encoding="utf-8")).get("map_id") == r["map_id"]
        for z in z_ids
    )]
    assert stress_rows, "expected stress pack rows in emit"
    for r in stress_rows:
        assert r["leak_margin"] > 0.0


def test_wfc_c6_twice():
    """Seeded double emit must keep an identical seal_hex."""
    _run_emit()
    a = _load_cert()["seal_hex"]
    _run_emit()
    b = _load_cert()["seal_hex"]
    assert a == b


def test_wfc_d7_ow():
    """A second emit must overwrite the cert file cleanly."""
    _run_emit()
    first = _load_cert()
    # Mutate output then overwrite via fresh emit.
    CERT.write_text(json.dumps({"rows": [], "seal_hex": "0" * 64}), encoding="utf-8")
    _run_emit()
    second = _load_cert()
    assert second["rows"]
    assert second["seal_hex"] == first["seal_hex"]
    assert len(second["rows"]) == len(first["rows"])


def test_wfc_d8_arm():
    """Search path required; decoy greedy-only scores must not match emit."""
    _run_emit()
    cert = _load_cert()
    cap = _load_cap()
    floor = _load_floor()
    # Authoritative expected scores must beat decoy-greedy amplitude path.
    expected = _expected_rows()
    got = {
        (r["map_id"], r["wave_index"], r["spawn_hex"]): r["pressure_score"]
        for r in cert["rows"]
    }
    exp = {
        (r["map_id"], r["wave_index"], r["spawn_hex"]): r["pressure_score"]
        for r in expected
    }
    assert got == exp
    # Greedy decoy differs on at least one pack.
    found_diff = False
    for root in (M9, Z2):
        for d in _child_dirs(root):
            bag = json.loads((d / "bag.json").read_text(encoding="utf-8"))
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
            mid = str(meta["map_id"])
            greedy = _greedy_scores(bag, mid, cap, floor)
            gset = {
                (r["map_id"], r["wave_index"], r["spawn_hex"], r["pressure_score"])
                for r in greedy
            }
            cset = {
                (r["map_id"], r["wave_index"], r["spawn_hex"], r["pressure_score"])
                for r in cert["rows"]
                if r["map_id"] == mid
            }
            if gset != cset:
                found_diff = True
                break
        if found_diff:
            break
    assert found_diff
