import hashlib
import hmac as hmac_lib
import json
import os
import signal
import socket
import sqlite3
import struct
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import requests

APP = Path(os.getenv("CHAINAUDIT_APP_DIR", "/app"))
DB_PATH = Path(os.getenv("CHAINAUDIT_DB", str(APP / "data" / "chainaudit.db")))
NOW_FILE = Path(os.getenv("CHAINAUDIT_NOW_FILE", str(APP / "data" / "NOW.txt")))
OUT_DIR = Path(os.getenv("CHAINAUDIT_OUT_DIR", str(APP / "out")))
KMS_ADDR = os.getenv("CHAINAUDIT_KMS_ADDR", "http://127.0.0.1:8500")
KMS_LOG = Path(os.getenv("CHAINAUDIT_KMS_LOG", str(APP / "data" / "kms_access.log")))
GO_MOD_FLAG = os.getenv("CHAINAUDIT_GO_BUILD_MOD", "-mod=vendor")
BINARY_PATH = Path(os.getenv("CHAINAUDIT_TEST_BIN", "/tmp/chainaudit_test_bin"))
MOCKKMS_BIN = Path(os.getenv("CHAINAUDIT_MOCKKMS_BIN", "/usr/local/bin/mockkms"))
MOCKKMS_PID_FILE = Path(os.getenv("CHAINAUDIT_MOCKKMS_PID", "/var/run/mockkms.pid"))

# ---------------------------------------------------------------------------
# Independent oracle: canonical encoding, Merkle tree, tip chain, checkpoint
# signing. This is a from-scratch reimplementation from CHAINAUDIT-SPEC.md,
# not a port of the Go source -- it must agree with whatever the agent's
# rebuilt binary produces, not the other way around.
# ---------------------------------------------------------------------------

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"
GENESIS_PREFIX = b"\x02"
TIP_PREFIX = b"\x03"

V1 = 0x01
V2 = 0x02

TOMBSTONE_SENTINEL = hashlib.sha256(b"CHAINAUDIT-TOMBSTONE-SENTINEL-v1").digest()
assert len(TOMBSTONE_SENTINEL) == 32

# Reason precedence (CHAINAUDIT-SPEC.md Section 8.7): lower number wins when
# a stream trips more than one finding at once.
PRIORITY_TAMPERED_EVENT = 1
PRIORITY_TAMPERED_MERKLE_ROOT = 2
PRIORITY_TAMPERED_SIGNATURE = 3
PRIORITY_REVOKED_KEY = 4
PRIORITY_KMS_UNAVAILABLE = 5
PRIORITY_NONE = 6

REASON_FOR_PRIORITY = {
    PRIORITY_TAMPERED_EVENT: "tampered_event",
    PRIORITY_TAMPERED_MERKLE_ROOT: "tampered_merkle_root",
    PRIORITY_TAMPERED_SIGNATURE: "tampered_checkpoint_signature",
    PRIORITY_REVOKED_KEY: "revoked_key",
    PRIORITY_KMS_UNAVAILABLE: "kms_unavailable",
}

VERIFY_STREAM_KEYS = {
    "stream_id", "status", "event_count", "checkpoint_count", "chain_tip_hash",
    "first_bad_seq", "first_bad_batch", "reason", "revoked_key_ids",
}
COMPACT_STREAM_KEYS = {"stream_id", "batches_pruned", "batches_retained", "events_deleted", "chain_tip_hash"}

# Fixture streams that are already corrupt/revoked/unverifiable by design --
# off limits as exploit targets, since pointing at one proves nothing about
# the agent's own understanding of the attack surface.
FORBIDDEN_EXPLOIT_STREAMS = {
    "tampered-event-001", "tampered-event-002", "tampered-checkpoint-sig-001",
    "kms-revoked-001", "kms-revoked-002",
    "precedence-signature-over-revoked-001", "precedence-revoked-over-kms-unavailable-001",
    "kms-exhausted-001",
}


def be16(n):
    return struct.pack(">H", n)


def be64(n):
    return struct.pack(">Q", n & 0xFFFFFFFFFFFFFFFF)


def encoding_version(migrated_at, ts):
    if migrated_at is None:
        return V1
    return V2 if ts >= migrated_at else V1


def canonical_event(stream_id, migrated_at, seq, ts, event_type, payload, tombstone, legal_hold):
    ver = encoding_version(migrated_at, ts)
    sid = stream_id.encode()
    et = event_type.encode()
    buf = bytes([ver])
    buf += be16(len(sid)) + sid
    buf += be64(seq)
    buf += be64(ts)
    buf += be16(len(et)) + et
    if tombstone:
        buf += bytes([0x01]) + struct.pack(">I", 32) + TOMBSTONE_SENTINEL
    else:
        p = payload or b""
        buf += bytes([0x00]) + struct.pack(">I", len(p)) + p
    if ver == V2:
        buf += bytes([0x01 if legal_hold else 0x00])
    return buf


def leaf_hash(canonical):
    return hashlib.sha256(LEAF_PREFIX + canonical).digest()


def internal_hash(left, right):
    return hashlib.sha256(NODE_PREFIX + left + right).digest()


def merkle_root(leaves):
    n = len(leaves)
    if n == 0:
        raise ValueError("merkle_root called with no leaves -- caller likely queried an already-pruned batch")
    if n == 1:
        return leaves[0]
    k = 1
    while k * 2 < n:
        k *= 2
    return internal_hash(merkle_root(leaves[:k]), merkle_root(leaves[k:]))


def merkle_root_duplicate_last(leaves):
    """Bitcoin-style construction the spec explicitly rejects; used only to
    prove the fixture actually discriminates against it."""
    level = list(leaves)
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(internal_hash(left, right))
        level = nxt
    return level[0]


def merkle_root_no_domain(leaves):
    """Same recursion, but without domain-separation prefixes; used only to
    prove the fixture actually depends on domain separation."""
    n = len(leaves)
    if n == 1:
        return leaves[0]
    k = 1
    while k * 2 < n:
        k *= 2
    left = merkle_root_no_domain(leaves[:k])
    right = merkle_root_no_domain(leaves[k:])
    return hashlib.sha256(left + right).digest()


def genesis(stream_id):
    return hashlib.sha256(GENESIS_PREFIX + b"CHAINAUDIT-GENESIS-v1" + stream_id.encode()).digest()


def fold_checkpoint(prev_tip, batch_index, start_seq, end_seq, root, key_id):
    kb = key_id.encode()
    buf = TIP_PREFIX + prev_tip + be64(batch_index) + be64(start_seq) + be64(end_seq) + root + be16(len(kb)) + kb
    return hashlib.sha256(buf).digest()


