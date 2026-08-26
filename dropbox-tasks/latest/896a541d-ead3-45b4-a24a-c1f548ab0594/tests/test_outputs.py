"""Verifier for timeline resume report output."""

import json
import re
import shutil
import subprocess
from pathlib import Path

OUTPUT = Path("/app/output/timeline_resume_report.json")
MATERIAL = Path("/app/svc-state/replay_material")
CHECKPOINT = Path("/app/svc-state/checkpoint/epoch.json")
HANDOFF = Path("/app/state/handoff")
ENV = Path("/app/environment")

SCENARIOS = ["warm_lane", "clock_step", "catalog_c", "journal_batch", "bind_mount"]
REPLAY_ORDER = ["warm_lane", "clock_step", "journal_batch", "catalog_c", "bind_mount"]


def _swap_sh(path: Path, body: str):
    original = path.read_text(encoding="utf-8")
    path.write_text(body, encoding="utf-8")
    return path, original


def _restore_sh(path: Path, original: str) -> None:
    path.write_text(original, encoding="utf-8")


def _sha256_hex(raw: str) -> str:
    proc = subprocess.run(
        ["openssl", "dgst", "-sha256", "-hex"],
        input=raw.encode("utf-8"),
        capture_output=True,
        check=True,
        text=False,
    )
    return proc.stdout.decode("utf-8").strip().split()[-1]


def _canonical_digest(runs: list[dict]) -> str:
    raw = json.dumps(runs, separators=(",", ":"), sort_keys=True)
    return _sha256_hex(raw)


def _row_tag(name: str, label_pick: str, pre_id: int, post_id: int, wal_cursor: int, scope: int) -> str:
    return _sha256_hex(f"{name}:{label_pick}:{pre_id}:{post_id}:{wal_cursor}:{scope}")


def _build() -> None:
    subprocess.run(["bash", "/app/environment/scripts/build.sh"], check=True)


def _replay() -> None:
    subprocess.run(["bash", "/app/environment/scripts/replay_exec.sh"], check=True)


def _emit() -> dict:
    subprocess.run(["bash", "/app/environment/scripts/emit_exec.sh"], check=True)
    return json.loads(OUTPUT.read_text(encoding="utf-8"))


def _reset_output() -> None:
    if OUTPUT.exists():
        OUTPUT.unlink()


def _reset_state() -> None:
    for path in (MATERIAL, HANDOFF):
        if path.exists():
            shutil.rmtree(path)
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)


def _reset_all() -> None:
    _reset_output()
    _reset_state()


def _pipeline() -> dict:
    _reset_all()
    _build()
    _replay()
    return _emit()


def _swap_go(path: Path, body: str):
    return _swap_sh(path, body)


def _restore_go(path: Path, original: str) -> None:
    _restore_sh(path, original)


def _row(report: dict, name: str) -> dict:
    for row in report["runs"]:
        if row["name"] == name:
            return row
    raise AssertionError(f"missing run row: {name}")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resume_policy() -> tuple[int, int]:
    body = (ENV / "config/resume_policy.toml").read_text(encoding="utf-8")
    stride = int(re.search(r"stride\s*=\s*([0-9]+)", body).group(1))
    sweep = int(re.search(r"sweep_epoch\s*=\s*([0-9]+)", body).group(1))
    return stride, sweep


def _quorum_min() -> int:
    body = (ENV / "config/view_policy.toml").read_text(encoding="utf-8")
    return int(re.search(r"quorum_min\s*=\s*([0-9]+)", body).group(1))


def _scan_list_head(lines: list[str], locale: str) -> int:
    newest = 0
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if locale == "c":
            fields = line.split(";")
        else:
            fields = line.split()
        for field in fields:
            try:
                val = int(field.strip())
            except ValueError:
                continue
            if val > newest:
                newest = val
    return newest


def _choose_label(labels: list[dict]) -> dict:
    if not labels:
        return {"text": "", "epoch": 0}
    chosen = labels[0]
    for row in labels[1:]:
        if row["text"] > chosen["text"]:
            chosen = row
        if row["text"] == chosen["text"] and row["epoch"] > chosen["epoch"]:
            chosen = row
    return chosen


