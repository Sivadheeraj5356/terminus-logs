"""Lab closure reference math for beta-six lattice chronicle fuse pipeline."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path


def _perl_json_num(value: float | int) -> int | float:
    """Match Perl JSON::PP encoding: whole-number floats become JSON integers."""
    num = float(value)
    if num.is_integer():
        return int(num)
    return num


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def load_jsonl_dir(batch_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for fp in sorted(batch_dir.glob("*.jsonl")):
        rows.extend(load_jsonl(fp))
    return rows


def load_trace_events(batch_dir: Path) -> list[dict]:
    rows = [r for r in load_jsonl_dir(batch_dir) if r.get("event") != "MARKER"]
    return sorted(rows, key=lambda r: (r["batch_id"], r["cycle_seq"], r["ts"]))


def window_mid(w: dict) -> float:
    return (float(w["min_c"]) + float(w["max_c"])) / 2.0


def match_polymorph(temp_c: float, windows: list[dict]) -> str | None:
    for w in windows:
        if float(w["min_c"]) <= temp_c <= float(w["max_c"]):
            return w["polymorph"]
    return None


def effective_hold(duration_s: int, shear_hz: float, shear_bonus: float) -> int:
    bonus = int(duration_s * 0.1) if shear_hz >= shear_bonus else 0
    return duration_s + bonus


def build_peak_capture(events: list[dict], windows: list[dict], shear_bonus: float) -> dict:
    batches: dict[str, list[dict]] = defaultdict(list)
    for ev in events:
        batches[ev["batch_id"]].append(ev)

    batch_rows = []
    for batch_id in sorted(batches):
        evs = batches[batch_id]
        holds = []
        for ev in evs:
            if ev.get("event") != "HOLD":
                continue
            poly = match_polymorph(float(ev["temp_c"]), windows)
            if poly is None:
                continue
            eff = effective_hold(int(ev.get("duration_s", 0)), float(ev.get("shear_hz", 0)), shear_bonus)
            holds.append({
                "polymorph": poly,
                "effective_hold_s": eff,
                "temp_c": _perl_json_num(ev["temp_c"]),
            })
        batch_rows.append({
            "batch_id": batch_id,
            "formulation_id": evs[0]["formulation_id"],
            "event_count": len(evs),
            "hold_profiles": holds,
        })

    payload = {"batches": batch_rows, "schema": "thermal-cycle-capture-v1"}
    digest = hashlib.sha256(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
    return {**payload, "capture_digest": digest}


def lattice_residuals(
    staging: dict,
    windows: list[dict],
    catalog: dict | None = None,
    adjacency_by_batch: dict[str, float] | None = None,
) -> dict:
    mids = {w["polymorph"]: window_mid(w) for w in windows}
    quench: dict[str, float] = {}
    if catalog:
        for form in catalog.get("formulations", []):
            quench[form["formulation_id"]] = float(form.get("quench_scale", 1.0))
    adj = adjacency_by_batch or {}
    residuals = []
    for batch in staging["batches"]:
        score = 0.0
        q = quench.get(batch["formulation_id"], 1.0)
        for hp in batch.get("hold_profiles", []):
            mid = mids.get(hp["polymorph"])
            if mid is None:
                continue
            score += abs(float(hp["temp_c"]) - mid) * int(hp["effective_hold_s"]) * q
        score += float(adj.get(batch["batch_id"], 0.0))
        residuals.append({
            "batch_id": batch["batch_id"],
            "residual_score": _perl_json_num(round(score, 3)),
        })
    residuals.sort(key=lambda r: r["batch_id"])
    payload = {"residuals": residuals, "schema": "lattice-residual-v1"}
    digest = hashlib.sha256(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
    return {**payload, "snapshot_digest": digest}


def build_hold_adjacency(
    staging: dict,
    gap_c: float = 1.5,
    pair_weight: float = 0.01,
) -> dict:
    """Consecutive HOLD temp-gap pairs under /app/docs/hold-adjacency-ledger.md."""
    pairs: list[dict] = []
    pair_seq = 1
    for batch in staging["batches"]:
        holds = batch.get("hold_profiles", [])
        for i in range(len(holds) - 1):
            left, right = holds[i], holds[i + 1]
            dt = abs(float(left["temp_c"]) - float(right["temp_c"]))
            if dt < gap_c:
                continue
            min_eff = min(int(left["effective_hold_s"]), int(right["effective_hold_s"]))
            contrib = float(f"{dt * pair_weight * min_eff:.6f}")
            pairs.append(
                {
                    "pair_seq": pair_seq,
                    "batch_id": batch["batch_id"],
                    "left_polymorph": left["polymorph"],
                    "right_polymorph": right["polymorph"],
                    "temp_gap_c": _perl_json_num(round(dt, 3)),
                    "adjacency_contrib": _perl_json_num(contrib),
                }
            )
            pair_seq += 1
    payload = {"schema": "hold-adjacency-ledger-v1", "pairs": pairs}
    digest = hashlib.sha256(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
    return {**payload, "adjacency_digest": digest}


def adjacency_batch_map(ledger: dict) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for p in ledger.get("pairs", []):
        out[p["batch_id"]] += float(p.get("adjacency_contrib", 0.0))
    return dict(out)


def build_cross_batch_concordance(staging: dict, residual: dict) -> dict:
    """Pairwise polymorph overlap and residual-distance closure."""
    residuals = {
        row["batch_id"]: float(row.get("residual_score", 0))
        for row in residual.get("residuals", [])
    }
    batches = sorted(staging.get("batches", []), key=lambda row: row["batch_id"])
    rows: list[dict] = []
    for i, left in enumerate(batches):
        for right in batches[i + 1 :]:
            left_holds: dict[str, int] = defaultdict(int)
            right_holds: dict[str, int] = defaultdict(int)
            for hold in left.get("hold_profiles", []):
                left_holds[hold["polymorph"]] += int(hold["effective_hold_s"])
            for hold in right.get("hold_profiles", []):
                right_holds[hold["polymorph"]] += int(hold["effective_hold_s"])
            shared = sorted(set(left_holds) & set(right_holds))
            shared_hold = sum(min(left_holds[p], right_holds[p]) for p in shared)
            gap = float(
                f"{abs(residuals.get(left['batch_id'], 0) - residuals.get(right['batch_id'], 0)):.3f}"
            )
            denominator = shared_hold + gap
            score = float(f"{shared_hold / denominator:.6f}") if denominator else 1
            rows.append(
                {
                    "left_batch_id": left["batch_id"],
                    "right_batch_id": right["batch_id"],
                    "shared_polymorphs": shared,
                    "shared_effective_hold_s": shared_hold,
                    "residual_gap": _perl_json_num(gap),
                    "concordance_score": _perl_json_num(score),
                }
            )
    payload = {"schema": "cross-batch-concordance-v1", "rows": rows}
    digest = hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return {**payload, "concordance_digest": digest}


def build_concordance_cycle_basis(staging: dict, concordance: dict) -> dict:
    batches = sorted(staging.get("batches", []), key=lambda row: row["batch_id"])
    edges = {
        f"{row['left_batch_id']}|{row['right_batch_id']}": row
        for row in concordance.get("rows", [])
    }
    rows: list[dict] = []
    for i, left in enumerate(batches):
        for j, middle in enumerate(batches[i + 1 :], start=i + 1):
            for right in batches[j + 1 :]:
                triple = [left, middle, right]
                ids = [batch["batch_id"] for batch in triple]
                totals: list[dict[str, int]] = []
                for batch in triple:
                    holds: dict[str, int] = defaultdict(int)
                    for hold in batch.get("hold_profiles", []):
                        holds[hold["polymorph"]] += int(hold["effective_hold_s"])
                    totals.append(holds)
                common = sorted(set(totals[0]) & set(totals[1]) & set(totals[2]))
                common_hold = sum(min(totals[0][p], totals[1][p], totals[2][p]) for p in common)
                pairs = [f"{ids[0]}|{ids[1]}", f"{ids[0]}|{ids[2]}", f"{ids[1]}|{ids[2]}"]
                scores = [_perl_json_num(edges[pair]["concordance_score"]) for pair in pairs]
                committed = [{"pair": pair, "score": score} for pair, score in zip(pairs, scores)]
                edge_commitment = hashlib.sha256(
                    json.dumps(committed, separators=(",", ":"), sort_keys=True).encode()
                ).hexdigest()
                mean = _perl_json_num(round(sum(float(score) for score in scores) / 3, 6))
                rows.append(
                    {
                        "batch_ids": ids,
                        "common_polymorphs": common,
                        "common_effective_hold_s": common_hold,
                        "edge_pairs": pairs,
                        "edge_scores": scores,
                        "edge_commitment": edge_commitment,
                        "cycle_mean": mean,
                    }
                )
    payload = {"schema": "concordance-cycle-basis-v1", "rows": rows}
    digest = hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return {**payload, "cycle_digest": digest}


def manifest_bind_digest(traces_path: str | Path, window_path: str | Path) -> str:
    return hashlib.sha256(f"{traces_path}|{window_path}".encode()).hexdigest()


def build_hold_spine(staging: dict) -> dict:
    """Global hold spine: batches by batch_id, holds in capture order, contiguous spine_seq."""
    rows: list[dict] = []
    seq = 1
    for batch in staging["batches"]:
        for hp in batch.get("hold_profiles", []):
            rows.append(
                {
                    "spine_seq": seq,
                    "batch_id": batch["batch_id"],
                    "polymorph": hp["polymorph"],
                    "effective_hold_s": int(hp["effective_hold_s"]),
                    "temp_c": hp["temp_c"],
                }
            )
            seq += 1
    lines = [
        f"{r['spine_seq']}|{r['batch_id']}|{r['polymorph']}|{r['effective_hold_s']}|{r['temp_c']}"
        for r in rows
    ]
    digest = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    return {"schema": "hold-spine-ledger-v1", "rows": rows, "spine_digest": digest}


def audit_commitment(epoch_before: int) -> str:
    """Fuse audit commitment for the upcoming epoch bump (fuse|before|after)."""
    epoch_after = epoch_before + 1
    return hashlib.sha256(f"fuse|{epoch_before}|{epoch_after}".encode()).hexdigest()


def ledger_triad_digest(bind_digest: str, spine_digest: str, adjacency_digest: str) -> str:
    """SHA-256 over bind|spine|adjacency ledger fingerprints."""
    return hashlib.sha256(
        f"{bind_digest}|{spine_digest}|{adjacency_digest}".encode()
    ).hexdigest()


def topology_bundle_digest(concordance_digest: str, cycle_digest: str) -> str:
    return hashlib.sha256(f"{concordance_digest}|{cycle_digest}".encode()).hexdigest()


def closure_bundle_digest(triad_digest: str, topology_digest: str) -> str:
    return hashlib.sha256(f"{triad_digest}|{topology_digest}".encode()).hexdigest()


def phase_seal(
    capture_digest: str,
    snapshot_digest: str,
    epoch: int,
    bind_digest: str,
    spine_digest: str,
    adjacency_digest: str,
    concordance_digest: str,
    cycle_digest: str,
) -> dict:
    """Twelve-field phase seal including pair and cycle topology closure."""
    commit = audit_commitment(epoch)
    triad = ledger_triad_digest(bind_digest, spine_digest, adjacency_digest)
    topology = topology_bundle_digest(concordance_digest, cycle_digest)
    bundle = closure_bundle_digest(triad, topology)
    bind = hashlib.sha256(
        f"{capture_digest}|{snapshot_digest}|{epoch}|{bind_digest}|{spine_digest}|"
        f"{adjacency_digest}|{concordance_digest}|{cycle_digest}|{commit}|{triad}|"
        f"{topology}|{bundle}".encode()
    ).hexdigest()
    return {
        "schema": "phase-stabilization-seal-v2",
        "epoch": epoch,
        "capture_digest": capture_digest,
        "snapshot_digest": snapshot_digest,
        "spine_digest": spine_digest,
        "adjacency_digest": adjacency_digest,
        "concordance_digest": concordance_digest,
        "cycle_digest": cycle_digest,
        "audit_commitment": commit,
        "ledger_triad_digest": triad,
        "topology_bundle_digest": topology,
        "closure_bundle_digest": bundle,
        "phase_seal": bind,
    }


def dominant_polymorph(hold_profiles: list[dict], windows: list[dict]) -> str:
    hold_min = {w["polymorph"]: int(w["hold_min_s"]) for w in windows}
    acc: dict[str, int] = defaultdict(int)
    for hp in hold_profiles:
        poly = hp["polymorph"]
        acc[poly] += int(hp["effective_hold_s"])
    ranked = sorted(acc.items(), key=lambda kv: (-kv[1], kv[0]))
    for poly, total in ranked:
        if total >= hold_min.get(poly, 0):
            return poly
    return ranked[0][0] if ranked else "NONE"


def build_chronicle(staging: dict, residual: dict, seal: dict, catalog: dict, windows: list[dict]) -> dict:
    form_map = {f["formulation_id"]: f for f in catalog["formulations"]}
    tracks = []
    for batch in staging["batches"]:
        fid = batch["formulation_id"]
        form = form_map[fid]
        dom = dominant_polymorph(batch.get("hold_profiles", []), windows)
        res_map = {r["batch_id"]: r["residual_score"] for r in residual["residuals"]}
        tracks.append({
            "batch_id": batch["batch_id"],
            "formulation_id": fid,
            "seed_polymorph": form["seed_polymorph"],
            "dominant_polymorph": dom,
            "residual_score": _perl_json_num(res_map.get(batch["batch_id"], 0.0)),
            "quench_scale": _perl_json_num(float(form.get("quench_scale", 1.0))),
            "transition": dom != form["seed_polymorph"],
        })
    tracks.sort(key=lambda t: t["batch_id"])
    body = {
        "schema": "beta-six-lattice-chronicle-v1",
        "epoch": seal["epoch"],
        "phase_seal": seal["phase_seal"],
        "lattice_walks": tracks,
    }
    digest = hashlib.sha256(json.dumps(body, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
    walk_digest = hashlib.sha256(
        json.dumps(tracks, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return {**body, "chronicle_digest": digest, "walk_content_digest": walk_digest}


def reference_fuse(
    formulation_registry: Path,
    temper_window: Path,
    batch_dir: Path,
    epoch: int,
    *,
    bind_traces_path: Path | None = None,
    bind_window_path: Path | None = None,
) -> tuple[dict, dict, dict, dict, dict, dict]:
    catalog = json.loads(formulation_registry.read_text(encoding="utf-8"))
    tw = json.loads(temper_window.read_text(encoding="utf-8"))
    windows = tw["windows"]
    shear_bonus = float(tw.get("shear_bonus_hz", 4.0))
    gap_c = float(tw.get("adjacency_gap_c", 1.5))
    pair_weight = float(tw.get("adjacency_pair_weight", 0.01))
    events = load_trace_events(batch_dir)
    staging = build_peak_capture(events, windows, shear_bonus)
    adjacency = build_hold_adjacency(staging, gap_c, pair_weight)
    residual = lattice_residuals(staging, windows, catalog, adjacency_batch_map(adjacency))
    concordance = build_cross_batch_concordance(staging, residual)
    cycles = build_concordance_cycle_basis(staging, concordance)
    spine = build_hold_spine(staging)
    bind_digest = manifest_bind_digest(
        bind_traces_path or batch_dir,
        bind_window_path or temper_window,
    )
    seal = phase_seal(
        staging["capture_digest"],
        residual["snapshot_digest"],
        epoch,
        bind_digest,
        spine["spine_digest"],
        adjacency["adjacency_digest"],
        concordance["concordance_digest"],
        cycles["cycle_digest"],
    )
    atlas = build_chronicle(staging, residual, seal, catalog, windows)
    return staging, residual, seal, atlas, spine, adjacency


def expected_bundled_chronicle(epoch: int = 1) -> dict:
    _, _, _, atlas, _, _ = reference_fuse(
        Path("/app/lattice-invariant-catalog/formulation-catalog.json"),
        Path("/app/conching-network/conching-window-table.json"),
        Path("/app/kiln-run-traces"),
        epoch,
    )
    return atlas