def checkpoint_signing_bytes(stream_id, batch_index, start_seq, end_seq, root):
    sid = stream_id.encode()
    return b"CHAINAUDIT-CKPT-v1" + be16(len(sid)) + sid + be64(batch_index) + be64(start_seq) + be64(end_seq) + root


def overall_chain_tip(stream_reports):
    h = hashlib.sha256()
    for s in sorted(stream_reports, key=lambda s: s["stream_id"]):
        sid = s["stream_id"].encode()
        h.update(be16(len(sid)))
        h.update(sid)
        h.update(bytes.fromhex(s["chain_tip_hash"]))
    return h.hexdigest()


def fetch_kms_key(key_id, max_attempts=12):
    url = f"{KMS_ADDR}/v1/keys/{key_id}"
    last_status = None
    for attempt in range(max_attempts):
        resp = requests.get(url, timeout=5)
        last_status = resp.status_code
        if resp.status_code == 200:
            body = resp.json()
            return "active", bytes.fromhex(body["key_material_hex"])
        if resp.status_code == 410:
            return "revoked", None
        if resp.status_code == 429:
            time.sleep(0.05 * (attempt + 1))
            continue
        raise RuntimeError(f"kms: unexpected status {resp.status_code} for {key_id}")
    raise RuntimeError(f"kms: exhausted retries for {key_id}, last status {last_status}")


def oracle_verify_stream(conn, stream_row):
    stream_id = stream_row["stream_id"]
    migrated_at = stream_row["migrated_at"]
    events = stream_events(conn, stream_id)
    checkpoints = stream_checkpoints(conn, stream_id)
    events_by_seq = {e["seq"]: e for e in events}

    best = [PRIORITY_NONE]

    def consider(p):
        if p < best[0]:
            best[0] = p

    first_bad_seq = None
    first_bad_batch = None
    revoked_key_ids = []
    seen_revoked = set()

    for e in events:
        computed = leaf_hash(canonical_event(
            stream_id, migrated_at, e["seq"], e["ts"], e["event_type"], e["payload"], e["tombstone"], e["legal_hold"],
        ))
        if computed != e["leaf_hash"]:
            consider(PRIORITY_TAMPERED_EVENT)
            if first_bad_seq is None or e["seq"] < first_bad_seq:
                first_bad_seq = e["seq"]

    tip = genesis(stream_id)
    for cp in checkpoints:
        start, end = cp["start_seq"], cp["end_seq"]
        leaves = []
        have_all = True
        for seq in range(start, end + 1):
            ev = events_by_seq.get(seq)
            if ev is None:
                have_all = False
                break
            leaves.append(ev["leaf_hash"])

        if have_all:
            if merkle_root(leaves) != cp["merkle_root"]:
                consider(PRIORITY_TAMPERED_MERKLE_ROOT)
                if first_bad_batch is None or cp["batch_index"] < first_bad_batch:
                    first_bad_batch = cp["batch_index"]

        try:
            status, material = fetch_kms_key(cp["key_id"])
        except RuntimeError:
            consider(PRIORITY_KMS_UNAVAILABLE)
        else:
            if status == "revoked":
                consider(PRIORITY_REVOKED_KEY)
                if cp["key_id"] not in seen_revoked:
                    seen_revoked.add(cp["key_id"])
                    revoked_key_ids.append(cp["key_id"])
            else:
                signing_bytes = checkpoint_signing_bytes(stream_id, cp["batch_index"], start, end, cp["merkle_root"])
                expected_sig = hmac_lib.new(material, signing_bytes, hashlib.sha256).digest()
                if not hmac_lib.compare_digest(expected_sig, cp["signature"]):
                    consider(PRIORITY_TAMPERED_SIGNATURE)
                    if first_bad_batch is None or cp["batch_index"] < first_bad_batch:
                        first_bad_batch = cp["batch_index"]

        tip = fold_checkpoint(tip, cp["batch_index"], start, end, cp["merkle_root"], cp["key_id"])

    p = best[0]
    if p <= PRIORITY_TAMPERED_SIGNATURE:
        status_out = "corrupt"
        reason = REASON_FOR_PRIORITY[p]
    elif p <= PRIORITY_KMS_UNAVAILABLE:
        status_out = "legacy_unverifiable"
        reason = REASON_FOR_PRIORITY[p]
    else:
        status_out = "ok"
        reason = None

    return {
        "stream_id": stream_id,
        "status": status_out,
        "event_count": len(events),
        "checkpoint_count": len(checkpoints),
        "chain_tip_hash": tip.hex(),
        "first_bad_seq": first_bad_seq,
        "first_bad_batch": first_bad_batch,
        "reason": reason,
        "revoked_key_ids": sorted(revoked_key_ids),
    }


def oracle_compact_eligible_batches(conn, pre_events, stream_row, now):
    stream_id = stream_row["stream_id"]
    checkpoints = stream_checkpoints(conn, stream_id)
    cutoff = now - stream_row["retention_days"] * 86400

    eligible, retained = [], []
    for cp in checkpoints:
        if stream_row["legal_hold"]:
            retained.append(cp["batch_index"])
            continue
        ok = True
        for seq in range(cp["start_seq"], cp["end_seq"] + 1):
            ev = pre_events.get((stream_id, seq))
            if ev is None:
                continue
            if ev["legal_hold"] or ev["ts"] > cutoff:
                ok = False
                break
        (eligible if ok else retained).append(cp["batch_index"])
    return eligible, retained


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def all_streams(conn):
    return conn.execute("SELECT * FROM streams ORDER BY stream_id").fetchall()


def get_stream_row(conn, stream_id):
    row = conn.execute("SELECT * FROM streams WHERE stream_id=?", (stream_id,)).fetchone()
    assert row is not None, f"stream {stream_id} missing from database"
    return row


def stream_events(conn, stream_id):
    return conn.execute("SELECT * FROM events WHERE stream_id=? ORDER BY seq", (stream_id,)).fetchall()


def stream_checkpoints(conn, stream_id):
    return conn.execute("SELECT * FROM checkpoints WHERE stream_id=? ORDER BY batch_index", (stream_id,)).fetchall()


def find_stream(report, stream_id):
    for s in report["streams"]:
        if s["stream_id"] == stream_id:
            return s
    raise KeyError(f"stream {stream_id} not found in report")


def batch_fully_pruned(conn, stream_id, start_seq, end_seq):
    """Whether a batch's events are currently absent from the live database.

    Checked against live state rather than compact_1's batches_pruned delta:
    a correct solution may already have run compact once (e.g. solve.sh runs
    it as part of producing compact_manifest.json) before this test's own
    pipeline starts, in which case a batch pruned earlier legitimately won't
    appear in *this* run's batches_pruned even though pruning it was correct.
    """
    row = conn.execute(
        "SELECT COUNT(*) c FROM events WHERE stream_id=? AND seq BETWEEN ? AND ?",
        (stream_id, start_seq, end_seq),
    ).fetchone()
    return row["c"] == 0


