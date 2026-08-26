import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path

import crc32c
import pytest

APP = Path("/app")
ENV = APP / "environment"
PROFILE_PATH = ENV / "configs" / "audit_profile.json"
REGION_PATH = ENV / "data" / "region_codes.txt"

BIN = APP / "bin" / "claimdocketaudit"
OUT = APP / "out"
REPORT = OUT / "claim_docket_audit.json"
STATE = APP / "var" / "claim_docket_audit_run.json"
PRACTICE = ENV / "fixtures" / "practice"
REGRESSION = ENV / "fixtures" / "regression"

REPORT_KEYS = frozenset(
    {
        "api_version",
        "epoch",
        "docket_files",
        "frame_count",
        "record_count",
        "retract_count",
        "distinct_account_count",
        "chain_root_sha256",
        "crc_failure_count",
        "anchor_skip_count",
        "duplicate_slot_drops",
        "transfer_amount_sum",
        "min_seq",
        "max_seq",
        "region_reject_count",
    }
)

REGRESSION_EPOCHS = {
    "transfer_void": 9,
}


def _chain_seq_width() -> int:
    if PROFILE_PATH.is_file():
        doc = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        return int(doc.get("chain_seq_width", 16))
    return 16


def _canonical_payload(payload: dict) -> str:
    kind = payload["kind"]
    if kind == "tombstone":
        slim = {
            "account": payload["account"],
            "kind": kind,
            "region": payload["region"],
            "seq": payload["seq"],
        }
        return json.dumps(slim, separators=(",", ":"), sort_keys=True)
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _link_step(prev: str, seq: int, payload: dict, *, width: int) -> str:
    token = f"{seq:0{width}d}:{_canonical_payload(payload)}"
    return hashlib.sha256((prev + ":" + token).encode()).hexdigest()


def _docket_fingerprint(names: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(names)).encode()).hexdigest()


def _load_checkpoint(docket_dir: Path, epoch: int, fingerprint: str) -> tuple[str, int]:
    mark = docket_dir / f"{docket_dir.name}.cdkmark"
    if not mark.is_file():
        return "0" * 64, 0
    doc = json.loads(mark.read_text(encoding="utf-8"))
    if doc.get("epoch") != epoch or doc.get("docket_fingerprint") != fingerprint:
        return "0" * 64, 0
    return doc["chain_tail_sha256"], int(doc.get("skip_through_seq", 0))


def _region_allowlist() -> set[str]:
    return {line.strip() for line in REGION_PATH.read_text().splitlines() if line.strip()}


def _region_gate_enabled() -> bool:
    if PROFILE_PATH.is_file():
        doc = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        return bool(doc.get("region_gate", True))
    return True