def _merge_segments(trace: dict, *, by_seq: bool) -> list[dict]:
    segs = list(trace.get("wal_segments") or [])
    if by_seq:
        return sorted(segs, key=lambda s: s["seq"])
    return sorted(segs, key=lambda s: s["file_name"])


def _handoff_journal(stepback_latched: int) -> dict:
    return {"anchor_epoch": 0, "stepback_latched": stepback_latched}


def _expected_label_pick(trace: dict) -> str:
    segs = _merge_segments(trace, by_seq=True)
    last = None
    for seg in segs:
        ov = seg.get("override") or {}
        if ov.get("text"):
            last = ov
    if last:
        return last["text"]
    return _choose_label(trace.get("labels") or [])["text"]


def _expected_ids(trace: dict, ledger: dict, stepback_latched: int) -> tuple[int, int]:
    stride, sweep = _resume_policy()
    pre = trace["automation"]["pre_raw"]
    post = trace["automation"]["post_raw"]
    if ledger["retention_epoch"] >= sweep and stepback_latched == 1:
        if pre >= stride:
            pre -= stride
        if post >= stride:
            post -= stride
    if trace.get("list_file"):
        lines = (ENV / trace["list_file"]).read_text(encoding="utf-8").splitlines()
        head = _scan_list_head(lines, trace.get("locale", "host"))
        if head > 0:
            pre = head
    return pre, post


def _expected_wal_cursor(trace: dict) -> int:
    segs = trace.get("wal_segments") or []
    if not segs:
        return 0
    return max(seg["seq"] for seg in segs)


def _expected_scope(trace: dict) -> int:
    target = trace["target"]["path"]
    quorum = _quorum_min()
    matches = sum(1 for view in trace["views"] if view["path"] == target)
    return 1 if matches >= quorum else 0


def _stepback_before(name: str) -> int:
    if name not in REPLAY_ORDER:
        return 0
    latched = 0
    for run_id in REPLAY_ORDER:
        if run_id == name:
            break
        trace = _load_json(ENV / f"traces/{run_id}.trace")
        if trace.get("stepback_event", 0) > 0:
            latched = 1
    return latched


def _expected_row(name: str) -> dict:
    catalog = (ENV / "config/scenario_catalog.toml").read_text(encoding="utf-8")
    names = re.findall(r'name\s*=\s*"([^"]+)"', catalog)
    ledgers = re.findall(r'ledger\s*=\s*"([^"]+)"', catalog)
    traces = re.findall(r'trace\s*=\s*"([^"]+)"', catalog)
    idx = names.index(name)
    trace = _load_json(ENV / traces[idx])
    ledger = _load_json(ENV / ledgers[idx])
    segs = _merge_segments(trace, by_seq=True)
    last = None
    for seg in segs:
        ov = seg.get("override") or {}
        if ov.get("text"):
            last = ov
    if last:
        label_pick = last["text"]
        label_epoch = last["epoch"]
    else:
        chosen = _choose_label(trace.get("labels") or [])
        label_pick = chosen["text"]
        label_epoch = chosen["epoch"]
    stepback = _stepback_before(name)
    pre_id, post_id = _expected_ids(trace, ledger, stepback)
    wal_cursor = _expected_wal_cursor(trace)
    scope = _expected_scope(trace)
    return {
        "name": name,
        "label_pick": label_pick,
        "label_epoch": label_epoch,
        "pre_id": pre_id,
        "post_id": post_id,
        "wal_cursor": wal_cursor,
        "scope_visible": scope,
        "row_tag": _row_tag(name, label_pick, pre_id, post_id, wal_cursor, scope),
    }


