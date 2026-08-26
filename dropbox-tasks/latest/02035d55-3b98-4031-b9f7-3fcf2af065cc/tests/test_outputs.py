"""Behavioral verifier for orchard crate pick balance reports."""

import json
import os
import subprocess
import tempfile
from pathlib import Path


def _app_root() -> Path:
    root = os.getenv("ORCHARD_APP_ROOT") or os.getenv("TB_APP_ROOT")
    if not root:
        raise RuntimeError("ORCHARD_APP_ROOT or TB_APP_ROOT must be set")
    return Path(root)


APP = _app_root()
CAP = 12000
MARK_CADENCE = 4
SCHEMA_GENERATION = 3
BIN = APP / "bin" / "pick-balance"
FIXTURE = APP / "data" / "feed.jsonl"
OUT = Path("/app/output/pick_report.json")
ZONE_FIELDS = frozenset(
    {
        "zone",
        "grade_prime",
        "grade_standard",
        "grade_cull",
        "net_kept_g",
        "net_refused",
        "pick_marks",
    }
)
TOP_FIELDS = frozenset({"balance_stamp", "checkpoint_used", "zones"})
ZONE_STATE_FIELDS = frozenset(
    {
        "grade_prime",
        "grade_standard",
        "grade_cull",
        "net_kept_g",
        "net_refused",
        "pick_marks",
        "kept_rows",
    }
)
CHECKPOINT_TOP_FIELDS = frozenset(
    {
        "input_identity",
        "schema_generation",
        "last_event_position",
        "previous_stamp_seed",
        "tare_lineage",
        "zone_order",
        "zone_states",
        "supersede_winners",
        "spoilage_winners",
    }
)
_U64_MAX = (1 << 64) - 1
_I64_MAX = (1 << 63) - 1


def _u64_add(a: int, b: int) -> int | None:
    total = a + b
    if total < 0 or total > _U64_MAX:
        return None
    return total


def _capacity_refused(kept: int, incoming: int) -> bool:
    total = _u64_add(kept, incoming)
    if total is None:
        return True
    return total > CAP