def _recompute_report(docket_dir: Path, epoch: int) -> dict:
    files = sorted(p.name for p in docket_dir.glob("*.cdk"))
    fingerprint = _docket_fingerprint(files)
    prev, skip_through = _load_checkpoint(docket_dir, epoch, fingerprint)
    allow = _region_allowlist()
    gate = _region_gate_enabled()
    width = _chain_seq_width()
    frame_count = 0
    crc_failures = 0
    anchor_skip_count = 0
    retract_count = 0
    duplicate_slot_drops = 0
    region_reject_count = 0
    active: dict[tuple[str, int], dict] = {}
    kept_seq: list[int] = []

    for name in files:
        blob = (docket_dir / name).read_bytes()
        off = 0
        while off < len(blob):
            if len(blob) - off < 26:
                break
            if blob[off : off + 4] != b"CDKT":
                break
            hdr_seq = int.from_bytes(blob[off + 10 : off + 18], "little")
            ep = int.from_bytes(blob[off + 6 : off + 10], "little")
            plen = int.from_bytes(blob[off + 18 : off + 22], "little")
            end = off + 22 + plen
            if end + 4 > len(blob):
                crc_failures += 1
                break
            want = int.from_bytes(blob[end : end + 4], "little")
            got = crc32c.crc32c(blob[off:end])
            if got != want:
                crc_failures += 1
                off = end + 4
                continue
            payload = json.loads(blob[off + 22 : end].decode("utf-8"))
            off = end + 4
            if ep != epoch:
                continue
            if hdr_seq <= skip_through:
                anchor_skip_count += 1
                continue
            frame_count += 1
            kept_seq.append(hdr_seq)
            prev = _link_step(prev, hdr_seq, payload, width=width)
            kind = payload.get("kind")
            if kind in ("upsert", "transfer"):
                region = payload.get("region", "")
                if gate and region not in allow:
                    region_reject_count += 1
                    continue
                slot = (payload["account"], int(payload["seq"]))
                replaces = int(payload.get("replaces_seq") or 0)
                if replaces:
                    active.pop((payload["account"], replaces), None)
                if slot in active:
                    duplicate_slot_drops += 1
                active[slot] = payload
            elif kind == "void":
                retract_count += 1
            elif kind == "tombstone":
                acct = payload["account"]
                for key in list(active):
                    if key[0] == acct:
                        del active[key]

    record_count = sum(1 for p in active.values() if p["kind"] in ("upsert", "transfer"))
    accounts = {p["account"] for p in active.values() if p["kind"] in ("upsert", "transfer")}
    transfer_amount_sum = sum(
        int(p.get("amount") or 0)
        for p in active.values()
        if p["kind"] in ("upsert", "transfer")
    )
    min_seq = min(kept_seq) if kept_seq else 0
    max_seq = max(kept_seq) if kept_seq else 0

    return {
        "api_version": 1,
        "epoch": epoch,
        "docket_files": files,
        "chain_root_sha256": prev,
        "frame_count": frame_count,
        "record_count": record_count,
        "retract_count": retract_count,
        "distinct_account_count": len(accounts),
        "crc_failure_count": crc_failures,
        "anchor_skip_count": anchor_skip_count,
        "duplicate_slot_drops": duplicate_slot_drops,
        "transfer_amount_sum": transfer_amount_sum,
        "min_seq": min_seq,
        "max_seq": max_seq,
        "region_reject_count": region_reject_count,
    }


def _encode_frame(epoch: int, seq: int, payload: dict) -> bytes:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    header = bytearray()
    header += b"CDKT"
    header += bytes([1])
    header += bytes([1 if payload["kind"] != "void" else 2])
    header += struct.pack("<I", epoch)
    header += struct.pack("<Q", seq)
    header += struct.pack("<I", len(body))
    frame = bytes(header) + body
    csum = crc32c.crc32c(frame)
    return frame + struct.pack("<I", csum)


def _binary_stale() -> bool:
    if not BIN.is_file():
        return True
    built_at = BIN.stat().st_mtime
    for path in ENV.rglob("*.go"):
        if path.stat().st_mtime > built_at:
            return True
    gomod = ENV / "go.mod"
    return gomod.is_file() and gomod.stat().st_mtime > built_at


def _ensure_binary_built() -> None:
    if not _binary_stale():
        return
    subprocess.run(
        ["bash", "-c", "cd /app/environment && go build -o /app/bin/claimdocketaudit /app/environment/cmd/claimdocketaudit"],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="session", autouse=True)
def _claim_docket_binary_built() -> None:
    _ensure_binary_built()


def _reset_out() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()


def _clear_run_state() -> None:
    if STATE.is_file():
        STATE.unlink()


def _write_poisoned_run_tail(chain_tail: str, epoch: int = 7) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "docket_fingerprint": "deadbeef" * 8,
        "epoch": epoch,
        "chain_tail": chain_tail,
    }
    STATE.write_text(json.dumps(doc), encoding="utf-8")