def restart_mockkms():
    """Kill and relaunch mockkms so its in-memory per-key request counters
    reset to zero, and truncate its access log.

    Without this, a key's flaky-429 budget is consumed once, forever, for the
    lifetime of the container: if the agent (reasonably) ran `verify`
    themselves while developing their fix, or if a prior grading attempt
    already queried a given key, every key would already be resolved by the
    time this test session's own verify call runs, and the retry-evidence
    tests could pass even for a solution with no retry logic at all, purely
    from unrelated historical traffic sharing the log. Restarting guarantees
    any 429-then-resolved evidence in the log came from this session's own
    calls.
    """
    if MOCKKMS_PID_FILE.exists():
        try:
            pid = int(MOCKKMS_PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
        except (ValueError, ProcessLookupError, PermissionError):
            pass

    deadline = time.time() + 5
    while time.time() < deadline:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        try:
            s.connect(("127.0.0.1", 8500))
        except OSError:
            s.close()
            break
        else:
            s.close()
            time.sleep(0.1)

    KMS_LOG.parent.mkdir(parents=True, exist_ok=True)
    KMS_LOG.write_text("")

    proc = subprocess.Popen(
        [str(MOCKKMS_BIN)],
        env={**os.environ, "MOCKKMS_LOG": str(KMS_LOG)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    MOCKKMS_PID_FILE.write_text(str(proc.pid))

    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            r = requests.get(f"{KMS_ADDR}/healthz", timeout=0.5)
            if r.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.1)
    raise RuntimeError("mockkms did not become healthy after restart")


# ---------------------------------------------------------------------------
# Pipeline fixture: restart the KMS fresh, build once, run
# verify -> compact -> compact -> verify once per session, snapshotting
# pre-compact event data first since pruning deletes the only evidence needed
# to judge whether pruning was correct.
# ---------------------------------------------------------------------------

@dataclass
class Pipeline:
    binary: Path
    verify_before: dict
    compact_1: dict
    compact_2: dict
    verify_after: dict
    returncodes: dict
    kms_log: list
    pre_compact_events: dict = field(default_factory=dict)
    pre_compact_event_counts: dict = field(default_factory=dict)


@pytest.fixture(scope="session")
def pipeline():
    restart_mockkms()

    build_cmd = ["go", "build"]
    if GO_MOD_FLAG:
        build_cmd.append(GO_MOD_FLAG)
    build_cmd += ["-o", str(BINARY_PATH), "./cmd/chainaudit"]
    build = subprocess.run(build_cmd, cwd=str(APP), capture_output=True, text=True)
    assert build.returncode == 0, f"go build failed:\nstdout={build.stdout}\nstderr={build.stderr}"

    snap = sqlite3.connect(str(DB_PATH))
    snap.row_factory = sqlite3.Row
    pre_compact_events = {}
    for row in snap.execute("SELECT stream_id, seq, ts, legal_hold FROM events"):
        pre_compact_events[(row["stream_id"], row["seq"])] = {"ts": row["ts"], "legal_hold": row["legal_hold"]}
    pre_compact_event_counts = {}
    for row in snap.execute("SELECT stream_id, COUNT(*) AS n FROM events GROUP BY stream_id"):
        pre_compact_event_counts[row["stream_id"]] = row["n"]
    snap.close()

    returncodes = {}

    def run(name, *args):
        r = subprocess.run([str(BINARY_PATH), *args], cwd=str(APP), capture_output=True, text=True, timeout=180)
        returncodes[name] = r.returncode
        assert r.returncode == 0, f"{name} failed (exit {r.returncode}): stdout={r.stdout!r} stderr={r.stderr!r}"
        return r

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    baseline_path = OUT_DIR / "_baseline_verify_report.json"
    run("verify_before", "verify", "--db", str(DB_PATH), "--out", str(baseline_path), "--kms-addr", KMS_ADDR)
    verify_before = json.loads(baseline_path.read_text())

    manifest_path = OUT_DIR / "compact_manifest.json"
    run("compact_1", "compact", "--db", str(DB_PATH), "--out", str(manifest_path), "--now-file", str(NOW_FILE))
    compact_1 = json.loads(manifest_path.read_text())

    rerun_manifest_path = OUT_DIR / "_rerun_compact_manifest.json"
    run("compact_2", "compact", "--db", str(DB_PATH), "--out", str(rerun_manifest_path), "--now-file", str(NOW_FILE))
    compact_2 = json.loads(rerun_manifest_path.read_text())

    verify_report_path = OUT_DIR / "verify_report.json"
    run("verify_after", "verify", "--db", str(DB_PATH), "--out", str(verify_report_path), "--kms-addr", KMS_ADDR)
    verify_after = json.loads(verify_report_path.read_text())

    kms_log = []
    if KMS_LOG.exists():
        for line in KMS_LOG.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                kms_log.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    return Pipeline(
        binary=BINARY_PATH, verify_before=verify_before, compact_1=compact_1, compact_2=compact_2,
        verify_after=verify_after, returncodes=returncodes, kms_log=kms_log,
        pre_compact_events=pre_compact_events, pre_compact_event_counts=pre_compact_event_counts,
    )


@pytest.fixture(scope="session")
def conn(pipeline):
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def assert_matches_oracle(conn, report, stream_id, check_counts=True):
    stream_row = get_stream_row(conn, stream_id)
    expected = oracle_verify_stream(conn, stream_row)
    actual = find_stream(report, stream_id)
    assert actual["status"] == expected["status"], f"{stream_id}: status"
    assert actual["reason"] == expected["reason"], f"{stream_id}: reason"
    assert actual["first_bad_seq"] == expected["first_bad_seq"], f"{stream_id}: first_bad_seq"
    assert actual["first_bad_batch"] == expected["first_bad_batch"], f"{stream_id}: first_bad_batch"
    assert actual["revoked_key_ids"] == expected["revoked_key_ids"], (
        f"{stream_id}: revoked_key_ids must be in ascending lexical order (CHAINAUDIT-SPEC.md Section 13.1), "
        f"expected {expected['revoked_key_ids']}, got {actual['revoked_key_ids']}"
    )
    assert actual["chain_tip_hash"] == expected["chain_tip_hash"], f"{stream_id}: chain_tip_hash"
    if check_counts:
        assert actual["event_count"] == expected["event_count"], f"{stream_id}: event_count"
        assert actual["checkpoint_count"] == expected["checkpoint_count"], f"{stream_id}: checkpoint_count"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_binary_builds(pipeline):
    assert pipeline.binary.exists()
    assert os.access(pipeline.binary, os.X_OK)


def test_output_paths_and_exit_codes(pipeline):
    assert pipeline.returncodes["verify_before"] == 0
    assert pipeline.returncodes["compact_1"] == 0
    assert pipeline.returncodes["compact_2"] == 0
    assert pipeline.returncodes["verify_after"] == 0
    assert (OUT_DIR / "verify_report.json").exists()
    assert (OUT_DIR / "compact_manifest.json").exists()


def test_verify_report_schema(pipeline, conn):
    report = pipeline.verify_after
    assert set(report.keys()) == {"db_path", "chain_tip_hash_overall", "streams"}, (
        f"unexpected top-level verify_report.json fields: {set(report.keys())}"
    )
    assert isinstance(report["db_path"], str) and report["db_path"]
    assert isinstance(report["chain_tip_hash_overall"], str) and len(report["chain_tip_hash_overall"]) == 64
    int(report["chain_tip_hash_overall"], 16)
    assert isinstance(report["streams"], list)

    db_ids = {r["stream_id"] for r in all_streams(conn)}
    seen = set()
    for s in report["streams"]:
        assert set(s.keys()) == VERIFY_STREAM_KEYS, f"{s.get('stream_id')}: unexpected per-stream fields {set(s.keys())}"
        assert isinstance(s["stream_id"], str) and s["stream_id"]
        assert s["stream_id"] not in seen, f"duplicate stream {s['stream_id']} in verify report"
        seen.add(s["stream_id"])
        assert s["status"] in ("ok", "legacy_unverifiable", "corrupt")
        assert isinstance(s["event_count"], int) and s["event_count"] >= 0
        assert isinstance(s["checkpoint_count"], int) and s["checkpoint_count"] >= 0
        assert isinstance(s["chain_tip_hash"], str) and len(s["chain_tip_hash"]) == 64
        int(s["chain_tip_hash"], 16)
        assert s["first_bad_seq"] is None or isinstance(s["first_bad_seq"], int)
        assert s["first_bad_batch"] is None or isinstance(s["first_bad_batch"], int)
        assert s["reason"] is None or isinstance(s["reason"], str)
        assert isinstance(s["revoked_key_ids"], list)
        if s["status"] == "ok":
            assert s["reason"] is None and s["first_bad_seq"] is None and s["first_bad_batch"] is None
        if s["status"] == "corrupt":
            assert s["reason"] in ("tampered_event", "tampered_merkle_root", "tampered_checkpoint_signature", "kms_unavailable")
        if s["status"] == "legacy_unverifiable":
            assert s["reason"] in ("revoked_key", "kms_unavailable")
            if s["reason"] == "revoked_key":
                assert len(s["revoked_key_ids"]) > 0

    assert seen == db_ids, f"verify_report.json stream coverage mismatch: missing={db_ids - seen}, extra={seen - db_ids}"


def test_compact_manifest_schema(pipeline, conn):
    manifest = pipeline.compact_1
    assert set(manifest.keys()) == {"db_path", "now", "streams"}, f"unexpected top-level compact_manifest.json fields: {set(manifest.keys())}"
    assert isinstance(manifest["db_path"], str) and manifest["db_path"]
    assert isinstance(manifest["now"], int)
    assert manifest["now"] == int(NOW_FILE.read_text().strip())
    assert isinstance(manifest["streams"], list)

    db_ids = {r["stream_id"] for r in all_streams(conn)}
    seen = set()
    for s in manifest["streams"]:
        assert set(s.keys()) == COMPACT_STREAM_KEYS, f"{s.get('stream_id')}: unexpected per-stream fields {set(s.keys())}"
        assert isinstance(s["stream_id"], str) and s["stream_id"]
        seen.add(s["stream_id"])
        assert isinstance(s["batches_pruned"], list)
        assert isinstance(s["batches_retained"], list)
        assert set(s["batches_pruned"]).isdisjoint(s["batches_retained"]), s["stream_id"]
        assert isinstance(s["events_deleted"], int) and s["events_deleted"] >= 0
        assert isinstance(s["chain_tip_hash"], str) and len(s["chain_tip_hash"]) == 64
        int(s["chain_tip_hash"], 16)

    assert seen == db_ids, f"compact_manifest.json stream coverage mismatch: missing={db_ids - seen}, extra={seen - db_ids}"


def test_chain_tip_hash_overall_correct(pipeline):
    expected = overall_chain_tip(pipeline.verify_after["streams"])
    assert pipeline.verify_after["chain_tip_hash_overall"] == expected, (
        "chain_tip_hash_overall isn't the fold of every stream's own chain_tip_hash "
        "(sorted by stream_id) -- it must be recomputed, not copied from somewhere or left stale"
    )


def test_verify_report_streams_sorted_by_id(pipeline):
    ids = [s["stream_id"] for s in pipeline.verify_after["streams"]]
    assert ids == sorted(ids), "verify_report.json's streams array must be sorted by stream_id ascending (CHAINAUDIT-SPEC.md Section 13.1)"


def test_compact_manifest_streams_sorted_by_id(pipeline):
    ids = [s["stream_id"] for s in pipeline.compact_1["streams"]]
    assert ids == sorted(ids), "compact_manifest.json's streams array must be sorted by stream_id ascending"


def test_revoked_key_ids_sorted_not_just_encounter_order(pipeline, conn):
    # this stream's checkpoints are signed by revoked keys in an order that
    # is deliberately NOT lexically sorted -- collecting revoked_key_ids in
    # checkpoint/batch_index order without an explicit sort would report
    # them backwards.
    stream_id = "revoked-keys-reverse-order-001"
    assert_matches_oracle(conn, pipeline.verify_after, stream_id)
    actual = find_stream(pipeline.verify_after, stream_id)
    assert actual["status"] == "legacy_unverifiable"
    assert actual["revoked_key_ids"] == ["key-2022-11", "key-2023-05"], (
        f"revoked_key_ids must be in ascending lexical order regardless of which checkpoint encountered "
        f"each key first, got {actual['revoked_key_ids']}"
    )


def test_verify_clean_stream_ok(pipeline, conn):
    for stream_id in ("untouched-001", "untouched-002", "clean-bulk-001", "clean-bulk-002", "clean-bulk-010"):
        assert_matches_oracle(conn, pipeline.verify_after, stream_id)
        assert find_stream(pipeline.verify_after, stream_id)["status"] == "ok"


def test_verify_detects_tampered_event_hash(pipeline, conn):
    for stream_id, expected_seq in (("tampered-event-001", 10), ("tampered-event-002", 90)):
        assert_matches_oracle(conn, pipeline.verify_after, stream_id)
        actual = find_stream(pipeline.verify_after, stream_id)
        assert actual["status"] == "corrupt"
        assert actual["reason"] == "tampered_event"
        assert actual["first_bad_seq"] == expected_seq


def test_verify_detects_tampered_checkpoint_signature(pipeline, conn):
    assert_matches_oracle(conn, pipeline.verify_after, "tampered-checkpoint-sig-001")
    actual = find_stream(pipeline.verify_after, "tampered-checkpoint-sig-001")
    assert actual["status"] == "corrupt"
    assert actual["reason"] == "tampered_checkpoint_signature"
    assert actual["first_bad_batch"] == 1


def test_verify_revoked_key_not_corrupt(pipeline, conn):
    for stream_id in ("kms-revoked-001", "kms-revoked-002"):
        assert_matches_oracle(conn, pipeline.verify_after, stream_id)
        actual = find_stream(pipeline.verify_after, stream_id)
        assert actual["status"] == "legacy_unverifiable"
        assert actual["status"] != "corrupt"
        assert actual["reason"] == "revoked_key"
        assert len(actual["revoked_key_ids"]) > 0


def test_kms_exhausted_retries_classified_as_legacy_not_corrupt(pipeline, conn):
    assert_matches_oracle(conn, pipeline.verify_after, "kms-exhausted-001")
    actual = find_stream(pipeline.verify_after, "kms-exhausted-001")
    assert actual["status"] == "legacy_unverifiable", (
        "a KMS lookup that never resolves (exhausted retries) is not itself evidence of tampering -- "
        "it must be legacy_unverifiable, not corrupt"
    )
    assert actual["reason"] == "kms_unavailable"


def test_reason_precedence_signature_over_revoked(pipeline, conn):
    assert_matches_oracle(conn, pipeline.verify_after, "precedence-signature-over-revoked-001")
    actual = find_stream(pipeline.verify_after, "precedence-signature-over-revoked-001")
    assert actual["status"] == "corrupt"
    assert actual["reason"] == "tampered_checkpoint_signature", (
        "this stream has both a genuine signature mismatch on an active key AND a revoked key on a "
        "different batch -- the higher-precedence finding (signature tampering) must win the reported reason"
    )


def test_reason_precedence_revoked_over_kms_unavailable(pipeline, conn):
    assert_matches_oracle(conn, pipeline.verify_after, "precedence-revoked-over-kms-unavailable-001")
    actual = find_stream(pipeline.verify_after, "precedence-revoked-over-kms-unavailable-001")
    assert actual["status"] == "legacy_unverifiable"
    assert actual["reason"] == "revoked_key", (
        "this stream has both a revoked key AND a KMS lookup that never resolves on different batches -- "
        "revoked_key outranks kms_unavailable"
    )


def test_verify_kms_429_retries_succeed(pipeline):
    by_key = {}
    for e in pipeline.kms_log:
        by_key.setdefault(e["key_id"], []).append(e)

    saw_retry_then_resolved = False
    for entries in by_key.values():
        statuses = [e["status"] for e in sorted(entries, key=lambda e: e["ts"])]
        if 429 in statuses:
            first = statuses.index(429)
            if any(s in (200, 410) for s in statuses[first:]):
                saw_retry_then_resolved = True
    assert saw_retry_then_resolved, "no key_id shows a 429 eventually followed by a resolved (200/410) response"


def test_verify_kms_backoff_timing(pipeline):
    # key-2024-12-degraded is deliberately excluded: it never resolves, so it
    # gets a fresh independent retry sequence from every separate verify
    # invocation in this pipeline (verify_before, verify_after), and the gap
    # *between* two such invocations isn't governed by backoff at all -- only
    # the gap *within* one client's own retry loop is. The ordinary flaky
    # keys resolve permanently on their first retry sequence and are never
    # queried again, so they can't have this ambiguity.
    by_key = {}
    for e in pipeline.kms_log:
        if e["key_id"] == "key-2024-12-degraded":
            continue
        by_key.setdefault(e["key_id"], []).append(e)

    checked_any = False
    for key_id, entries in by_key.items():
        entries = sorted(entries, key=lambda e: e["ts"])
        for i in range(len(entries) - 1):
            if entries[i]["status"] == 429:
                gap_ms = entries[i + 1]["ts"] - entries[i]["ts"]
                checked_any = True
                assert gap_ms >= 15, (
                    f"retry for {key_id} followed a 429 after only {gap_ms}ms -- "
                    "expected real backoff, not a tight retry loop"
                )
    assert checked_any, "no 429 responses found in the KMS access log to check backoff timing against"


def test_verify_kms_giving_up_eventually(pipeline):
    by_key = {}
    for e in pipeline.kms_log:
        by_key.setdefault(e["key_id"], []).append(e)
    entries = by_key.get("key-2024-12-degraded", [])
    assert entries, "the permanently-throttled key was never queried"
    assert all(e["status"] == 429 for e in entries), "the permanently-throttled key should only ever answer 429"
    # This pipeline calls verify exactly twice (verify_before, verify_after),
    # each making its own independent retry attempt against this key since it
    # never resolves. Bounding the total across both, rather than trying to
    # split the log into per-invocation windows (which timing alone can't
    # reliably do when two runs' retry sequences butt up against each other),
    # still catches a client that retries without ever giving up.
    assert len(entries) <= 40, (
        f"{len(entries)} requests were made across this session for a key that only ever returns 429 -- "
        "expected a small, bounded retry budget with a clear give-up on each verify invocation, "
        "not an unbounded or tight retry loop"
    )


def test_kms_server_actually_used(pipeline):
    assert len(pipeline.kms_log) >= 20, "too few KMS access log entries for genuine per-checkpoint verification traffic"
    key_ids = {e["key_id"] for e in pipeline.kms_log}
    assert {"key-2022-11", "key-2023-05", "key-2024-02", "key-2024-11"} <= key_ids


def test_tombstone_not_flagged_corrupt(pipeline, conn):
    for stream_id in ("tombstone-001", "tombstone-002"):
        assert_matches_oracle(conn, pipeline.verify_after, stream_id)
        assert find_stream(pipeline.verify_after, stream_id)["status"] == "ok"


def test_tombstone_sentinel_hash_correct(conn):
    cases = {"tombstone-001": (5, 25, 45), "tombstone-002": (0, 39)}
    for stream_id, seqs in cases.items():
        stream_row = get_stream_row(conn, stream_id)
        events = {e["seq"]: e for e in stream_events(conn, stream_id)}
        for seq in seqs:
            e = events[seq]
            assert e["tombstone"] == 1
            assert e["payload"] is None
            canonical = canonical_event(
                stream_id, stream_row["migrated_at"], e["seq"], e["ts"], e["event_type"], e["payload"], e["tombstone"], e["legal_hold"],
            )
            assert leaf_hash(canonical) == e["leaf_hash"]
            wrong = canonical_event(
                stream_id, stream_row["migrated_at"], e["seq"], e["ts"], e["event_type"], b"", False, e["legal_hold"],
            )
            assert leaf_hash(wrong) != e["leaf_hash"], "sentinel substitution is not actually load-bearing in this fixture"


def test_v1_legacy_stream_encoding(pipeline, conn):
    for stream_id in ("v1-legacy-001", "v1-legacy-002"):
        stream_row = get_stream_row(conn, stream_id)
        assert stream_row["migrated_at"] is None
        assert_matches_oracle(conn, pipeline.verify_after, stream_id)
        assert find_stream(pipeline.verify_after, stream_id)["status"] == "ok"


def test_mixed_version_boundary_encoding(pipeline, conn):
    for stream_id, straddled_batch in (("migration-boundary-001", 1), ("migration-boundary-002", 0)):
        stream_row = get_stream_row(conn, stream_id)
        migrated_at = stream_row["migrated_at"]
        assert migrated_at is not None
        cp = next(c for c in stream_checkpoints(conn, stream_id) if c["batch_index"] == straddled_batch)
        events = [e for e in stream_events(conn, stream_id) if cp["start_seq"] <= e["seq"] <= cp["end_seq"]]
        versions = {encoding_version(migrated_at, e["ts"]) for e in events}
        assert versions == {V1, V2}, (
            f"{stream_id} batch {straddled_batch} was expected to straddle the migration boundary "
            f"(mix of v1 and v2 events) but only contains version(s) {versions}"
        )
        assert_matches_oracle(conn, pipeline.verify_after, stream_id)
        assert find_stream(pipeline.verify_after, stream_id)["status"] == "ok"


def test_merkle_domain_separation(conn):
    stream_id = "custom-interval-002"
    cp = stream_checkpoints(conn, stream_id)[0]
    events = [e for e in stream_events(conn, stream_id) if cp["start_seq"] <= e["seq"] <= cp["end_seq"]]
    leaves = [e["leaf_hash"] for e in events]
    correct = merkle_root(leaves)
    assert cp["merkle_root"] == correct

    no_domain = merkle_root_no_domain(leaves)
    assert no_domain != correct, "domain-separation prefixes don't actually change the root in this fixture"


def test_merkle_no_duplicate_last_node(conn):
    stream_id = "custom-interval-001"
    cp = next(c for c in stream_checkpoints(conn, stream_id) if c["batch_index"] == 0)
    events = [e for e in stream_events(conn, stream_id) if cp["start_seq"] <= e["seq"] <= cp["end_seq"]]
    leaves = [e["leaf_hash"] for e in events]
    assert len(leaves) == 9, "expected an odd-sized batch to distinguish tree constructions"

    correct = merkle_root(leaves)
    wrong = merkle_root_duplicate_last(leaves)
    assert correct != wrong, "odd batch size doesn't actually distinguish the two tree constructions"
    assert cp["merkle_root"] == correct
    assert cp["merkle_root"] != wrong


def test_chain_genesis_hash(pipeline, conn):
    for stream_id in ("v1-legacy-002", "tombstone-002", "untouched-002"):
        cps = stream_checkpoints(conn, stream_id)
        assert len(cps) == 1, f"{stream_id} fixture expected exactly one checkpoint"
        cp = cps[0]
        expected_tip = fold_checkpoint(
            genesis(stream_id), cp["batch_index"], cp["start_seq"], cp["end_seq"], cp["merkle_root"], cp["key_id"],
        ).hex()
        actual = find_stream(pipeline.verify_after, stream_id)
        assert actual["chain_tip_hash"] == expected_tip


def test_checkpoint_interval_per_stream(pipeline, conn):
    for stream_id in ("custom-interval-001", "custom-interval-002"):
        stream_row = get_stream_row(conn, stream_id)
        interval = stream_row["checkpoint_interval"]
        assert interval not in (25, 50), f"{stream_id} should use a non-default interval to be a meaningful check"
        # use the pre-compaction count: pruning can legitimately remove whole
        # batches' worth of events, which must not be mistaken for the tool
        # mis-sizing checkpoints against a non-default interval.
        original_count = pipeline.pre_compact_event_counts[stream_id]
        cps = stream_checkpoints(conn, stream_id)
        assert len(cps) == original_count // interval
        assert_matches_oracle(conn, pipeline.verify_after, stream_id)
        assert find_stream(pipeline.verify_after, stream_id)["status"] == "ok"


def test_compact_removes_expired_events(pipeline, conn):
    now = pipeline.compact_1["now"]
    any_pruned = False
    for stream_id in ("expiring-001", "expiring-002", "boundary-inclusive-001",
                       "clean-bulk-001", "clean-bulk-004", "clean-bulk-007", "clean-bulk-010"):
        stream_row = get_stream_row(conn, stream_id)
        eligible, retained = oracle_compact_eligible_batches(conn, pipeline.pre_compact_events, stream_row, now)
        cps = {cp["batch_index"]: cp for cp in stream_checkpoints(conn, stream_id)}
        for b in eligible:
            cp = cps[b]
            assert batch_fully_pruned(conn, stream_id, cp["start_seq"], cp["end_seq"]), (
                f"{stream_id} batch {b} was eligible for pruning but its events are still present"
            )
        for b in retained:
            cp = cps[b]
            assert not batch_fully_pruned(conn, stream_id, cp["start_seq"], cp["end_seq"]), (
                f"{stream_id} batch {b} was not eligible for pruning but its events are gone"
            )
        if eligible:
            any_pruned = True
    assert any_pruned, "none of the sampled streams had prunable batches; fixture assumption broken"


def test_compact_preserves_legal_hold_events(pipeline, conn):
    now = pipeline.compact_1["now"]
    stream_id = "legal-hold-event-001"
    stream_row = get_stream_row(conn, stream_id)
    eligible, retained = oracle_compact_eligible_batches(conn, pipeline.pre_compact_events, stream_row, now)
    entry = find_stream(pipeline.compact_1, stream_id)
    assert 0 in entry["batches_retained"], "batch containing the legal-hold event must be retained"
    assert 0 not in entry["batches_pruned"]

    cps = {cp["batch_index"]: cp for cp in stream_checkpoints(conn, stream_id)}
    assert not batch_fully_pruned(conn, stream_id, cps[0]["start_seq"], cps[0]["end_seq"])
    for b in eligible:
        cp = cps[b]
        assert batch_fully_pruned(conn, stream_id, cp["start_seq"], cp["end_seq"]), (
            f"batch {b} was eligible for pruning but its events are still present"
        )
    assert len(eligible) > 0, "fixture should have at least one batch that IS eligible, otherwise this isn't a real test"


def test_compact_preserves_legal_hold_streams(pipeline, conn):
    entry = find_stream(pipeline.compact_1, "legal-hold-stream-001")
    assert entry["batches_pruned"] == []
    assert entry["events_deleted"] == 0
    before = pipeline.pre_compact_event_counts.get("legal-hold-stream-001", 0)
    after = conn.execute("SELECT COUNT(*) c FROM events WHERE stream_id=?", ("legal-hold-stream-001",)).fetchone()["c"]
    assert before == after


def test_compact_batch_aligned_pruning_only(pipeline, conn):
    for stream_row in all_streams(conn):
        stream_id = stream_row["stream_id"]
        remaining = {e["seq"] for e in stream_events(conn, stream_id)}
        for cp in stream_checkpoints(conn, stream_id):
            batch_seqs = set(range(cp["start_seq"], cp["end_seq"] + 1))
            present = batch_seqs & remaining
            assert present == batch_seqs or not present, (
                f"{stream_id} batch {cp['batch_index']} is partially pruned "
                f"({len(present)}/{len(batch_seqs)} events remain) -- pruning must be whole-batch only"
            )


def test_compact_idempotent_rerun(pipeline):
    for entry in pipeline.compact_2["streams"]:
        assert entry["batches_pruned"] == [], f"{entry['stream_id']}: second compact run pruned new batches"
        assert entry["events_deleted"] == 0, f"{entry['stream_id']}: second compact run deleted rows"
    ids_1 = {s["stream_id"] for s in pipeline.compact_1["streams"]}
    ids_2 = {s["stream_id"] for s in pipeline.compact_2["streams"]}
    assert ids_1 == ids_2


def test_verify_after_compact_matches_manifest_tip_hash(pipeline):
    manifest_by_id = {s["stream_id"]: s for s in pipeline.compact_1["streams"]}
    mismatches = [
        e["stream_id"] for e in pipeline.verify_after["streams"]
        if e["chain_tip_hash"] != manifest_by_id[e["stream_id"]]["chain_tip_hash"]
    ]
    assert not mismatches, f"chain_tip_hash disagreement between verify (after compact) and the compact manifest: {mismatches}"

    manifest2_by_id = {s["stream_id"]: s for s in pipeline.compact_2["streams"]}
    mismatches2 = [
        sid for sid, m in manifest_by_id.items() if manifest2_by_id[sid]["chain_tip_hash"] != m["chain_tip_hash"]
    ]
    assert not mismatches2, f"chain_tip_hash changed between the first and second compact run: {mismatches2}"


def test_verify_after_compact_still_consistent(pipeline):
    before_by_id = {s["stream_id"]: s for s in pipeline.verify_before["streams"]}
    for entry in pipeline.verify_after["streams"]:
        before = before_by_id[entry["stream_id"]]
        if before["status"] in ("corrupt", "legacy_unverifiable"):
            assert entry["status"] == before["status"], (
                f"{entry['stream_id']}: status changed from {before['status']} to {entry['status']} "
                "as a side effect of compaction"
            )
        else:
            assert entry["status"] == "ok", (
                f"{entry['stream_id']}: previously-ok stream became {entry['status']} after compaction"
            )


def test_compact_untouched_streams_unchanged(pipeline, conn):
    for stream_id in ("untouched-001", "untouched-002"):
        entry = find_stream(pipeline.compact_1, stream_id)
        assert entry["batches_pruned"] == []
        assert entry["events_deleted"] == 0
        before = pipeline.pre_compact_event_counts.get(stream_id, 0)
        after = conn.execute("SELECT COUNT(*) c FROM events WHERE stream_id=?", (stream_id,)).fetchone()["c"]
        assert before == after


def test_retention_boundary_inclusive(pipeline, conn):
    stream_id = "boundary-inclusive-001"
    entry = find_stream(pipeline.compact_1, stream_id)
    assert 1 in entry["batches_retained"], "batch starting one second after the cutoff must not be pruned"

    cps = {cp["batch_index"]: cp for cp in stream_checkpoints(conn, stream_id)}
    assert batch_fully_pruned(conn, stream_id, cps[0]["start_seq"], cps[0]["end_seq"]), (
        "batch ending exactly at the retention cutoff must be treated as expired (inclusive) and pruned"
    )
    assert not batch_fully_pruned(conn, stream_id, cps[1]["start_seq"], cps[1]["end_seq"])


def test_db_not_regenerated_canary(pipeline, conn):
    row = conn.execute("SELECT marker FROM _canary WHERE id=1").fetchone()
    assert row is not None, "_canary row missing -- database may have been regenerated"
    assert row["marker"] == "CHAINAUDIT-CANARY-8f2c9a1e-do-not-regenerate"


def test_all_streams_match_oracle_exhaustively(pipeline, conn):
    """Every stream, every run, deterministically -- not a random sample.

    Covers both verify's per-stream fields and compact's batch-level pruning
    decisions against the oracle, and fully accounts for every checkpoint
    batch in every stream as pruned, retained, or already-empty at pipeline
    start, so a fix that only special-cases the named fixture streams (or
    that happens to get lucky on whichever few streams a sample would have
    picked) has nowhere left to hide.
    """
    now = pipeline.compact_1["now"]
    mismatches = []
    for stream_row in all_streams(conn):
        stream_id = stream_row["stream_id"]
        expected = oracle_verify_stream(conn, stream_row)
        actual = find_stream(pipeline.verify_after, stream_id)
        for key in ("status", "reason", "first_bad_seq", "first_bad_batch", "chain_tip_hash", "event_count", "checkpoint_count"):
            if actual[key] != expected[key]:
                mismatches.append(f"{stream_id}.{key}: expected {expected[key]!r}, got {actual[key]!r}")
        if actual["revoked_key_ids"] != expected["revoked_key_ids"]:
            mismatches.append(f"{stream_id}.revoked_key_ids: expected {expected['revoked_key_ids']}, got {actual['revoked_key_ids']}")

        eligible, retained = oracle_compact_eligible_batches(conn, pipeline.pre_compact_events, stream_row, now)
        manifest_entry = find_stream(pipeline.compact_1, stream_id)
        pruned_set = set(manifest_entry["batches_pruned"])
        retained_set = set(manifest_entry["batches_retained"])
        cps = {cp["batch_index"]: cp for cp in stream_checkpoints(conn, stream_id)}

        for b in eligible:
            cp = cps[b]
            if not batch_fully_pruned(conn, stream_id, cp["start_seq"], cp["end_seq"]):
                mismatches.append(f"{stream_id} batch {b}: eligible for pruning but events remain")
        for b in retained:
            cp = cps[b]
            if batch_fully_pruned(conn, stream_id, cp["start_seq"], cp["end_seq"]):
                mismatches.append(f"{stream_id} batch {b}: not eligible for pruning but its events are gone")

        for b, cp in cps.items():
            was_already_empty = all(
                pipeline.pre_compact_events.get((stream_id, seq)) is None
                for seq in range(cp["start_seq"], cp["end_seq"] + 1)
            )
            accounted = (b in pruned_set) or (b in retained_set) or was_already_empty
            if not accounted:
                mismatches.append(f"{stream_id} batch {b}: not accounted for in batches_pruned, batches_retained, or already-empty")
            if (b in pruned_set) and (b in retained_set):
                mismatches.append(f"{stream_id} batch {b}: appears in both batches_pruned and batches_retained")

    assert not mismatches, "oracle disagreements found:\n" + "\n".join(mismatches)


def test_agent_constructed_exploit_defeats_content_check_only(pipeline):
    """The agent must construct their own tampering -- not point at a
    pre-seeded corrupt stream -- that survives the per-event content check by
    correctly recomputing leaf_hash, while remaining caught by the
    structural (Merkle) check, since forging a consistent batch root would
    require the signing key they don't have. See instruction.md.
    """
    report_path = OUT_DIR / "exploit_report.json"
    assert report_path.exists(), "expected /app/out/exploit_report.json describing a self-constructed tampering"
    claim = json.loads(report_path.read_text())
    stream_id, seq = claim["stream_id"], int(claim["seq"])
    assert stream_id not in FORBIDDEN_EXPLOIT_STREAMS, (
        f"{stream_id} is one of the fixture's own pre-existing corrupt/revoked streams -- "
        "construct new tampering against a stream that started out clean"
    )

    exploit_db_path = OUT_DIR / "exploit.db"
    assert exploit_db_path.exists(), "expected /app/out/exploit.db, a tampered copy of the database"

    exp_conn = sqlite3.connect(str(exploit_db_path))
    exp_conn.row_factory = sqlite3.Row
    exp_stream = get_stream_row(exp_conn, stream_id)
    cp = exp_conn.execute(
        "SELECT * FROM checkpoints WHERE stream_id=? AND ? BETWEEN start_seq AND end_seq",
        (stream_id, seq),
    ).fetchone()
    assert cp is not None, (
        f"seq {seq} in {stream_id} isn't covered by any checkpoint in exploit.db -- "
        "pick an event from an intact, checkpointed batch"
    )
    batch_events = exp_conn.execute(
        "SELECT * FROM events WHERE stream_id=? AND seq BETWEEN ? AND ? ORDER BY seq",
        (stream_id, cp["start_seq"], cp["end_seq"]),
    ).fetchall()
    assert len(batch_events) == (cp["end_seq"] - cp["start_seq"] + 1), (
        f"batch {cp['batch_index']} of {stream_id} is not fully present in exploit.db -- "
        "pick a target whose checkpoint batch is intact"
    )

    target = next(e for e in batch_events if e["seq"] == seq)
    recomputed_leaf = leaf_hash(canonical_event(
        stream_id, exp_stream["migrated_at"], target["seq"], target["ts"], target["event_type"],
        target["payload"], target["tombstone"], target["legal_hold"],
    ))
    assert recomputed_leaf == target["leaf_hash"], (
        f"{stream_id} seq {seq}: stored leaf_hash doesn't match its current content in exploit.db -- "
        "the per-event content check would already catch this on its own; the point is to defeat that "
        "one check specifically by keeping the row internally self-consistent"
    )

    orig_conn = sqlite3.connect(str(DB_PATH))
    orig_conn.row_factory = sqlite3.Row
    orig_stream = get_stream_row(orig_conn, stream_id)
    orig_event = orig_conn.execute("SELECT * FROM events WHERE stream_id=? AND seq=?", (stream_id, seq)).fetchone()
    assert orig_event is not None, (
        f"{stream_id} seq {seq} is no longer present in /app/data/chainaudit.db (likely pruned by compact "
        "since exploit.db was made) -- pick a target from a stream that's never eligible for pruning"
    )
    orig_recomputed = leaf_hash(canonical_event(
        stream_id, orig_stream["migrated_at"], orig_event["seq"], orig_event["ts"], orig_event["event_type"],
        orig_event["payload"], orig_event["tombstone"], orig_event["legal_hold"],
    ))
    assert orig_recomputed == orig_event["leaf_hash"], (
        f"{stream_id} seq {seq} was already inconsistent in the original fixture -- pick a target that started out clean"
    )
    changed = (
        target["payload"] != orig_event["payload"]
        or target["event_type"] != orig_event["event_type"]
        or target["ts"] != orig_event["ts"]
        or target["tombstone"] != orig_event["tombstone"]
        or target["legal_hold"] != orig_event["legal_hold"]
    )
    assert changed, f"{stream_id} seq {seq}: content in exploit.db is identical to the original -- nothing was actually tampered"
    orig_conn.close()

    leaves = [e["leaf_hash"] for e in batch_events]
    rebuilt_root = merkle_root(leaves)
    assert rebuilt_root != cp["merkle_root"], (
        f"{stream_id} batch {cp['batch_index']}: the Merkle root still matches after your edit -- "
        "this doesn't demonstrate defeating only the content-level check"
    )
    exp_conn.close()

    verify_out = OUT_DIR / "exploit_verify_report.json"
    r = subprocess.run(
        [str(pipeline.binary), "verify", "--db", str(exploit_db_path), "--out", str(verify_out), "--kms-addr", KMS_ADDR],
        cwd=str(APP), capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, f"verify failed against exploit.db: {r.stderr}"
    exploit_report = json.loads(verify_out.read_text())
    entry = find_stream(exploit_report, stream_id)
    assert entry["status"] == "corrupt", f"expected exploit.db's {stream_id} to verify as corrupt, got {entry['status']}"
    assert entry["reason"] == "tampered_merkle_root", (
        f"expected reason=tampered_merkle_root (the content check was defeated; only the structural "
        f"check should still catch this), got {entry['reason']!r}"
    )
    assert entry["first_bad_batch"] == cp["batch_index"]
    assert entry["first_bad_seq"] is None, "the content check should not also be firing here"


def test_no_unexpected_network_egress():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    reached = True
    try:
        s.connect(("1.1.1.1", 443))
    except OSError:
        reached = False
    finally:
        s.close()
    assert not reached, "outbound internet connectivity is reachable; this task must run with no route to the internet"