def _file_sha256(path: Path) -> str:
    proc = subprocess.run(
        ["openssl", "dgst", "-sha256", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip().split()[-1]


def _sha_hex(payload: str) -> str:
    proc = subprocess.run(
        ["openssl", "dgst", "-sha256"],
        input=payload,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip().split()[-1]


def _grade_slot(value: int) -> int:
    if value < 200:
        return 0
    if 200 <= value <= 850:
        return 1
    return 2


def _downgrade_slot(slot: int) -> int:
    return min(slot + 1, 2)


def _effective_net(raw: int, offset: int) -> int | None:
    gross = int(raw)
    if gross > _I64_MAX:
        return None
    total = gross + int(offset)
    if total < 0 or total > _U64_MAX:
        return None
    return total


def _resolve_offset(profile_id: str, sequence: int, tares: list[dict]) -> int:
    best_gen: int | None = None
    best_idx: int | None = None
    best_offset = 0
    for idx, rec in enumerate(tares):
        if str(rec["tare_profile_id"]) != profile_id:
            continue
        if rec["status"] != "active":
            continue
        if not (int(rec["start_seq"]) <= sequence < int(rec["end_seq"])):
            continue
        gen = int(rec["generation"])
        if best_gen is None or gen > best_gen or (gen == best_gen and idx < best_idx):
            best_gen = gen
            best_idx = idx
            best_offset = int(rec["offset_g"])
    return best_offset


def _tare_lineage(tares: list[dict]) -> str:
    by_id: dict[str, dict] = {}
    for tare in tares:
        profile_id = str(tare["tare_profile_id"])
        prev = by_id.get(profile_id)
        if prev is None or int(tare["generation"]) > int(prev["generation"]):
            by_id[profile_id] = tare
    parts: list[str] = []
    for profile_id in sorted(by_id):
        winner = by_id[profile_id]
        parts.append(
            f"{winner['tare_profile_id']}|{winner['generation']}|{winner['zone']}|"
            f"{winner['start_seq']}|{winner['end_seq']}|{winner['offset_g']}|{winner['status']}"
        )
    return ";".join(parts)


def _split_feed(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    picks: list[dict] = []
    tares: list[dict] = []
    supersedes: list[dict] = []
    spoilages: list[dict] = []
    for row in rows:
        kind = row.get("kind")
        if kind == "pick":
            picks.append(row)
        elif kind == "tare":
            tares.append(row)
        elif kind == "supersede":
            supersedes.append(row)
        elif kind == "spoilage":
            spoilages.append(row)
    return picks, tares, supersedes, spoilages


def _baseline_kept(picks: list[dict], tares: list[dict]) -> set[str]:
    kept: set[str] = set()
    zones: dict[str, int] = {}
    ordered = sorted(picks, key=lambda r: (int(r["sequence"]),))
    for row in ordered:
        offset = _resolve_offset(str(row["tare_profile_id"]), int(row["sequence"]), tares)
        net = _effective_net(int(row["gross_g"]), offset)
        if net is None:
            continue
        zone_kept = zones.setdefault(str(row["zone"]), 0)
        if _capacity_refused(zone_kept, net):
            continue
        new_kept = _u64_add(zone_kept, net)
        if new_kept is None:
            continue
        zones[str(row["zone"])] = new_kept
        kept.add(str(row["pick_id"]))
    return kept


def _supersede_winners(supersedes: list[dict], baseline_kept: set[str]) -> dict[str, dict]:
    winners: dict[str, dict] = {}
    for sup in supersedes:
        target = str(sup["target_pick_id"])
        if target not in baseline_kept:
            continue
        prev = winners.get(target)
        if prev is None or int(sup["generation"]) > int(prev["generation"]):
            winners[target] = {
                "generation": int(sup["generation"]),
                "action": str(sup["action"]),
                "gross_g": int(sup.get("gross_g", 0)),
            }
    return winners


def _spoilage_winners(spoilages: list[dict], baseline_kept: set[str]) -> dict[str, dict]:
    winners: dict[str, dict] = {}
    for row in spoilages:
        target = str(row["target_pick_id"])
        if target not in baseline_kept:
            continue
        prev = winners.get(target)
        if prev is None or int(row["generation"]) > int(prev["generation"]):
            winners[target] = {"generation": int(row["generation"])}
    return winners


def _supersede_row_matches_winner(sup: dict, winner: dict) -> bool:
    if int(sup["generation"]) != winner["generation"]:
        return False
    if str(sup["action"]) != winner["action"]:
        return False
    return winner["action"] != "replace" or int(sup.get("gross_g", 0)) == winner["gross_g"]


def _supersede_lineage(supersedes: list[dict], winners: dict[str, dict]) -> str:
    parts: list[str] = []
    emitted: set[str] = set()
    for sup in supersedes:
        target = str(sup["target_pick_id"])
        if target in emitted:
            continue
        winner = winners.get(target)
        if winner is None or not _supersede_row_matches_winner(sup, winner):
            continue
        emitted.add(target)
        value = "VOID" if winner["action"] == "void" else str(winner["gross_g"])
        parts.append(f"{target}|{sup['generation']}|{sup['action']}|{value}")
    return ";".join(parts)


def _spoilage_lineage(spoilages: list[dict], winners: dict[str, dict]) -> str:
    parts: list[str] = []
    emitted: set[str] = set()
    for row in spoilages:
        target = str(row["target_pick_id"])
        if target in emitted:
            continue
        winner = winners.get(target)
        if winner is None or winner["generation"] != int(row["generation"]):
            continue
        emitted.add(target)
        parts.append(f"{target}|{row['generation']}")
    return ";".join(parts)


def _zone_order(picks: list[dict]) -> list[str]:
    order: list[str] = []
    seen: set[str] = set()
    for row in sorted(picks, key=lambda r: (int(r["sequence"]),)):
        label = str(row["zone"])
        if label not in seen:
            seen.add(label)
            order.append(label)
    return order


def _last_event_position(rows: list[dict]) -> int:
    return max(0, len(rows) - 1)


def _reference_report(rows: list[dict]) -> dict:
    picks, tares, supersedes, spoilages = _split_feed(rows)
    tare_lin = _tare_lineage(tares)
    baseline = _baseline_kept(picks, tares)
    supersede_w = _supersede_winners(supersedes, baseline)
    spoilage_w = _spoilage_winners(spoilages, baseline)
    supersede_lin = _supersede_lineage(supersedes, supersede_w)
    spoilage_lin = _spoilage_lineage(spoilages, spoilage_w)

    order = _zone_order(picks)
    lanes: dict[str, list[object]] = {}
    for label in order:
        lanes[label] = [0, 0, 0, 0, 0, 0, []]

    ordered = sorted(picks, key=lambda r: (int(r["sequence"]),))
    for row in ordered:
        pid = str(row["pick_id"])
        label = str(row["zone"])
        lane = lanes[label]
        winner = supersede_w.get(pid)
        if winner and winner["action"] == "void":
            continue
        gross = int(row["gross_g"])
        if winner and winner["action"] == "replace":
            gross = winner["gross_g"]
        offset = _resolve_offset(str(row["tare_profile_id"]), int(row["sequence"]), tares)
        net = _effective_net(gross, offset)
        if net is None:
            lane[5] = int(lane[5]) + 1
            continue
        kept = int(lane[3])
        if _capacity_refused(kept, net):
            lane[5] = int(lane[5]) + 1
            continue
        new_kept = _u64_add(kept, net)
        if new_kept is None:
            lane[5] = int(lane[5]) + 1
            continue
        slot = _grade_slot(net)
        if pid in spoilage_w:
            slot = _downgrade_slot(slot)
        lane[slot] = int(lane[slot]) + 1
        lane[3] = new_kept
        accepted = int(lane[4]) + 1
        lane[4] = accepted
        marks: list[str] = lane[6]  # type: ignore[assignment]
        if accepted % MARK_CADENCE == 0:
            marks.append(_sha_hex(f"{label}|{lane[3]}|{len(marks) + 1}"))

    records = []
    stamp_parts: list[str] = []
    for label in order:
        lane = lanes[label]
        marks = list(lane[6])  # type: ignore[arg-type]
        records.append(
            {
                "zone": label,
                "grade_prime": lane[0],
                "grade_standard": lane[1],
                "grade_cull": lane[2],
                "net_kept_g": lane[3],
                "net_refused": lane[5],
                "pick_marks": marks,
            }
        )
        stamp_parts.extend(marks)

    payload = ";".join(stamp_parts)
    if tare_lin:
        payload = f"{payload};{tare_lin}" if payload else tare_lin
    if supersede_lin:
        payload = f"{payload};{supersede_lin}" if payload else supersede_lin
    if spoilage_lin:
        payload = f"{payload};{spoilage_lin}" if payload else spoilage_lin
    return {
        "zones": records,
        "balance_stamp": _sha_hex(payload),
        "checkpoint_used": False,
    }


def _load_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_feed(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n",
        encoding="utf-8",
    )


def _scratch_path(root: Path, stem: str, suffix: str = "json") -> Path:
    return root / f"{stem}.{suffix}"


def _rebuild_and_run(
    input_path: Path | None = None,
    out: Path | None = None,
    checkpoint_in: Path | None = None,
    checkpoint_out: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    build = subprocess.run(
        ["make", "-C", str(APP), f"APP_ROOT={APP}", "all"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr or build.stdout
    target = out or OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            str(BIN),
            "--input",
            str(input_path or FIXTURE),
            "--out",
            str(target),
            *(
                ["--checkpoint-in", str(checkpoint_in)]
                if checkpoint_in is not None
                else []
            ),
            *(
                ["--checkpoint-out", str(checkpoint_out)]
                if checkpoint_out is not None
                else []
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _run_scenario_bytes(rows: list[dict], **kwargs) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        inp = _scratch_path(Path(tmp), "feed", "jsonl")
        outp = _scratch_path(Path(tmp), "report")
        _write_feed(inp, rows)
        proc = _rebuild_and_run(inp, outp, **kwargs)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        return outp.read_bytes()


def _run_scenario(rows: list[dict], **kwargs) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        inp = _scratch_path(Path(tmp), "feed", "jsonl")
        outp = _scratch_path(Path(tmp), "report")
        _write_feed(inp, rows)
        proc = _rebuild_and_run(inp, outp, **kwargs)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        return json.loads(outp.read_text(encoding="utf-8"))


def test_driver_rebuilds_and_emits_report(tmp_path: Path) -> None:
    """Release build must run and write the balance JSON artifact."""
    out = tmp_path / "pick_report.json"
    proc = _rebuild_and_run(out=out)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert out.is_file(), "driver did not create balance output"


def test_report_top_level_schema(tmp_path: Path) -> None:
    """Emitted report must expose the documented top-level fields."""
    out = tmp_path / "pick_report.json"
    _rebuild_and_run(out=out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert set(payload) == TOP_FIELDS
    assert isinstance(payload["zones"], list)
    assert isinstance(payload["balance_stamp"], str)
    assert isinstance(payload["checkpoint_used"], bool)
    assert len(payload["balance_stamp"]) == 64


def test_records_match_reference_fixture(tmp_path: Path) -> None:
    """Bundled fixture balance must match the independent reference model."""
    out = tmp_path / "pick_report.json"
    _rebuild_and_run(out=out)
    observed = json.loads(out.read_text(encoding="utf-8"))
    expected = _reference_report(_load_rows(FIXTURE))
    assert observed == expected


def test_zone_field_shapes(tmp_path: Path) -> None:
    """Each zone object must carry the documented per-zone fields."""
    out = tmp_path / "pick_report.json"
    _rebuild_and_run(out=out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    for zone in payload["zones"]:
        assert set(zone) == ZONE_FIELDS
        assert isinstance(zone["pick_marks"], list)
        for mark in zone["pick_marks"]:
            assert len(mark) == 64


def test_zone_order_is_first_seen(tmp_path: Path) -> None:
    """Zones must remain in first-seen order from pick rows."""
    out = tmp_path / "pick_report.json"
    _rebuild_and_run(out=out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    picks, _, _, _ = _split_feed(_load_rows(FIXTURE))
    assert [z["zone"] for z in payload["zones"]] == _zone_order(picks)


def test_case_sensitive_zone_labels(tmp_path: Path) -> None:
    """Zone labels must preserve input casing."""
    out = tmp_path / "pick_report.json"
    _rebuild_and_run(out=out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    labels = {z["zone"] for z in payload["zones"]}
    picks, _, _, _ = _split_feed(_load_rows(FIXTURE))
    fixture_labels = {str(row["zone"]) for row in picks}
    assert labels == fixture_labels


def test_standard_grade_includes_boundary_values(tmp_path: Path) -> None:
    """Boundary net values must count in the standard grade on the bundled fixture."""
    out = tmp_path / "pick_report.json"
    _rebuild_and_run(out=out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    expected = _reference_report(_load_rows(FIXTURE))
    for obs, exp in zip(payload["zones"], expected["zones"], strict=True):
        assert obs["grade_standard"] == exp["grade_standard"]


def test_capacity_refusals_do_not_mutate_kept_totals(tmp_path: Path) -> None:
    """Refused rows must not add kept totals or grade counts for that zone."""
    out = tmp_path / "pick_report.json"
    _rebuild_and_run(out=out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    expected = _reference_report(_load_rows(FIXTURE))
    for obs, exp in zip(payload["zones"], expected["zones"], strict=True):
        assert obs["net_refused"] == exp["net_refused"]
        assert obs["net_kept_g"] == exp["net_kept_g"]


def test_marks_fire_on_cadence(tmp_path: Path) -> None:
    """Pick marks must appear on every Nth kept row per zone."""
    out = tmp_path / "pick_report.json"
    _rebuild_and_run(out=out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    expected = _reference_report(_load_rows(FIXTURE))
    for obs, exp in zip(payload["zones"], expected["zones"], strict=True):
        assert obs["pick_marks"] == exp["pick_marks"]


def test_balance_stamp_chains_zone_marks(tmp_path: Path) -> None:
    """Balance stamp must hash pick marks plus lineage segments."""
    out = tmp_path / "pick_report.json"
    _rebuild_and_run(out=out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    expected = _reference_report(_load_rows(FIXTURE))
    assert payload["balance_stamp"] == expected["balance_stamp"]


def test_hand_written_output_rejected_by_rebuild(tmp_path: Path) -> None:
    """Static JSON edits must be overwritten by a rebuilt driver run."""
    out = tmp_path / "pick_report.json"
    _rebuild_and_run(out=out)
    tampered = {"zones": [], "balance_stamp": "0" * 64}
    out.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
    proc = subprocess.run(
        [str(BIN), "--input", str(FIXTURE), "--out", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload != tampered
    assert payload == _reference_report(_load_rows(FIXTURE))


def _tare(
    profile_id: str,
    zone: str,
    gen: int,
    start: int,
    end: int,
    offset: int,
    status: str = "active",
) -> dict:
    return {
        "kind": "tare",
        "tare_profile_id": profile_id,
        "zone": zone,
        "generation": gen,
        "start_seq": start,
        "end_seq": end,
        "offset_g": offset,
        "status": status,
    }


def _pick(pid: str, zone: str, seq: int, gross: int, profile_id: str) -> dict:
    return {
        "kind": "pick",
        "pick_id": pid,
        "zone": zone,
        "sequence": seq,
        "gross_g": gross,
        "tare_profile_id": profile_id,
    }


def _supersede(target: str, gen: int, action: str, gross: int = 0) -> dict:
    row: dict = {
        "kind": "supersede",
        "target_pick_id": target,
        "generation": gen,
        "action": action,
    }
    if action == "replace":
        row["gross_g"] = gross
    return row


def _spoilage(target: str, gen: int) -> dict:
    return {"kind": "spoilage", "target_pick_id": target, "generation": gen}


def test_overlapping_tare_generations() -> None:
    """Highest numeric generation must win for the same tare_profile_id."""
    rows = [
        _tare("t1", "Z1", 2, 1, 10, 50),
        _tare("t1", "Z1", 10, 1, 10, -30),
        _pick("p1", "Z1", 5, 100, "t1"),
    ]
    assert _reference_report(rows)["zones"][0]["net_kept_g"] == 70
    assert _run_scenario(rows) == _reference_report(rows)


def test_boundary_at_end_seq() -> None:
    """Sequence equal to end_seq must not receive the tare offset."""
    rows = [
        _tare("t1", "Z1", 1, 1, 5, 100),
        _pick("p1", "Z1", 5, 200, "t1"),
    ]
    assert _reference_report(rows)["zones"][0]["grade_standard"] == 1
    assert _run_scenario(rows) == _reference_report(rows)


def test_revoked_newest_tare_falls_back() -> None:
    """Revoking the newest generation must fall back to the older active record."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, 10),
        _tare("t1", "Z1", 2, 1, 20, 100, status="revoked"),
        _pick("p1", "Z1", 3, 50, "t1"),
    ]
    assert _reference_report(rows)["zones"][0]["net_kept_g"] == 60
    assert _run_scenario(rows) == _reference_report(rows)


def test_negative_tare_offset_refusal() -> None:
    """Negative effective net from tare must count as a refusal."""
    rows = [
        _tare("t1", "Z1", 1, 1, 10, -200),
        _pick("p1", "Z1", 2, 100, "t1"),
    ]
    zone = _reference_report(rows)["zones"][0]
    assert zone["net_refused"] == 1
    assert zone["net_kept_g"] == 0
    assert _run_scenario(rows) == _reference_report(rows)


def test_spoilage_downgrades_grade_bucket() -> None:
    """Spoilage must demote prime to standard without changing net totals."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 150, "t1"),
        _spoilage("p1", 1),
    ]
    expected = _reference_report(rows)
    assert expected["zones"][0]["grade_prime"] == 0
    assert expected["zones"][0]["grade_standard"] == 1
    assert _run_scenario(rows) == expected


def test_voided_row_does_not_advance_mark_cadence() -> None:
    """Void supersedes must not consume pick-mark cadence positions."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 100, "t1"),
        _pick("p2", "Z1", 2, 100, "t1"),
        _pick("p3", "Z1", 3, 100, "t1"),
        _pick("p4", "Z1", 4, 100, "t1"),
        _pick("p5", "Z1", 5, 100, "t1"),
        _supersede("p2", 1, "void"),
    ]
    expected = _reference_report(rows)
    assert len(expected["zones"][0]["pick_marks"]) == 1
    assert _run_scenario(rows) == expected


def test_case_colliding_zone_labels() -> None:
    """Mixed-case zone labels must remain distinct zones."""
    rows = [
        _tare("ta", "Row-1", 1, 1, 20, 0),
        _tare("tb", "row-1", 1, 1, 20, 0),
        _pick("p1", "Row-1", 1, 100, "ta"),
        _pick("p2", "row-1", 2, 100, "tb"),
    ]
    expected = _reference_report(rows)
    labels = [z["zone"] for z in expected["zones"]]
    assert labels == ["Row-1", "row-1"]
    assert _run_scenario(rows) == expected


def test_valid_checkpoint_replay_matches_cold() -> None:
    """Checkpoint resume must match a full cold replay at the byte level."""
    rows = [
        _tare("t1", "Z1", 1, 1, 50, 0),
        _pick("p1", "Z1", 1, 100, "t1"),
        _pick("p2", "Z1", 2, 200, "t1"),
        _pick("p3", "Z1", 3, 300, "t1"),
        _spoilage("p2", 1),
        _supersede("p3", 2, "replace", 400),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        inp = _scratch_path(Path(tmp), "feed", "jsonl")
        cold_out = _scratch_path(Path(tmp), "cold")
        ckpt = _scratch_path(Path(tmp), "ckpt")
        warm_out = _scratch_path(Path(tmp), "warm")
        _write_feed(inp, rows)
        proc = _rebuild_and_run(inp, cold_out, checkpoint_out=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        assert ckpt.is_file(), "--checkpoint-out did not write checkpoint state"
        proc = _rebuild_and_run(inp, warm_out, checkpoint_in=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        cold = json.loads(cold_out.read_text(encoding="utf-8"))
        warm = json.loads(warm_out.read_text(encoding="utf-8"))
        assert cold["checkpoint_used"] is False
        assert warm["checkpoint_used"] is True
        assert warm["zones"] == cold["zones"] == _reference_report(rows)["zones"]
        assert warm["balance_stamp"] == cold["balance_stamp"]
        assert warm["balance_stamp"] == _reference_report(rows)["balance_stamp"]


def test_checkpoint_out_writes_required_fields() -> None:
    """--checkpoint-out must persist contract checkpoint fields for the input."""
    rows = [
        _tare("t1", "Z1", 1, 1, 50, 0),
        _pick("p1", "Z1", 1, 100, "t1"),
        _pick("p2", "Z1", 2, 200, "t1"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        inp = _scratch_path(Path(tmp), "feed", "jsonl")
        ckpt = _scratch_path(Path(tmp), "ckpt")
        _write_feed(inp, rows)
        proc = _rebuild_and_run(inp, checkpoint_out=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        payload = json.loads(ckpt.read_text(encoding="utf-8"))
        for key in (
            "input_identity",
            "schema_generation",
            "last_event_position",
            "previous_stamp_seed",
            "tare_lineage",
            "zone_order",
            "zone_states",
            "supersede_winners",
            "spoilage_winners",
        ):
            assert key in payload, f"checkpoint missing {key}"
        assert payload["schema_generation"] == SCHEMA_GENERATION
        assert payload["input_identity"] == _file_sha256(inp)
        assert payload["last_event_position"] == _last_event_position(rows)
        expected = _reference_report(rows)
        assert payload["previous_stamp_seed"] == expected["balance_stamp"]
        assert len(payload["previous_stamp_seed"]) == 64
        _, tares, _, _ = _split_feed(rows)
        assert payload["tare_lineage"] == _tare_lineage(tares)
        picks, _, _, _ = _split_feed(rows)
        assert payload["zone_order"] == _zone_order(picks)
        for zone in payload["zone_order"]:
            assert set(payload["zone_states"][zone]) == ZONE_STATE_FIELDS
        _assert_checkpoint_kept_rows_exact(rows, payload)


def test_checkpoint_rejects_extra_zone_state_field_keys() -> None:
    """Extra keys inside zone_states entries must force cold replay."""
    rows = _checkpoint_base_rows()
    expected = _reference_report(rows)

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        zone = payload["zone_order"][0]
        payload["zone_states"][zone]["tampered"] = 1

    assert _assert_cold_fallback_report(_run_with_tampered_checkpoint(rows, mutate), expected) is None


def test_checkpoint_rejects_missing_zone_state_field_keys() -> None:
    """Missing required zone_states fields must force cold replay."""
    rows = _checkpoint_base_rows()
    expected = _reference_report(rows)

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        zone = payload["zone_order"][0]
        payload["zone_states"][zone].pop("kept_rows", None)

    assert _assert_cold_fallback_report(_run_with_tampered_checkpoint(rows, mutate), expected) is None


def test_checkpoint_rejects_extra_zone_keys_in_zone_states() -> None:
    """zone_states keys outside zone_order must force cold replay."""
    rows = _checkpoint_base_rows()
    expected = _reference_report(rows)

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        payload["zone_states"]["orphan-zone"] = payload["zone_states"][
            payload["zone_order"][0]
        ].copy()

    assert _assert_cold_fallback_report(_run_with_tampered_checkpoint(rows, mutate), expected) is None


def test_checkpoint_rejects_missing_zone_in_zone_states() -> None:
    """Every zone_order label must have a matching zone_states entry."""
    rows = _checkpoint_base_rows()
    expected = _reference_report(rows)

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        zone = payload["zone_order"][0]
        payload["zone_states"].pop(zone, None)

    assert _assert_cold_fallback_report(_run_with_tampered_checkpoint(rows, mutate), expected) is None


def test_checkpoint_rejects_wrong_type_in_zone_states() -> None:
    """Non-integer zone_states fields must force cold replay."""
    rows = _checkpoint_base_rows()
    expected = _reference_report(rows)

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        zone = payload["zone_order"][0]
        payload["zone_states"][zone]["net_kept_g"] = "not-an-integer"

    with tempfile.TemporaryDirectory() as tmp:
        inp = _scratch_path(Path(tmp), "feed", "jsonl")
        warm_out = _scratch_path(Path(tmp), "warm")
        ckpt = _scratch_path(Path(tmp), "ckpt")
        _write_feed(inp, rows)
        proc = _rebuild_and_run(inp, checkpoint_out=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        payload = json.loads(ckpt.read_text(encoding="utf-8"))
        mutate(payload, inp, rows)
        ckpt.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        proc = _rebuild_and_run(inp, warm_out, checkpoint_in=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        warm = json.loads(warm_out.read_text(encoding="utf-8"))
        _assert_cold_fallback_report(warm, expected)


def test_warm_resume_from_valid_prefix_checkpoint() -> None:
    """Warm resume on a prefix-only feed must match cold replay on that prefix."""
    prefix = [
        _tare("t1", "Z1", 1, 1, 50, 0),
        _pick("p1", "Z1", 1, 100, "t1"),
        _pick("p2", "Z1", 2, 200, "t1"),
    ]
    expected = _reference_report(prefix)
    with tempfile.TemporaryDirectory() as tmp:
        inp = _scratch_path(Path(tmp), "feed", "jsonl")
        cold_out = _scratch_path(Path(tmp), "cold")
        ckpt = _scratch_path(Path(tmp), "ckpt")
        warm_out = _scratch_path(Path(tmp), "warm")
        _write_feed(inp, prefix)
        proc = _rebuild_and_run(inp, cold_out, checkpoint_out=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        assert ckpt.is_file(), "--checkpoint-out did not write checkpoint state"
        payload = json.loads(ckpt.read_text(encoding="utf-8"))
        assert payload["last_event_position"] == _last_event_position(prefix)
        assert payload["input_identity"] == _file_sha256(inp)
        assert payload["schema_generation"] == SCHEMA_GENERATION
        assert payload["previous_stamp_seed"] == expected["balance_stamp"]
        _, tares, _, _ = _split_feed(prefix)
        picks, _, _, _ = _split_feed(prefix)
        assert payload["tare_lineage"] == _tare_lineage(tares)
        assert payload["zone_order"] == _zone_order(picks)
        for zone in payload["zone_order"]:
            state = payload["zone_states"][zone]
            assert set(state) == ZONE_STATE_FIELDS
            ref_zone = next(z for z in expected["zones"] if z["zone"] == zone)
            assert state["grade_prime"] == ref_zone["grade_prime"]
            assert state["grade_standard"] == ref_zone["grade_standard"]
            assert state["grade_cull"] == ref_zone["grade_cull"]
            assert state["net_kept_g"] == ref_zone["net_kept_g"]
            assert state["net_refused"] == ref_zone["net_refused"]
            assert state["pick_marks"] == ref_zone["pick_marks"]
            assert state["kept_rows"] == _reference_kept_rows(prefix, zone)
        proc = _rebuild_and_run(inp, warm_out, checkpoint_in=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        warm = json.loads(warm_out.read_text(encoding="utf-8"))
        cold = json.loads(cold_out.read_text(encoding="utf-8"))
        assert warm["checkpoint_used"] is True
        assert cold["checkpoint_used"] is False
        assert warm["zones"] == cold["zones"] == expected["zones"]
        assert warm["balance_stamp"] == cold["balance_stamp"] == expected["balance_stamp"]


def test_suffix_continuation_requires_checkpoint_hydration() -> None:
    """Suffix-only input must hydrate prefix cadence; ignoring checkpoint-in fails."""
    prefix = [
        _tare("t1", "Z1", 1, 1, 50, 0),
        _pick("p1", "Z1", 1, 100, "t1"),
        _pick("p2", "Z1", 2, 200, "t1"),
        _pick("p3", "Z1", 3, 300, "t1"),
    ]
    suffix = [
        _tare("t1", "Z1", 1, 1, 50, 0),
        _pick("p4", "Z1", 4, 100, "t1"),
    ]
    extended = prefix + suffix[1:]
    expected = _reference_report(extended)
    suffix_only = _reference_report(suffix)
    assert suffix_only["balance_stamp"] != expected["balance_stamp"]
    assert suffix_only["zones"] != expected["zones"]
    assert len(expected["zones"][0]["pick_marks"]) == 1
    assert suffix_only["zones"][0]["pick_marks"] == []
    with tempfile.TemporaryDirectory() as tmp:
        suffix_inp = _scratch_path(Path(tmp), "suffix", "jsonl")
        ckpt = _scratch_path(Path(tmp), "ckpt")
        warm_out = _scratch_path(Path(tmp), "warm")
        cold_suffix_out = _scratch_path(Path(tmp), "cold_suffix")
        _write_feed(suffix_inp, suffix)
        ckpt_payload = _reference_continuation_checkpoint(prefix, suffix, suffix_inp)
        for zone in ckpt_payload["zone_order"]:
            assert ckpt_payload["zone_states"][zone]["kept_rows"] == _reference_kept_rows(
                prefix, zone
            )
        ckpt.write_text(json.dumps(ckpt_payload) + "\n", encoding="utf-8")
        proc = _rebuild_and_run(suffix_inp, cold_suffix_out)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        cold_suffix = json.loads(cold_suffix_out.read_text(encoding="utf-8"))
        assert cold_suffix["checkpoint_used"] is False
        assert cold_suffix == suffix_only
        proc = _rebuild_and_run(suffix_inp, warm_out, checkpoint_in=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        warm = json.loads(warm_out.read_text(encoding="utf-8"))
        assert warm["checkpoint_used"] is True
        assert warm["zones"] == expected["zones"]
        assert warm["balance_stamp"] == expected["balance_stamp"]
        assert warm != cold_suffix


def test_prefix_checkpoint_on_extended_input_replays_suffix_cold() -> None:
    """Prefix checkpoint on extended input must cold-replay to the full-feed report."""
    prefix = [
        _tare("t1", "Z1", 1, 1, 50, 0),
        _pick("p1", "Z1", 1, 100, "t1"),
        _pick("p2", "Z1", 2, 200, "t1"),
    ]
    suffix = [
        _pick("p3", "Z1", 3, 300, "t1"),
        _spoilage("p2", 1),
        _supersede("p3", 2, "replace", 400),
    ]
    extended = prefix + suffix
    expected = _reference_report(extended)
    with tempfile.TemporaryDirectory() as tmp:
        prefix_inp = _scratch_path(Path(tmp), "prefix", "jsonl")
        ext_inp = _scratch_path(Path(tmp), "extended", "jsonl")
        ckpt = _scratch_path(Path(tmp), "ckpt")
        cold_out = _scratch_path(Path(tmp), "cold")
        warm_out = _scratch_path(Path(tmp), "warm")
        _write_feed(prefix_inp, prefix)
        proc = _rebuild_and_run(prefix_inp, checkpoint_out=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        _write_feed(ext_inp, extended)
        proc = _rebuild_and_run(ext_inp, cold_out)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        proc = _rebuild_and_run(ext_inp, warm_out, checkpoint_in=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        warm = json.loads(warm_out.read_text(encoding="utf-8"))
        cold = json.loads(cold_out.read_text(encoding="utf-8"))
        assert warm["checkpoint_used"] is False
        assert warm["zones"] == cold["zones"] == expected["zones"]
        assert warm["balance_stamp"] == cold["balance_stamp"] == expected["balance_stamp"]


def test_last_event_position_zero_for_first_row() -> None:
    """A single-row feed must record last_event_position 0 in checkpoints."""
    rows = [_pick("p1", "Z1", 1, 100, "none")]
    with tempfile.TemporaryDirectory() as tmp:
        inp = _scratch_path(Path(tmp), "feed", "jsonl")
        ckpt = _scratch_path(Path(tmp), "ckpt")
        _write_feed(inp, rows)
        proc = _rebuild_and_run(inp, checkpoint_out=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        payload = json.loads(ckpt.read_text(encoding="utf-8"))
        assert payload["last_event_position"] == 0
        assert payload["last_event_position"] == _last_event_position(rows)


def test_checkpoint_rejects_tampered_zone_states() -> None:
    """Inconsistent zone_states must force cold replay on the same input bytes."""
    rows = _checkpoint_base_rows()

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        zone = payload["zone_order"][0]
        payload["zone_states"][zone]["net_kept_g"] = CAP + 88000000

    _assert_cold_fallback_report(
        _run_with_tampered_checkpoint(rows, mutate), _reference_report(rows)
    )


def test_repeated_replay_is_byte_identical() -> None:
    """Repeated runs on the same input must emit byte-identical report files."""
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        out_a = Path(tmp_a) / "pick_report.json"
        out_b = Path(tmp_b) / "pick_report.json"
        _rebuild_and_run(out=out_a)
        _rebuild_and_run(out=out_b)
        first = out_a.read_bytes()
        second = out_b.read_bytes()
        assert first == second
        assert first.endswith(b"\n")
        assert b"\r\n" not in first


def test_supersede_equal_generation_prefers_earlier_input() -> None:
    """Equal-generation supersede rows must keep the first ingested winner."""
    replace_first = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 500, "t1"),
        _supersede("p1", 5, "replace", 100),
        _supersede("p1", 5, "void"),
    ]
    void_first = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 500, "t1"),
        _supersede("p1", 5, "void"),
        _supersede("p1", 5, "replace", 100),
    ]
    replace_expected = _reference_report(replace_first)
    void_expected = _reference_report(void_first)
    assert replace_expected["zones"][0]["net_kept_g"] == 100
    assert void_expected["zones"][0]["net_kept_g"] == 0
    assert _run_scenario(replace_first) == replace_expected
    assert _run_scenario(void_first) == void_expected


def test_spoilage_equal_generation_prefers_earlier_input() -> None:
    """Equal-generation spoilage rows must keep the first ingested winner."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 150, "t1"),
        _spoilage("p1", 4),
        _spoilage("p1", 4),
    ]
    picks, tares, _, spoilages = _split_feed(rows)
    baseline = _baseline_kept(picks, tares)
    winners = _spoilage_winners(spoilages, baseline)
    assert winners["p1"]["generation"] == 4
    expected = _reference_report(rows)
    assert expected["zones"][0]["grade_prime"] == 0
    assert expected["zones"][0]["grade_standard"] == 1
    assert _run_scenario(rows) == expected


def test_all_voided_zone_emits_zeroed_record() -> None:
    """A zone whose kept picks are all voided must still emit a zeroed zone record."""
    rows = [
        _tare("t1", "Z1", 1, 1, 50, 0),
        _pick("p1", "Z1", 1, 100, "t1"),
        _pick("p2", "Z1", 2, 200, "t1"),
        _supersede("p1", 1, "void"),
        _supersede("p2", 1, "void"),
    ]
    expected = _reference_report(rows)
    zone = expected["zones"][0]
    assert zone["zone"] == "Z1"
    assert zone["grade_prime"] == 0
    assert zone["grade_standard"] == 0
    assert zone["grade_cull"] == 0
    assert zone["net_kept_g"] == 0
    assert zone["net_refused"] == 0
    assert zone["pick_marks"] == []
    assert _run_scenario(rows) == expected


def test_retroactive_supersede_invalidates_checkpoint() -> None:
    """Stale checkpoints after lineage change must not alter cold replay output."""
    base = [
        _tare("t1", "Z1", 1, 1, 50, 0),
        _pick("p1", "Z1", 1, 500, "t1"),
        _pick("p2", "Z1", 2, 500, "t1"),
    ]
    extended = base + [_supersede("p1", 1, "replace", 100)]
    with tempfile.TemporaryDirectory() as tmp:
        base_inp = _scratch_path(Path(tmp), "base", "jsonl")
        ext_inp = _scratch_path(Path(tmp), "ext", "jsonl")
        ckpt = _scratch_path(Path(tmp), "ckpt")
        cold_out = _scratch_path(Path(tmp), "cold")
        stale_out = _scratch_path(Path(tmp), "stale")
        _write_feed(base_inp, base)
        proc = _rebuild_and_run(base_inp, checkpoint_out=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        _write_feed(ext_inp, extended)
        proc = _rebuild_and_run(ext_inp, cold_out)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        proc = _rebuild_and_run(ext_inp, stale_out, checkpoint_in=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        stale = json.loads(stale_out.read_text())
        _assert_cold_fallback_report(stale, _reference_report(extended))


def test_grade_prime_boundary_below_200() -> None:
    """Effective net 199 must classify as prime; 200 must be standard."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 199, "t1"),
        _pick("p2", "Z1", 2, 200, "t1"),
    ]
    expected = _reference_report(rows)
    zone = expected["zones"][0]
    assert zone["grade_prime"] == 1
    assert zone["grade_standard"] == 1
    assert _run_scenario(rows) == expected


def test_grade_cull_boundary_above_850() -> None:
    """Effective net 850 must stay standard; 851 must be cull."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 850, "t1"),
        _pick("p2", "Z1", 2, 851, "t1"),
    ]
    expected = _reference_report(rows)
    zone = expected["zones"][0]
    assert zone["grade_standard"] == 1
    assert zone["grade_cull"] == 1
    assert _run_scenario(rows) == expected


def test_grade_after_tare_offset_crosses_threshold() -> None:
    """Grade must use effective net after tare offset, not gross alone."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, -51),
        _pick("p1", "Z1", 1, 250, "t1"),
    ]
    expected = _reference_report(rows)
    zone = expected["zones"][0]
    assert zone["grade_prime"] == 1
    assert zone["net_kept_g"] == 199
    assert _run_scenario(rows) == expected


def test_tare_lineage_includes_revoked_highest_generation() -> None:
    """Revoked highest generation must still appear in tare lineage binding."""
    rows = [
        _tare("tp-x", "Z", 1, 1, 10, 5, status="active"),
        _tare("tp-x", "Z", 2, 1, 10, 99, status="revoked"),
        _tare("tp-y", "Z", 1, 1, 10, -3, status="active"),
        _pick("p1", "Z", 5, 100, "tp-x"),
    ]
    expected = _reference_report(rows)
    lineage = _tare_lineage([r for r in rows if r["kind"] == "tare"])
    assert lineage
    assert expected["zones"][0]["net_kept_g"] == 105
    assert _run_scenario(rows) == expected


def test_tare_lineage_generation_tie_prefers_earlier_input() -> None:
    """Equal-generation tare rows must keep the first ingested representative."""
    rows = [
        _tare("tp-a", "Z", 3, 1, 10, 11, status="active"),
        _tare("tp-a", "Z", 3, 1, 10, 22, status="revoked"),
        _pick("p1", "Z", 2, 100, "tp-a"),
    ]
    lineage = _tare_lineage([r for r in rows if r["kind"] == "tare"])
    assert lineage.count(";") == 0
    assert _run_scenario(rows) == _reference_report(rows)


def test_balance_stamp_binds_documented_lineage_segments() -> None:
    """Balance stamp must hash marks plus tare, supersede, and spoilage lineage."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 150, "t1"),
        _spoilage("p1", 1),
        _supersede("p1", 1, "void"),
    ]
    expected = _reference_report(rows)
    assert _run_scenario(rows)["balance_stamp"] == expected["balance_stamp"]


def test_capacity_refusal_preserves_prior_net_kept_g() -> None:
    """A capacity refusal must not change net_kept_g for the zone."""
    rows = [
        _tare("t1", "Z1", 1, 1, 50, 0),
        _pick("p1", "Z1", 1, 11900, "t1"),
        _pick("p2", "Z1", 2, 200, "t1"),
    ]
    expected = _reference_report(rows)
    zone = expected["zones"][0]
    assert zone["net_kept_g"] == 11900
    assert zone["net_refused"] == 1
    assert _run_scenario(rows) == expected


def test_refused_and_void_rows_skip_mark_cadence() -> None:
    """Refused and voided rows must not advance the kept-row cadence counter."""
    rows = [
        _tare("t1", "Z1", 1, 1, 50, 0),
        _pick("p1", "Z1", 1, 100, "t1"),
        _pick("p2", "Z1", 2, 100, "t1"),
        _pick("p3", "Z1", 3, 100, "t1"),
        _tare("t2", "Z1", 1, 4, 5, -200),
        _pick("p4", "Z1", 4, 50, "t2"),
        _pick("p5", "Z1", 5, 100, "t1"),
        _supersede("p5", 1, "void"),
        _pick("p6", "Z1", 6, 100, "t1"),
    ]
    expected = _reference_report(rows)
    assert len(expected["zones"][0]["pick_marks"]) == 1
    assert _run_scenario(rows) == expected


def test_supersede_generation_uses_numeric_order() -> None:
    """Supersede winner must use numeric generation, not lexicographic order."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 500, "t1"),
        _supersede("p1", 2, "replace", 100),
        _supersede("p1", 10, "void"),
    ]
    expected = _reference_report(rows)
    zone = expected["zones"][0]
    assert zone["grade_prime"] == 0
    assert zone["net_kept_g"] == 0
    assert _run_scenario(rows) == expected


def test_spoilage_generation_uses_numeric_order() -> None:
    """Spoilage winner must use numeric generation, not lexicographic order."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 150, "t1"),
        _spoilage("p1", 2),
        _spoilage("p1", 10),
    ]
    expected = _reference_report(rows)
    zone = expected["zones"][0]
    assert zone["grade_prime"] == 0
    assert zone["grade_standard"] == 1
    assert _run_scenario(rows) == expected


def test_overlapping_generations_with_revoked_newest() -> None:
    """Overlapping active ranges must fall back when newest generation is revoked."""
    rows = [
        _tare("t1", "orchard-north", 1, 1, 100, 10, status="active"),
        _tare("t1", "orchard-north", 5, 1, 100, 200, status="revoked"),
        _tare("t1", "orchard-north", 3, 1, 100, 50, status="active"),
        _pick("p1", "orchard-north", 10, 140, "t1"),
    ]
    expected = _reference_report(rows)
    assert expected["zones"][0]["net_kept_g"] == 190
    assert _run_scenario(rows) == expected


def test_tare_generation_10_beats_2_not_lexicographic() -> None:
    """Tare offset resolution must compare generations numerically (10 > 2)."""
    rows = [
        _tare("tp", "Z", 2, 1, 20, 50, status="active"),
        _tare("tp", "Z", 10, 1, 20, -30, status="active"),
        _pick("p1", "Z", 5, 100, "tp"),
    ]
    expected = _reference_report(rows)
    assert expected["zones"][0]["net_kept_g"] == 70
    assert _run_scenario(rows) == expected


def test_tare_pick_time_generation_tie_prefers_earlier_input() -> None:
    """Equal-generation active tare matches must keep the first ingested offset."""
    rows = [
        _tare("tp", "Z", 5, 1, 20, 25, status="active"),
        _tare("tp", "Z", 5, 1, 20, 99, status="active"),
        _pick("p1", "Z", 3, 100, "tp"),
    ]
    expected = _reference_report(rows)
    assert expected["zones"][0]["net_kept_g"] == 125
    assert _run_scenario(rows) == expected


def test_tare_lineage_numeric_generation_10_over_2() -> None:
    """Tare lineage representative must use numeric generation, not lexicographic."""
    rows = [
        _tare("tp-z", "Z", 2, 1, 10, 1, status="active"),
        _tare("tp-z", "Z", 10, 1, 10, 2, status="revoked"),
        _pick("p1", "Z", 5, 100, "tp-z"),
    ]
    assert _run_scenario(rows) == _reference_report(rows)


def test_tare_offset_crosses_prime_to_standard_at_200() -> None:
    """Effective net 200 after tare must classify as standard."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, -1),
        _pick("p1", "Z1", 1, 201, "t1"),
    ]
    expected = _reference_report(rows)
    zone = expected["zones"][0]
    assert zone["grade_prime"] == 0
    assert zone["grade_standard"] == 1
    assert zone["net_kept_g"] == 200
    assert _run_scenario(rows) == expected


def test_tare_offset_crosses_standard_to_cull_at_851() -> None:
    """Effective net 851 after tare must classify as cull."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, -1),
        _pick("p1", "Z1", 1, 852, "t1"),
    ]
    expected = _reference_report(rows)
    zone = expected["zones"][0]
    assert zone["grade_standard"] == 0
    assert zone["grade_cull"] == 1
    assert zone["net_kept_g"] == 851
    assert _run_scenario(rows) == expected


def test_spoilage_downgrade_applies_after_tare_not_gross() -> None:
    """Spoilage must downgrade the grade computed from effective net, not gross."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, -51),
        _pick("p1", "Z1", 1, 250, "t1"),
        _spoilage("p1", 1),
    ]
    expected = _reference_report(rows)
    zone = expected["zones"][0]
    assert zone["grade_prime"] == 0
    assert zone["grade_standard"] == 1
    assert zone["net_kept_g"] == 199
    assert _run_scenario(rows) == expected


def test_spoilage_after_tare_at_standard_boundary() -> None:
    """Spoilage after tare-derived standard must downgrade to cull."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, -1),
        _pick("p1", "Z1", 1, 201, "t1"),
        _spoilage("p1", 1),
    ]
    expected = _reference_report(rows)
    zone = expected["zones"][0]
    assert zone["grade_standard"] == 0
    assert zone["grade_cull"] == 1
    assert _run_scenario(rows) == expected


def test_void_sandwiched_between_accepted_skips_cadence() -> None:
    """A void row between accepted picks must not advance mark cadence."""
    rows = [
        _tare("t1", "Z1", 1, 1, 50, 0),
        _pick("p1", "Z1", 1, 100, "t1"),
        _pick("p2", "Z1", 2, 100, "t1"),
        _pick("p3", "Z1", 3, 100, "t1"),
        _pick("p4", "Z1", 4, 100, "t1"),
        _supersede("p4", 1, "void"),
        _pick("p5", "Z1", 5, 100, "t1"),
        _pick("p6", "Z1", 6, 100, "t1"),
        _pick("p7", "Z1", 7, 100, "t1"),
    ]
    expected = _reference_report(rows)
    assert len(expected["zones"][0]["pick_marks"]) == 1
    assert _run_scenario(rows) == expected


def test_capacity_refusal_sandwiched_skips_cadence() -> None:
    """A capacity refusal between accepted picks must not advance mark cadence."""
    rows = [
        _tare("t1", "Z1", 1, 1, 50, 0),
        _pick("p1", "Z1", 1, 100, "t1"),
        _pick("p2", "Z1", 2, 100, "t1"),
        _pick("p3", "Z1", 3, 100, "t1"),
        _pick("p4", "Z1", 4, 11900, "t1"),
        _pick("p5", "Z1", 5, 100, "t1"),
        _pick("p6", "Z1", 6, 100, "t1"),
        _pick("p7", "Z1", 7, 100, "t1"),
    ]
    expected = _reference_report(rows)
    zone = expected["zones"][0]
    assert zone["net_kept_g"] == 600
    assert zone["net_refused"] == 1
    assert len(zone["pick_marks"]) == 1
    assert _run_scenario(rows) == expected


def test_zone_order_unchanged_by_tare_and_supersede_rows() -> None:
    """Tare and supersede rows must not reorder zones established by first pick."""
    rows = [
        _pick("p1", "orchard-west", 2, 100, "none"),
        _tare("t1", "orchard-east", 1, 1, 20, 0),
        _pick("p2", "orchard-east", 1, 100, "t1"),
        _supersede("p1", 1, "replace", 150),
    ]
    expected = _reference_report(rows)
    labels = [z["zone"] for z in expected["zones"]]
    assert labels == ["orchard-east", "orchard-west"]
    assert _run_scenario(rows) == expected


def test_retroactive_tare_invalidates_checkpoint() -> None:
    """Stale checkpoints after tare lineage change must not alter cold replay."""
    base = [
        _tare("t1", "Z1", 1, 1, 50, 0),
        _pick("p1", "Z1", 1, 500, "t1"),
    ]
    extended = base + [
        _tare("t2", "Z1", 2, 1, 50, 10, status="active"),
        _pick("p2", "Z1", 2, 500, "t1"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        base_inp = _scratch_path(Path(tmp), "base", "jsonl")
        ext_inp = _scratch_path(Path(tmp), "ext", "jsonl")
        ckpt = _scratch_path(Path(tmp), "ckpt")
        cold_out = _scratch_path(Path(tmp), "cold")
        stale_out = _scratch_path(Path(tmp), "stale")
        _write_feed(base_inp, base)
        proc = _rebuild_and_run(base_inp, checkpoint_out=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        _write_feed(ext_inp, extended)
        proc = _rebuild_and_run(ext_inp, cold_out)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        proc = _rebuild_and_run(ext_inp, stale_out, checkpoint_in=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        stale = json.loads(stale_out.read_text())
        _assert_cold_fallback_report(stale, _reference_report(extended))


def test_invalid_checkpoint_ignored_for_cold_replay() -> None:
    """Invalid checkpoint resume must yield the same report as no checkpoint."""
    rows = [
        _tare("t1", "Z1", 1, 1, 50, 0),
        _pick("p1", "Z1", 1, 100, "t1"),
        _pick("p2", "Z1", 2, 200, "t1"),
    ]
    other = [
        _tare("t1", "Z9", 1, 1, 50, 0),
        _pick("p9", "Z9", 1, 999, "t1"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        inp = _scratch_path(Path(tmp), "feed", "jsonl")
        other_inp = _scratch_path(Path(tmp), "other", "jsonl")
        ckpt = _scratch_path(Path(tmp), "ckpt")
        cold_out = _scratch_path(Path(tmp), "cold")
        warm_out = _scratch_path(Path(tmp), "warm")
        _write_feed(inp, rows)
        _write_feed(other_inp, other)
        proc = _rebuild_and_run(other_inp, checkpoint_out=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        proc = _rebuild_and_run(inp, cold_out)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        proc = _rebuild_and_run(inp, warm_out, checkpoint_in=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        assert json.loads(warm_out.read_text()) == json.loads(cold_out.read_text())


def test_balance_stamp_changes_when_supersede_generation_order_fixes() -> None:
    """Supersede generation numeric order must change balance_stamp binding."""
    void_wins = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 500, "t1"),
        _supersede("p1", 2, "replace", 100),
        _supersede("p1", 10, "void"),
    ]
    replace_only = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 500, "t1"),
        _supersede("p1", 2, "replace", 100),
    ]
    void_stamp = _reference_report(void_wins)["balance_stamp"]
    replace_stamp = _reference_report(replace_only)["balance_stamp"]
    assert void_stamp != replace_stamp
    assert _run_scenario(void_wins)["balance_stamp"] == void_stamp


def test_balance_stamp_changes_when_revoked_lineage_changes() -> None:
    """Revoked tare lineage representatives must change balance_stamp."""
    with_revoked = [
        _tare("tp", "Z", 1, 1, 10, 5, status="active"),
        _tare("tp", "Z", 2, 1, 10, 99, status="revoked"),
        _pick("p1", "Z", 5, 100, "tp"),
    ]
    without_revoked = [
        _tare("tp", "Z", 1, 1, 10, 5, status="active"),
        _pick("p1", "Z", 5, 100, "tp"),
    ]
    revoked_stamp = _reference_report(with_revoked)["balance_stamp"]
    active_stamp = _reference_report(without_revoked)["balance_stamp"]
    assert revoked_stamp != active_stamp
    assert _run_scenario(with_revoked)["balance_stamp"] == revoked_stamp


def test_balance_stamp_changes_when_tare_offset_changes() -> None:
    """Tare offset changes must change balance_stamp even without pick marks."""
    low = [
        _tare("tp", "Z", 1, 1, 10, 0, status="active"),
        _pick("p1", "Z", 5, 100, "tp"),
    ]
    high = [
        _tare("tp", "Z", 1, 1, 10, 5, status="active"),
        _pick("p1", "Z", 5, 100, "tp"),
    ]
    low_stamp = _reference_report(low)["balance_stamp"]
    high_stamp = _reference_report(high)["balance_stamp"]
    assert low_stamp != high_stamp
    assert _run_scenario(high)["balance_stamp"] == high_stamp


def test_balance_stamp_changes_when_mark_cadence_changes() -> None:
    """Pick-mark cadence state must change balance_stamp."""
    four_kept = [
        _tare("t1", "Z1", 1, 1, 50, 0),
        _pick("p1", "Z1", 1, 100, "t1"),
        _pick("p2", "Z1", 2, 100, "t1"),
        _pick("p3", "Z1", 3, 100, "t1"),
        _pick("p4", "Z1", 4, 100, "t1"),
    ]
    three_kept = four_kept[:-1]
    four_stamp = _reference_report(four_kept)["balance_stamp"]
    three_stamp = _reference_report(three_kept)["balance_stamp"]
    assert four_stamp != three_stamp
    assert _run_scenario(four_kept)["balance_stamp"] == four_stamp


def test_balance_stamp_changes_when_spoilage_generation_order_changes() -> None:
    """Spoilage generation numeric order must change balance_stamp binding."""
    gen10_winner = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 150, "t1"),
        _spoilage("p1", 2),
        _spoilage("p1", 10),
    ]
    gen2_winner = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 150, "t1"),
        _spoilage("p1", 2),
    ]
    gen10_stamp = _reference_report(gen10_winner)["balance_stamp"]
    gen2_stamp = _reference_report(gen2_winner)["balance_stamp"]
    assert gen10_stamp != gen2_stamp
    assert _run_scenario(gen10_winner)["balance_stamp"] == gen10_stamp


def _reference_kept_rows(rows: list[dict], zone: str) -> int:
    ref = _reference_report(rows)
    match = next(item for item in ref["zones"] if item["zone"] == zone)
    return (
        int(match["grade_prime"])
        + int(match["grade_standard"])
        + int(match["grade_cull"])
    )


def _reference_zone_checkpoint_states(rows: list[dict]) -> dict[str, dict]:
    report = _reference_report(rows)
    states: dict[str, dict] = {}
    for zone in report["zones"]:
        label = str(zone["zone"])
        states[label] = {
            "grade_prime": zone["grade_prime"],
            "grade_standard": zone["grade_standard"],
            "grade_cull": zone["grade_cull"],
            "net_kept_g": zone["net_kept_g"],
            "net_refused": zone["net_refused"],
            "pick_marks": list(zone["pick_marks"]),
            "kept_rows": _reference_kept_rows(rows, label),
        }
    return states


def _checkpoint_winner_maps(rows: list[dict]) -> tuple[dict, dict]:
    picks, tares, supersedes, spoilages = _split_feed(rows)
    baseline = _baseline_kept(picks, tares)
    return _supersede_winners(supersedes, baseline), _spoilage_winners(
        spoilages, baseline
    )


def _reference_continuation_checkpoint(
    prefix_rows: list[dict],
    suffix_rows: list[dict],
    suffix_path: Path,
) -> dict:
    prefix_report = _reference_report(prefix_rows)
    picks, tares, _, _ = _split_feed(suffix_rows)
    supersede_w, spoilage_w = _checkpoint_winner_maps(suffix_rows)
    return {
        "input_identity": _file_sha256(suffix_path),
        "schema_generation": SCHEMA_GENERATION,
        "last_event_position": _last_event_position(prefix_rows),
        "previous_stamp_seed": prefix_report["balance_stamp"],
        "tare_lineage": _tare_lineage(tares),
        "zone_order": _zone_order(picks),
        "zone_states": _reference_zone_checkpoint_states(prefix_rows),
        "supersede_winners": supersede_w,
        "spoilage_winners": spoilage_w,
    }


def _assert_checkpoint_kept_rows_exact(rows: list[dict], payload: dict) -> None:
    expected_states = _reference_zone_checkpoint_states(rows)
    for zone in payload["zone_order"]:
        observed = payload["zone_states"][zone]["kept_rows"]
        assert observed == expected_states[zone]["kept_rows"], (
            f"kept_rows mismatch for {zone}: {observed} != "
            f"{expected_states[zone]['kept_rows']}"
        )


def _checkpoint_base_rows() -> list[dict]:
    return [
        _tare("t1", "Z1", 1, 1, 50, 0),
        _pick("p1", "Z1", 1, 100, "t1"),
        _pick("p2", "Z1", 2, 200, "t1"),
        _pick("p3", "Z1", 3, 300, "t1"),
    ]


def _assert_cold_fallback_report(warm: dict, expected: dict) -> None:
    assert warm["zones"] == expected["zones"]
    assert warm["balance_stamp"] == expected["balance_stamp"]
    assert warm["checkpoint_used"] is False


def _run_with_tampered_checkpoint(
    rows: list[dict],
    mutate,
) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        inp = _scratch_path(Path(tmp), "feed", "jsonl")
        cold_out = _scratch_path(Path(tmp), "cold")
        warm_out = _scratch_path(Path(tmp), "warm")
        ckpt = _scratch_path(Path(tmp), "ckpt")
        _write_feed(inp, rows)
        proc = _rebuild_and_run(inp, cold_out, checkpoint_out=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        payload = json.loads(ckpt.read_text(encoding="utf-8"))
        mutate(payload, inp, rows)
        ckpt.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        proc = _rebuild_and_run(inp, warm_out, checkpoint_in=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        return json.loads(warm_out.read_text(encoding="utf-8"))


def test_checkpoint_rejects_tampered_input_identity() -> None:
    """input_identity mismatch must force cold replay on the same input bytes."""
    rows = _checkpoint_base_rows()
    expected = _reference_report(rows)

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        payload["input_identity"] = "0" * 64

    assert _assert_cold_fallback_report(_run_with_tampered_checkpoint(rows, mutate), expected) is None


def test_checkpoint_rejects_tampered_tare_lineage() -> None:
    """tare_lineage mismatch must force cold replay on the same input bytes."""
    rows = _checkpoint_base_rows()
    expected = _reference_report(rows)

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        payload["tare_lineage"] = "tampered"

    assert _assert_cold_fallback_report(_run_with_tampered_checkpoint(rows, mutate), expected) is None


def test_checkpoint_rejects_tampered_supersede_winners() -> None:
    """supersede_winners mismatch must force cold replay on the same input bytes."""
    rows = _checkpoint_base_rows() + [_supersede("p1", 1, "void")]
    expected = _reference_report(rows)

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        payload["supersede_winners"] = {}

    assert _assert_cold_fallback_report(_run_with_tampered_checkpoint(rows, mutate), expected) is None


def test_checkpoint_rejects_tampered_spoilage_winners() -> None:
    """spoilage_winners mismatch must force cold replay on the same input bytes."""
    rows = _checkpoint_base_rows() + [_spoilage("p2", 1)]
    expected = _reference_report(rows)

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        payload["spoilage_winners"] = {}

    assert _assert_cold_fallback_report(_run_with_tampered_checkpoint(rows, mutate), expected) is None


def test_checkpoint_rejects_tampered_schema_generation() -> None:
    """schema_generation mismatch must force cold replay on the same input bytes."""
    rows = _checkpoint_base_rows()
    expected = _reference_report(rows)

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        payload["schema_generation"] = SCHEMA_GENERATION + 1

    assert _assert_cold_fallback_report(_run_with_tampered_checkpoint(rows, mutate), expected) is None


def test_checkpoint_rejects_tampered_last_event_position() -> None:
    """last_event_position mismatch must force cold replay on the same input bytes."""
    rows = _checkpoint_base_rows()
    expected = _reference_report(rows)

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        payload["last_event_position"] = _last_event_position(_rows) - 1

    assert _assert_cold_fallback_report(_run_with_tampered_checkpoint(rows, mutate), expected) is None


def test_checkpoint_rejects_tampered_previous_stamp_seed() -> None:
    """previous_stamp_seed mismatch must force cold replay on the same input bytes."""
    rows = _checkpoint_base_rows()
    expected = _reference_report(rows)

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        payload["previous_stamp_seed"] = "0" * 64

    assert _assert_cold_fallback_report(_run_with_tampered_checkpoint(rows, mutate), expected) is None


def test_checkpoint_rejects_tampered_kept_rows() -> None:
    """Tampered kept_rows must force cold replay on the same input bytes."""
    rows = _checkpoint_base_rows()
    expected = _reference_report(rows)

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        zone = payload["zone_order"][0]
        payload["zone_states"][zone]["kept_rows"] += 1

    warm = _run_with_tampered_checkpoint(rows, mutate)
    assert warm["zones"] == expected["zones"]
    assert warm["balance_stamp"] == expected["balance_stamp"]
    assert warm["checkpoint_used"] is False


def test_checkpoint_rejects_extra_top_level_field() -> None:
    """Extra top-level checkpoint keys must force cold replay."""
    rows = _checkpoint_base_rows()
    expected = _reference_report(rows)

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        payload["debug_state"] = {"tampered": True}

    assert _assert_cold_fallback_report(_run_with_tampered_checkpoint(rows, mutate), expected) is None


def test_checkpoint_rejects_tampered_zone_order() -> None:
    """Tampered zone_order must force cold replay on the same input bytes."""
    rows = [
        _tare("ta", "Z-west", 1, 1, 50, 0),
        _pick("p1", "Z-west", 1, 100, "ta"),
        _tare("tb", "Z-east", 1, 1, 50, 0),
        _pick("p2", "Z-east", 2, 200, "tb"),
    ]
    expected = _reference_report(rows)

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        payload["zone_order"] = list(reversed(payload["zone_order"]))

    assert _assert_cold_fallback_report(_run_with_tampered_checkpoint(rows, mutate), expected) is None


def test_checkpoint_out_exact_top_level_fields() -> None:
    """--checkpoint-out must emit exactly the documented top-level keys."""
    rows = _checkpoint_base_rows()
    with tempfile.TemporaryDirectory() as tmp:
        inp = _scratch_path(Path(tmp), "feed", "jsonl")
        ckpt = _scratch_path(Path(tmp), "ckpt")
        _write_feed(inp, rows)
        proc = _rebuild_and_run(inp, checkpoint_out=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        payload = json.loads(ckpt.read_text(encoding="utf-8"))
        assert set(payload) == CHECKPOINT_TOP_FIELDS


def test_valid_checkpoint_warm_resume_does_not_double_count() -> None:
    """Warm resume on a valid complete-input checkpoint must not double-count rows."""
    rows = _checkpoint_base_rows()
    expected = _reference_report(rows)
    with tempfile.TemporaryDirectory() as tmp:
        inp = _scratch_path(Path(tmp), "feed", "jsonl")
        cold_out = _scratch_path(Path(tmp), "cold")
        warm_out = _scratch_path(Path(tmp), "warm")
        ckpt = _scratch_path(Path(tmp), "ckpt")
        _write_feed(inp, rows)
        proc = _rebuild_and_run(inp, cold_out, checkpoint_out=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        proc = _rebuild_and_run(inp, warm_out, checkpoint_in=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        warm = json.loads(warm_out.read_text(encoding="utf-8"))
        cold = json.loads(cold_out.read_text(encoding="utf-8"))
        assert warm["checkpoint_used"] is True
        assert cold["checkpoint_used"] is False
        assert warm["zones"] == cold["zones"] == expected["zones"]
        assert warm["balance_stamp"] == cold["balance_stamp"] == expected["balance_stamp"]
        zone = warm["zones"][0]
        assert zone["net_kept_g"] == 600
        assert zone["grade_prime"] + zone["grade_standard"] + zone["grade_cull"] == 3


def test_cold_and_warm_replay_match_lineage_and_digest() -> None:
    """Cold and warm replay must agree on balance_stamp and zone lineage totals."""
    rows = [
        _tare("t1", "Z1", 1, 1, 50, 0),
        _pick("p1", "Z1", 1, 100, "t1"),
        _pick("p2", "Z1", 2, 200, "t1"),
        _spoilage("p2", 1),
        _supersede("p1", 2, "replace", 150),
    ]
    expected = _reference_report(rows)
    with tempfile.TemporaryDirectory() as tmp:
        inp = _scratch_path(Path(tmp), "feed", "jsonl")
        cold_out = _scratch_path(Path(tmp), "cold")
        warm_out = _scratch_path(Path(tmp), "warm")
        ckpt = _scratch_path(Path(tmp), "ckpt")
        _write_feed(inp, rows)
        proc = _rebuild_and_run(inp, cold_out, checkpoint_out=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        proc = _rebuild_and_run(inp, warm_out, checkpoint_in=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        cold = json.loads(cold_out.read_text(encoding="utf-8"))
        warm = json.loads(warm_out.read_text(encoding="utf-8"))
        assert warm["checkpoint_used"] is True
        assert cold["checkpoint_used"] is False
        assert warm["balance_stamp"] == cold["balance_stamp"] == expected["balance_stamp"]
        assert warm["zones"] == cold["zones"] == expected["zones"]


def test_shuffled_non_pick_rows_preserve_output() -> None:
    """Shuffled tare/supersede/spoilage row order must not change settled output."""
    base_picks = [
        _pick("p1", "Z1", 1, 100, "t1"),
        _pick("p2", "Z1", 2, 200, "t1"),
    ]
    ordered = [
        _tare("t1", "Z1", 1, 1, 50, 0),
        *base_picks,
        _spoilage("p2", 1),
        _supersede("p1", 2, "replace", 150),
    ]
    shuffled = [
        _spoilage("p2", 1),
        _pick("p2", "Z1", 2, 200, "t1"),
        _tare("t1", "Z1", 1, 1, 50, 0),
        _supersede("p1", 2, "replace", 150),
        _pick("p1", "Z1", 1, 100, "t1"),
    ]
    expected = _reference_report(ordered)
    assert _run_scenario(shuffled) == expected


def test_same_sequence_zone_order_tie_breaks_by_file_order() -> None:
    """Equal-sequence picks must establish zone order by file order."""
    rows = [
        _tare("ta", "orchard-west", 1, 1, 20, 0),
        _pick("p-west", "orchard-west", 5, 100, "ta"),
        _tare("tb", "orchard-east", 1, 1, 20, 0),
        _pick("p-east", "orchard-east", 5, 100, "tb"),
    ]
    expected = _reference_report(rows)
    labels = [z["zone"] for z in expected["zones"]]
    assert labels == ["orchard-west", "orchard-east"]
    assert _run_scenario(rows) == expected


def test_capacity_exact_at_limit_accepted() -> None:
    """A row that brings net_kept_g exactly to 12000 must be accepted."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 6000, "t1"),
        _pick("p2", "Z1", 2, 6000, "t1"),
    ]
    expected = _reference_report(rows)
    zone = expected["zones"][0]
    assert zone["net_kept_g"] == CAP
    assert zone["net_refused"] == 0
    assert _run_scenario(rows) == expected


def test_capacity_one_gram_over_limit_refused() -> None:
    """A row that would push net_kept_g above 12000 must be refused."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 6000, "t1"),
        _pick("p2", "Z1", 2, 6001, "t1"),
    ]
    expected = _reference_report(rows)
    zone = expected["zones"][0]
    assert zone["net_kept_g"] == 6000
    assert zone["net_refused"] == 1
    assert _run_scenario(rows) == expected


def test_capacity_one_gram_under_limit_then_refused() -> None:
    """A row after net_kept_g 11999 that would exceed capacity must be refused."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 11999, "t1"),
        _pick("p2", "Z1", 2, 2, "t1"),
    ]
    expected = _reference_report(rows)
    zone = expected["zones"][0]
    assert zone["net_kept_g"] == 11999
    assert zone["net_refused"] == 1
    assert _run_scenario(rows) == expected


def test_report_pretty_printed_utf8_with_trailing_newline(tmp_path: Path) -> None:
    """Report output must be UTF-8 pretty-printed JSON with a single trailing newline."""
    out = tmp_path / "pick_report.json"
    _rebuild_and_run(out=out)
    raw = out.read_bytes()
    assert raw.endswith(b"\n")
    assert b"\r\n" not in raw
    text = raw.decode("utf-8")
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    assert "\n  " in text, "report must be pretty-printed"
    payload = json.loads(text)
    assert set(payload) == TOP_FIELDS


def test_balance_stamp_preimage_binds_output_fields() -> None:
    """balance_stamp must change when any bound output field changes."""
    base = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 150, "t1"),
    ]
    shifted_mark = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 100, "t1"),
        _pick("p2", "Z1", 2, 100, "t1"),
        _pick("p3", "Z1", 3, 100, "t1"),
        _pick("p4", "Z1", 4, 100, "t1"),
    ]
    base_stamp = _reference_report(base)["balance_stamp"]
    mark_stamp = _reference_report(shifted_mark)["balance_stamp"]
    assert base_stamp != mark_stamp
    assert _run_scenario(base)["balance_stamp"] == base_stamp
    assert _run_scenario(shifted_mark)["balance_stamp"] == mark_stamp


def test_checkpoint_rejects_stale_last_event_position_on_extended_input() -> None:
    """Shorter-input last_event_position must not alter cold replay on extended input."""
    base = _checkpoint_base_rows()
    extended = base + [_supersede("p1", 1, "void")]
    with tempfile.TemporaryDirectory() as tmp:
        base_inp = _scratch_path(Path(tmp), "base", "jsonl")
        ext_inp = _scratch_path(Path(tmp), "ext", "jsonl")
        ckpt = _scratch_path(Path(tmp), "ckpt")
        stale_out = _scratch_path(Path(tmp), "stale")
        _write_feed(base_inp, base)
        proc = _rebuild_and_run(base_inp, checkpoint_out=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        _write_feed(ext_inp, extended)
        proc = _rebuild_and_run(ext_inp, stale_out, checkpoint_in=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        stale = json.loads(stale_out.read_text())
        _assert_cold_fallback_report(stale, _reference_report(extended))


def test_checkpoint_rejects_malformed_last_event_position() -> None:
    """Malformed last_event_position must force cold replay on the same input bytes."""
    rows = _checkpoint_base_rows()
    expected = _reference_report(rows)

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        payload["last_event_position"] = "stale"

    with tempfile.TemporaryDirectory() as tmp:
        inp = _scratch_path(Path(tmp), "feed", "jsonl")
        warm_out = _scratch_path(Path(tmp), "warm")
        ckpt = _scratch_path(Path(tmp), "ckpt")
        _write_feed(inp, rows)
        proc = _rebuild_and_run(inp, checkpoint_out=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        payload = json.loads(ckpt.read_text(encoding="utf-8"))
        mutate(payload, inp, rows)
        ckpt.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        proc = _rebuild_and_run(inp, warm_out, checkpoint_in=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        warm = json.loads(warm_out.read_text(encoding="utf-8"))
        _assert_cold_fallback_report(warm, expected)


def test_checkpoint_rejects_missing_previous_stamp_seed() -> None:
    """Missing previous_stamp_seed must force cold replay on the same input bytes."""
    rows = _checkpoint_base_rows()
    expected = _reference_report(rows)

    def mutate(payload: dict, _inp: Path, _rows: list[dict]) -> None:
        payload.pop("previous_stamp_seed", None)

    with tempfile.TemporaryDirectory() as tmp:
        inp = _scratch_path(Path(tmp), "feed", "jsonl")
        warm_out = _scratch_path(Path(tmp), "warm")
        ckpt = _scratch_path(Path(tmp), "ckpt")
        _write_feed(inp, rows)
        proc = _rebuild_and_run(inp, checkpoint_out=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        payload = json.loads(ckpt.read_text(encoding="utf-8"))
        mutate(payload, inp, rows)
        ckpt.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        proc = _rebuild_and_run(inp, warm_out, checkpoint_in=ckpt)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        warm = json.loads(warm_out.read_text(encoding="utf-8"))
        _assert_cold_fallback_report(warm, expected)


def test_supersede_lineage_stamps_only_earliest_equal_generation_winner() -> None:
    """Equal-generation supersede ties must stamp only the first winning input row."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 500, "t1"),
        _supersede("p1", 5, "replace", 100),
        _supersede("p1", 5, "replace", 100),
    ]
    _, _, supersedes, _ = _split_feed(rows)
    picks, tares, _, _ = _split_feed(rows)
    baseline = _baseline_kept(picks, tares)
    winners = _supersede_winners(supersedes, baseline)
    lineage = _supersede_lineage(supersedes, winners)
    assert lineage.count(";") == 0
    assert len(lineage.split("|")) == 4
    assert _run_scenario(rows) == _reference_report(rows)


def test_spoilage_lineage_stamps_only_earliest_equal_generation_winner() -> None:
    """Equal-generation spoilage ties must stamp only the first winning input row."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, 150, "t1"),
        _spoilage("p1", 4),
        _spoilage("p1", 4),
    ]
    picks, tares, _, spoilages = _split_feed(rows)
    baseline = _baseline_kept(picks, tares)
    winners = _spoilage_winners(spoilages, baseline)
    lineage = _spoilage_lineage(spoilages, winners)
    assert lineage.count(";") == 0
    assert _run_scenario(rows) == _reference_report(rows)


def test_effective_net_rejects_gross_above_i64_max() -> None:
    """Gross grams above i64::MAX must refuse via checked promotion, not wrap."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, 0),
        _pick("p1", "Z1", 1, _I64_MAX + 1, "t1"),
    ]
    expected = _reference_report(rows)
    zone = expected["zones"][0]
    assert zone["net_refused"] == 1
    assert zone["net_kept_g"] == 0
    assert _run_scenario(rows) == expected


def test_effective_net_accepts_promoted_i64_max_with_offset() -> None:
    """Gross at i64::MAX must combine with offset using checked promotion."""
    rows = [
        _tare("t1", "Z1", 1, 1, 20, -(_I64_MAX - 100)),
        _pick("p1", "Z1", 1, _I64_MAX, "t1"),
    ]
    expected = _reference_report(rows)
    zone = expected["zones"][0]
    assert zone["net_kept_g"] == 100
    assert zone["net_refused"] == 0
    assert _run_scenario(rows) == expected


def _generated_dynamic_rows() -> list[dict]:
    zones = ["Qx7-north", "row-1", "ROW-1"]
    profile_ids = ["crate-alpha", "crate-beta", "crate-gamma"]
    rows: list[dict] = [
        _tare(profile_ids[0], zones[0], 2, 1, 100, -15, status="active"),
        _tare(profile_ids[0], zones[0], 10, 1, 100, 40, status="revoked"),
        _tare(profile_ids[0], zones[0], 3, 1, 100, 5, status="active"),
        _tare(profile_ids[1], zones[1], 1, 1, 50, 0, status="active"),
        _tare(profile_ids[2], zones[2], 1, 1, 50, -2, status="active"),
    ]
    rows.extend(
        [
            _pick("crate-001", zones[0], 1, 210, profile_ids[0]),
            _pick("crate-002", zones[1], 2, 199, profile_ids[1]),
            _pick("crate-003", zones[2], 3, 852, profile_ids[2]),
            _pick("crate-004", zones[0], 10, 140, profile_ids[0]),
            _pick("crate-005", zones[1], 4, 250, profile_ids[1]),
        ]
    )
    rows.extend(
        [
            _supersede("crate-005", 2, "replace", 201),
            _supersede("crate-005", 10, "void"),
            _spoilage("crate-002", 1),
            _spoilage("crate-004", 2),
            _spoilage("crate-004", 10),
        ]
    )
    return rows


def test_dynamic_generated_scenario_matches_reference() -> None:
    """Unfamiliar generated fixture must match the independent reference model."""
    rows = _generated_dynamic_rows()
    expected = _reference_report(rows)
    observed = _run_scenario(rows)
    assert observed == expected
    labels = [z["zone"] for z in observed["zones"]]
    assert labels == _zone_order([r for r in rows if r["kind"] == "pick"])