def _run_audit(docket_dir: Path, epoch: int, *, clear_state: bool = False) -> dict:
    if clear_state:
        _clear_run_state()
    _reset_out()
    proc = subprocess.run(
        [
            str(BIN),
            "audit",
            "--docket-dir",
            str(docket_dir),
            "--epoch",
            str(epoch),
            "--json-out",
            str(REPORT),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    raw = json.loads(REPORT.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), "report must be a JSON object at top level"
    assert "debug" not in raw, "report must not be wrapped in a debug envelope"
    return raw


def _assert_matches_contract(report: dict, docket_dir: Path, epoch: int) -> None:
    ref = _recompute_report(docket_dir, epoch)
    for key in REPORT_KEYS:
        assert report[key] == ref[key], key


def _regression_cases() -> list[tuple[str, Path, int]]:
    cases: list[tuple[str, Path, int]] = []
    for path in sorted(REGRESSION.iterdir()):
        if not path.is_dir():
            continue
        epoch = REGRESSION_EPOCHS.get(path.name, 7)
        cases.append((path.name, path, epoch))
    return cases


def test_practice_schema_and_contract() -> None:
    """Practice epoch 7 audit matches independent contract recomputation."""
    rep = _run_audit(PRACTICE, 7, clear_state=True)
    assert set(rep.keys()) == REPORT_KEYS
    assert rep["api_version"] == 1
    _assert_matches_contract(rep, PRACTICE, 7)


@pytest.mark.parametrize("case_name,docket_dir,epoch", _regression_cases())
def test_regression_corpus_matches_contract(
    case_name: str, docket_dir: Path, epoch: int
) -> None:
    """Each regression subdirectory satisfies the published claim docket contract."""
    rep = _run_audit(docket_dir, epoch, clear_state=True)
    _assert_matches_contract(rep, docket_dir, epoch)


def test_chain_and_settlement_share_filtered_stream() -> None:
    """frame_count must track the same filtered stream that feeds settlement."""
    for case_name, docket_dir, epoch in _regression_cases():
        rep = _run_audit(docket_dir, epoch, clear_state=True)
        ref = _recompute_report(docket_dir, epoch)
        assert rep["frame_count"] == ref["frame_count"], case_name
        assert rep["record_count"] == ref["record_count"], case_name
        assert rep["chain_root_sha256"] == ref["chain_root_sha256"], case_name
        assert rep["anchor_skip_count"] == ref["anchor_skip_count"], case_name


def test_three_pass_idempotency_same_directory() -> None:
    """Three consecutive audits of one directory yield identical reports."""
    _clear_run_state()
    first = _run_audit(PRACTICE, 7)
    second = _run_audit(PRACTICE, 7)
    third = _run_audit(PRACTICE, 7)
    assert first == second == third


def test_cross_directory_replay_sequence() -> None:
    """Persisted tail from practice must not skew a later regression directory."""
    _clear_run_state()
    _run_audit(PRACTICE, 7)
    _run_audit(REGRESSION / "epoch_mismatch", 7)
    rep = _run_audit(REGRESSION / "checkpoint_seed", 7)
    _assert_matches_contract(rep, REGRESSION / "checkpoint_seed", 7)


def test_poisoned_run_tail_does_not_seed_chain() -> None:
    """Persisted run tail must not override recomputation from shard bytes."""
    _write_poisoned_run_tail("f" * 64, epoch=7)
    rep = _run_audit(PRACTICE, 7)
    _assert_matches_contract(rep, PRACTICE, 7)


def test_persisted_state_records_matching_fingerprint() -> None:
    """Successful audits persist tail keyed by docket fingerprint and epoch."""
    _clear_run_state()
    rep = _run_audit(PRACTICE, 7)
    assert STATE.is_file()
    doc = json.loads(STATE.read_text(encoding="utf-8"))
    names = sorted(p.name for p in PRACTICE.glob("*.cdk"))
    assert doc["docket_fingerprint"] == _docket_fingerprint(names)
    assert doc["epoch"] == 7
    assert doc["chain_tail"] == rep["chain_root_sha256"]


def test_runtime_dup_slot_last_row_wins() -> None:
    """Duplicate account+seq in one shard keeps last settlement row; both chain."""
    with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
        spool = Path(tmp)
        shard = spool / "lane.cdk"
        frames = [
            _encode_frame(
                7, 1, {"account": "X", "amount": 1, "kind": "upsert", "region": "west", "seq": 1}
            ),
            _encode_frame(
                7, 1, {"account": "X", "amount": 9, "kind": "upsert", "region": "west", "seq": 1}
            ),
        ]
        shard.write_bytes(b"".join(frames))
        rep = _run_audit(spool, 7, clear_state=True)
        _assert_matches_contract(rep, spool, 7)
        assert rep["duplicate_slot_drops"] == 1


def test_runtime_trunc_tail_counts_failure_and_stops_shard() -> None:
    """Truncated tail frame counts as CRC failure without aborting later shards."""
    with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
        spool = Path(tmp)
        good = _encode_frame(
            7, 1, {"account": "T", "amount": 1, "kind": "upsert", "region": "west", "seq": 1}
        )
        truncated = bytearray(b"CDKT")
        truncated += bytes([1, 1])
        truncated += struct.pack("<I", 7)
        truncated += struct.pack("<Q", 99)
        truncated += struct.pack("<I", 500)
        truncated += bytes(4)
        (spool / "north.cdk").write_bytes(good + bytes(truncated))
        (spool / "south.cdk").write_bytes(
            _encode_frame(
                7, 2, {"account": "U", "amount": 2, "kind": "upsert", "region": "west", "seq": 2}
            )
        )
        rep = _run_audit(spool, 7, clear_state=True)
        _assert_matches_contract(rep, spool, 7)
        assert rep["crc_failure_count"] >= 1


def test_runtime_magic_gap_stops_without_fatal_error() -> None:
    """Non-CDKT bytes mid-shard stop that shard scan without failing the audit."""
    with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
        spool = Path(tmp)
        f1 = _encode_frame(
            7, 1, {"account": "G1", "amount": 1, "kind": "upsert", "region": "west", "seq": 1}
        )
        f2 = _encode_frame(
            7, 2, {"account": "G2", "amount": 2, "kind": "upsert", "region": "west", "seq": 2}
        )
        (spool / "gap.cdk").write_bytes(f1 + b"GARB" + f2)
        rep = _run_audit(spool, 7, clear_state=True)
        _assert_matches_contract(rep, spool, 7)


def test_transfer_amount_sum_uses_settled_active_rows_only() -> None:
    """transfer_amount_sum reflects final active rows after supersede and duplicate resolution."""
    with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
        spool = Path(tmp)
        shard = spool / "amounts.cdk"
        frames = [
            _encode_frame(
                7,
                1,
                {
                    "account": "A",
                    "amount": 100,
                    "kind": "upsert",
                    "region": "west",
                    "seq": 1,
                    "replaces_seq": 0,
                },
            ),
            _encode_frame(
                7,
                2,
                {
                    "account": "A",
                    "amount": 40,
                    "kind": "upsert",
                    "region": "west",
                    "seq": 2,
                    "replaces_seq": 1,
                },
            ),
            _encode_frame(
                7,
                2,
                {"account": "B", "amount": 5, "kind": "upsert", "region": "west", "seq": 2},
            ),
        ]
        shard.write_bytes(b"".join(frames))
        rep = _run_audit(spool, 7, clear_state=True)
        _assert_matches_contract(rep, spool, 7)
        assert rep["transfer_amount_sum"] == 45


def test_chain_seq_width_zero_pads_digest_links() -> None:
    """Digest link tokens must zero-pad header seq to chain_seq_width."""
    with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
        spool = Path(tmp)
        (spool / "pad.cdk").write_bytes(
            _encode_frame(
                7,
                12,
                {"account": "P", "amount": 1, "kind": "upsert", "region": "west", "seq": 1},
            )
        )
        rep = _run_audit(spool, 7, clear_state=True)
        _assert_matches_contract(rep, spool, 7)
        assert rep["min_seq"] == 12


def test_delayed_run_tail_poison_after_practice() -> None:
    """Persisted tail from an earlier directory must not seed digest on a later corpus."""
    _clear_run_state()
    _run_audit(PRACTICE, 7)
    rep = _run_audit(REGRESSION / "checkpoint_seed", 7)
    _assert_matches_contract(rep, REGRESSION / "checkpoint_seed", 7)


def test_checkpoint_filtered_settlement_excludes_skipped_rows() -> None:
    """Settlement counters must ignore frames dropped by checkpoint skip filtering."""
    rep = _run_audit(REGRESSION / "checkpoint_seed", 7, clear_state=True)
    ref = _recompute_report(REGRESSION / "checkpoint_seed", 7)
    assert rep["anchor_skip_count"] > 0
    assert rep["record_count"] == ref["record_count"]
    assert rep["min_seq"] == ref["min_seq"]
    assert rep["max_seq"] == ref["max_seq"]


def test_seq_span_covers_checkpoint_kept_frames() -> None:
    """min_seq and max_seq span header seq values kept after checkpoint filtering."""
    rep = _run_audit(REGRESSION / "checkpoint_seed", 7, clear_state=True)
    ref = _recompute_report(REGRESSION / "checkpoint_seed", 7)
    assert rep["min_seq"] == ref["min_seq"]
    assert rep["max_seq"] == ref["max_seq"]
    assert rep["anchor_skip_count"] > 0


def test_region_reject_count_tracks_chained_but_excluded_rows() -> None:
    """Foreign-region upserts stay in the chain but increment region_reject_count."""
    rep = _run_audit(REGRESSION / "region_excluded", 7, clear_state=True)
    ref = _recompute_report(REGRESSION / "region_excluded", 7)
    assert rep["region_reject_count"] == ref["region_reject_count"]
    assert rep["region_reject_count"] > 0
    assert rep["frame_count"] > rep["record_count"]


def test_perturbed_practice_bytes_change_chain_root() -> None:
    """Independent walk detects shard perturbation before restored audit passes."""
    alpha = PRACTICE / "alpha.cdk"
    backup = alpha.read_bytes()
    baseline = _recompute_report(PRACTICE, 7)["chain_root_sha256"]
    try:
        data = bytearray(backup)
        data[30] ^= 0x01
        alpha.write_bytes(data)
        perturbed = _recompute_report(PRACTICE, 7)["chain_root_sha256"]
        assert perturbed != baseline
    finally:
        alpha.write_bytes(backup)
    rep = _run_audit(PRACTICE, 7, clear_state=True)
    _assert_matches_contract(rep, PRACTICE, 7)


def test_hand_written_json_replaced_by_pipeline() -> None:
    """Stale hand-written JSON is replaced by a fresh audit run."""
    _reset_out()
    REPORT.write_text('{"api_version":1,"epoch":7}', encoding="utf-8")
    rep = _run_audit(PRACTICE, 7, clear_state=True)
    _assert_matches_contract(rep, PRACTICE, 7)


def test_stale_checkpoint_fingerprint_ignored() -> None:
    """Sidecar with mismatched docket fingerprint must not seed digest or skip prefix."""
    rep = _run_audit(REGRESSION / "stale_checkpoint", 7, clear_state=True)
    ref = _recompute_report(REGRESSION / "stale_checkpoint", 7)
    assert rep["chain_root_sha256"] == ref["chain_root_sha256"]
    assert rep["chain_root_sha256"] != "f" * 64


def test_malformed_run_state_ignored() -> None:
    """Corrupted persisted run state must not influence recomputation."""
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text("{not-json", encoding="utf-8")
    rep = _run_audit(PRACTICE, 7)
    _assert_matches_contract(rep, PRACTICE, 7)


def test_anchor_skip_counts_only_target_epoch() -> None:
    """Checkpoint skip tallies must not include frames from non-target epochs."""
    rep = _run_audit(REGRESSION / "epoch_mismatch", 7, clear_state=True)
    ref = _recompute_report(REGRESSION / "epoch_mismatch", 7)
    assert rep["anchor_skip_count"] == ref["anchor_skip_count"]


def test_dynamic_multi_shard_global_order() -> None:
    """Frames from later basenames follow earlier shards in the merged stream."""
    with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
        spool = Path(tmp)
        (spool / "alpha.cdk").write_bytes(
            _encode_frame(
                7, 1, {"account": "M", "amount": 1, "kind": "upsert", "region": "west", "seq": 1}
            )
        )
        (spool / "omega.cdk").write_bytes(
            _encode_frame(
                7,
                2,
                {
                    "account": "M",
                    "amount": 5,
                    "kind": "upsert",
                    "region": "west",
                    "seq": 2,
                    "replaces_seq": 1,
                },
            )
        )
        rep = _run_audit(spool, 7, clear_state=True)
        _assert_matches_contract(rep, spool, 7)
        assert rep["record_count"] == 1
        assert rep["transfer_amount_sum"] == 5


def test_digest_link_uses_header_seq_not_payload_seq() -> None:
    """Digest tokens must use header seq with width padding, not payload seq alone."""
    with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
        spool = Path(tmp)
        (spool / "hdr.cdk").write_bytes(
            _encode_frame(
                7,
                42,
                {"account": "H", "amount": 3, "kind": "upsert", "region": "west", "seq": 7},
            )
        )
        rep = _run_audit(spool, 7, clear_state=True)
        _assert_matches_contract(rep, spool, 7)
        assert rep["min_seq"] == 42