def test_schema_and_digest() -> None:
    """Output schema and digest formatting per resume_contract.md."""
    report = _pipeline()
    assert report["resume_digest"] == report["timeline_hash"]
    assert report["resume_digest"] == _canonical_digest(report["runs"])
    for row in report["runs"]:
        assert set(row.keys()) == {
            "name",
            "label_pick",
            "label_epoch",
            "pre_id",
            "post_id",
            "wal_cursor",
            "scope_visible",
            "row_tag",
            "provenance",
        }


def test_warm_lane_rebuilds_stale_seed() -> None:
    """Stale seeded material for warm_lane must rebuild under correct checkpoint rules."""
    report = _pipeline()
    exp = _expected_row("warm_lane")
    row = _row(report, "warm_lane")
    assert row["label_pick"] == exp["label_pick"]
    assert row["pre_id"] == exp["pre_id"]
    assert row["post_id"] == exp["post_id"]


def test_clock_step_epoch_tie() -> None:
    """Colliding timeline text keeps the higher epoch on clock_step."""
    report = _pipeline()
    exp = _expected_row("clock_step")
    row = _row(report, "clock_step")
    assert row["label_pick"] == exp["label_pick"]
    assert row["label_epoch"] == exp["label_epoch"]
    assert row["pre_id"] == exp["pre_id"]
    assert row["post_id"] == exp["post_id"]


def test_catalog_c_locale_sample() -> None:
    """Locale c catalog sample yields the semicolon-separated newest id."""
    report = _pipeline()
    row = _row(report, "catalog_c")
    exp = _expected_row("catalog_c")
    assert row["pre_id"] == exp["pre_id"]


def test_journal_batch_order_and_recycle() -> None:
    """Journal override dominance follows segment sequence and stride recycle after stepback latch."""
    report = _pipeline()
    row = _row(report, "journal_batch")
    exp = _expected_row("journal_batch")
    assert row["label_pick"] == exp["label_pick"]
    assert row["wal_cursor"] == exp["wal_cursor"]
    assert row["pre_id"] == exp["pre_id"]
    assert row["post_id"] == exp["post_id"]


def test_bind_mount_visibility() -> None:
    """Scope visibility needs agreement across enough mount views, not a single alias."""
    report = _pipeline()
    row = _row(report, "bind_mount")
    assert row["scope_visible"] == _expected_row("bind_mount")["scope_visible"]


def test_idempotent_emit() -> None:
    """Repeated emit yields identical digests."""
    first = _pipeline()
    digest = first["resume_digest"]
    second = _emit()
    assert second["resume_digest"] == digest


def test_delete_output_regenerates() -> None:
    """Deleting output and re-emitting rebuilds from replay material."""
    report = _pipeline()
    empty = _canonical_digest([])
    bogus = {
        "runs": [],
        "resume_digest": empty,
        "timeline_hash": empty,
        "epoch_notes": ["epoch placeholder"],
    }
    OUTPUT.write_text(json.dumps(bogus) + "\n", encoding="utf-8")
    rebuilt = _emit()
    assert rebuilt["resume_digest"] == report["resume_digest"]
    assert len(rebuilt["runs"]) == len(SCENARIOS)


def test_checkpoint_drift_forces_rebuild() -> None:
    """Stale checkpoint stamp must not keep corrupted material."""
    report = _pipeline()
    path = MATERIAL / "journal_batch.json"
    material = _load_json(path)
    material["label_pick"] = "corrupt"
    path.write_text(json.dumps(material) + "\n", encoding="utf-8")
    CHECKPOINT.write_text(
        json.dumps({"ledger_epoch": 1, "material_seq": 4, "handoff_gen": 4}) + "\n",
        encoding="utf-8",
    )
    _replay()
    rebuilt = _emit()
    assert _row(rebuilt, "journal_batch")["label_pick"] == _row(report, "journal_batch")["label_pick"]


def test_handoff_drift_delayed_rebuild() -> None:
    """Wrong handoff in checkpoint must rebuild catalog_c after warm restart drift."""
    report = _pipeline()
    path = MATERIAL / "catalog_c.json"
    material = _load_json(path)
    material["pre_id"] = 0
    path.write_text(json.dumps(material) + "\n", encoding="utf-8")
    ledger = _load_json(ENV / "ledgers/gen-003.snapshot.json")
    CHECKPOINT.write_text(
        json.dumps(
            {
                "ledger_epoch": ledger["epoch"],
                "material_seq": ledger["generation"],
                "handoff_gen": ledger["generation"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _replay()
    rebuilt = _emit()
    assert _row(rebuilt, "catalog_c")["pre_id"] == _row(report, "catalog_c")["pre_id"]


def test_rerun_after_material_wipe() -> None:
    """Full material wipe followed by replay converges."""
    first = _pipeline()
    shutil.rmtree(MATERIAL)
    _replay()
    second = _emit()
    assert second["resume_digest"] == first["resume_digest"]


def test_handoff_journal_persisted() -> None:
    """Replay persists handoff journal with stepback latch after clock_step."""
    _pipeline()
    journal = _load_json(HANDOFF / "journal.json")
    assert journal["stepback_latched"] == 1


def test_replay_order_differs_from_catalog() -> None:
    """journal_batch observes stepback carry-forward only when replay order is honored."""
    report = _pipeline()
    row = _row(report, "journal_batch")
    exp = _expected_row("journal_batch")
    assert row["pre_id"] == exp["pre_id"]
    assert row["post_id"] == exp["post_id"]


def test_epoch_notes_present() -> None:
    """Preservation notes document epoch handling per scenario."""
    report = _pipeline()
    assert len(report["epoch_notes"]) == len(SCENARIOS)
    assert all("epoch" in note for note in report["epoch_notes"])


def test_provenance_multi_source() -> None:
    """Rows list multiple authority sources."""
    report = _pipeline()
    row = _row(report, "warm_lane")
    assert len(row["provenance"]) >= 2


def test_partial_revert_stamp_plane() -> None:
    """Broken checkpoint stamp alone keeps stale seeded warm_lane material."""
    path, original = _swap_sh(
        ENV / "u0_a/warm_gate.sh",
        """#!/usr/bin/env bash
source /app/environment/scripts/s0.sh
source /app/environment/u0_a/stamp_lane.sh
stamp_fresh() { return 0; }
""",
    )
    try:
        _reset_state()
        shutil.copytree(ENV / "svc-state-seed/replay_material", MATERIAL)
        CHECKPOINT.write_text(
            (ENV / "svc-state-seed/checkpoint/epoch.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        _replay()
        report = _emit()
        assert _row(report, "warm_lane")["label_pick"] != _expected_row("warm_lane")["label_pick"]
    finally:
        _restore_sh(path, original)


def test_partial_revert_journal_plane() -> None:
    """Filename journal merge alone chooses the wrong override text."""
    path, original = _swap_sh(
        ENV / "u1_b/wal_fold.sh",
        """#!/usr/bin/env bash
source /app/environment/scripts/s0.sh
wal_override_label() {
  local trace_file="$1"
  local best_text="" best_epoch=0 best_fname="" cursor=0
  while IFS= read -r seg; do
    [[ -z "$seg" ]] && continue
    local fname seq text epoch
    fname=$(jq -r '.file_name' <<<"$seg")
    seq=$(jq -r '.seq' <<<"$seg")
    text=$(jq -r '.override.text // empty' <<<"$seg")
    epoch=$(jq -r '.override.epoch // 0' <<<"$seg")
    if (( seq > cursor )); then cursor=$seq; fi
    if [[ -n "$text" && ( -z "$best_fname" || "$fname" < "$best_fname" ) ]]; then
      best_fname=$fname
      best_text=$text
      best_epoch=$epoch
    fi
  done < <(jq -c '.wal_segments[]?' "$trace_file" 2>/dev/null || true)
  WAL_CURSOR=$cursor
  WAL_OVERRIDE_TEXT=$best_text
  WAL_OVERRIDE_EPOCH=$best_epoch
  WAL_HAS_OVERRIDE=0
  if [[ -n "$best_text" ]]; then
    WAL_HAS_OVERRIDE=1
  fi
}
""",
    )
    try:
        report = _pipeline()
        assert _row(report, "journal_batch")["label_pick"] != _expected_row("journal_batch")["label_pick"]
    finally:
        _restore_sh(path, original)


def test_partial_revert_label_plane() -> None:
    """Broken timeline choice alone keeps the lower epoch on clock_step."""
    path, original = _swap_sh(
        ENV / "u2_c/label_lane.sh",
        """#!/usr/bin/env bash
source /app/environment/scripts/s0.sh
pick_label_rows() {
  local trace_file="$1"
  local best_text="" best_epoch=999999
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    local text epoch
    text=$(jq -r '.text' <<<"$row")
    epoch=$(jq -r '.epoch' <<<"$row")
    if [[ -z "$best_text" || "$text" > "$best_text" ]]; then
      best_text=$text
      best_epoch=$epoch
    elif [[ "$text" == "$best_text" && "$epoch" -lt "$best_epoch" ]]; then
      best_epoch=$epoch
    fi
  done < <(jq -c '.labels[]?' "$trace_file" 2>/dev/null || true)
  LABEL_PICK=$best_text
  LABEL_EPOCH=$best_epoch
}
""",
    )
    try:
        report = _pipeline()
        row = _row(report, "clock_step")
        assert row["label_epoch"] != _expected_row("clock_step")["label_epoch"]
    finally:
        _restore_sh(path, original)


def test_partial_revert_locale_plane() -> None:
    """Whitespace-only catalog reader alone misses locale c delimiter rows."""
    path, original = _swap_sh(
        ENV / "u2_c/list_lane.sh",
        """#!/usr/bin/env bash
source /app/environment/scripts/s0.sh
list_head_id() {
  local list_path="$1"
  local newest=0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line=${line%%#*}
    line=$(echo "$line" | xargs)
    [[ -z "$line" ]] && continue
    local first
    first=$(echo "$line" | awk '{print $1}')
    if [[ "$first" =~ ^[0-9]+$ ]] && (( first > newest )); then
      newest=$first
    fi
  done <"$list_path"
  LIST_HEAD_ID=$newest
}
""",
    )
    try:
        report = _pipeline()
        assert _row(report, "catalog_c")["pre_id"] != _expected_row("catalog_c")["pre_id"]
    finally:
        _restore_sh(path, original)


def test_partial_revert_recycle_plane() -> None:
    """Skipping retention recycle alone leaves raw automation ids on journal_batch."""
    path, original = _swap_sh(
        ENV / "u2_c/recycle_lane.sh",
        """#!/usr/bin/env bash
source /app/environment/scripts/s0.sh
recycle_pair_ids() {
  RECYCLE_PRE=$1
  RECYCLE_POST=$2
}
""",
    )
    try:
        report = _pipeline()
        row = _row(report, "journal_batch")
        trace = _load_json(ENV / "traces/journal_batch.trace")
        assert row["pre_id"] == trace["automation"]["pre_raw"]
        assert row["post_id"] == trace["automation"]["post_raw"]
    finally:
        _restore_sh(path, original)


def test_partial_revert_vote_plane() -> None:
    """Single-view match alone marks visibility without agreement threshold."""
    path, original = _swap_sh(
        ENV / "u3_d/vote_lane.sh",
        """#!/usr/bin/env bash
source /app/environment/scripts/s0.sh
mount_scope_visible() {
  local trace_file="$1"
  local target
  target=$(json_field "$trace_file" target.path)
  while IFS= read -r view; do
    [[ -z "$view" ]] && continue
    path=$(jq -r '.path' <<<"$view")
    if [[ "$path" == "$target" ]]; then
      SCOPE_VISIBLE=1
      return
    fi
  done < <(jq -c '.views[]?' "$trace_file" 2>/dev/null || true)
  SCOPE_VISIBLE=0
}
""",
    )
    try:
        report = _pipeline()
        assert _row(report, "bind_mount")["scope_visible"] != _expected_row("bind_mount")["scope_visible"]
    finally:
        _restore_sh(path, original)

