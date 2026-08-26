import json
import subprocess
from pathlib import Path

APP = Path("/app")
ENV = APP / "environment"
OUT = APP / "output" / "rule_witness.json"
STUB = ENV / "blk_m2" / "snap_q4" / "q4_stub.json"
ARMS = ("cedar", "maple", "birch", "willow")
BANDS = ("dawn", "dusk")

FORK_SCOPES = {
    "cedar": 4,
    "maple": 3,
    "birch": 5,
    "willow": 6,
}


def _run_checker() -> dict:
    OUT.unlink(missing_ok=True)
    subprocess.run(["bash", "/app/environment/scripts/bake_rs.sh"], check=True)
    proc = subprocess.run(
        [
            "/app/environment/bin/grti_matrix_k9",
            "--all-arms",
            "--witness-out",
            str(OUT),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert OUT.exists(), "rule_witness.json missing"
    return json.loads(OUT.read_text(encoding="utf-8"))


def _rows_by_key(witness: dict) -> dict:
    return {(row["arm"], row["band"]): row for row in witness["rows"]}


def _digest_from_replay_hex(replay_hex: str) -> str:
    proc = subprocess.run(
        [
            "python3",
            "-c",
            "import hashlib,sys; print(hashlib.sha256(bytes.fromhex(sys.argv[1])).hexdigest())",
            replay_hex,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def test_t_q7_live_row():
    """Witness rows bind live GRTIROW replay bytes and arm tags."""
    witness = _run_checker()
    rows = _rows_by_key(witness)
    assert set(rows) == {(a, b) for a in ARMS for b in BANDS}
    digests = set()
    for (arm, band), row in rows.items():
        assert row["row_label"].startswith("GRTIROW|")
        assert arm in row["row_label"]
        assert band in row["row_label"]
        assert row["replay_hex"]
        assert row["move_digest"] == _digest_from_replay_hex(row["replay_hex"])
        digests.add(row["move_digest"])
    assert len(digests) == 8


def test_t_m3_arm_split():
    """Arm fork bytes diverge on fork scopes."""
    witness = _run_checker()
    rows = _rows_by_key(witness)
    fork_bytes = {arm: set() for arm in ARMS}
    for arm in ARMS:
        for band in BANDS:
            row = rows[(arm, band)]
            assert row["fork_tag"] == f"FORK{arm}:{FORK_SCOPES[arm]}"
            fork_bytes[arm].add(row["replay_hex"][:24])
    assert all(len(v) >= 1 for v in fork_bytes.values())
    assert fork_bytes["cedar"] != fork_bytes["maple"]


def test_t_n8_seq_gate():
    """Gated scopes clear pending and advance seq ladder."""
    witness = _run_checker()
    rows = _rows_by_key(witness)
    birch_dawn = rows[("birch", "dawn")]
    birch_dusk = rows[("birch", "dusk")]
    assert birch_dawn["seq"] == birch_dusk["seq"]
    assert birch_dawn["gate_cursor"] == birch_dusk["gate_cursor"]
    assert birch_dawn["move_digest"] != birch_dusk["move_digest"]


def test_t_p2_epoch_mono():
    """Epoch marks monotone per band."""
    witness = _run_checker()
    rows = _rows_by_key(witness)
    for arm in ARMS:
        dawn_epoch = rows[(arm, "dawn")]["epoch_mark"]
        dusk_epoch = rows[(arm, "dusk")]["epoch_mark"]
        assert dawn_epoch >= dusk_epoch or dusk_epoch == 0


def test_t_r4_triple_hash():
    """Triple-pass digest stability."""
    digests = []
    for _ in range(3):
        witness = _run_checker()
        rows = _rows_by_key(witness)
        digests.append(tuple(rows[(a, b)]["move_digest"] for a in ARMS for b in BANDS))
    assert digests[0] == digests[1] == digests[2]


def test_t_s1_chain_depth():
    """Phase-then-full-pass chain integrity."""
    witness = _run_checker()
    rows = _rows_by_key(witness)
    maple_dawn = rows[("maple", "dawn")]
    maple_dusk = rows[("maple", "dusk")]
    assert maple_dawn["epoch_mark"] > maple_dusk["epoch_mark"]
    assert maple_dawn["seq"] == maple_dusk["seq"]


def test_t_t5_journal_end():
    """Export journal terminal shape."""
    witness = _run_checker()
    tail = witness["journal_tail"]
    assert tail
    parts = tail.split(":")
    assert len(parts) >= 3
    for part in parts:
        assert len(part) == 16
        int(part, 16)


def test_t_u6_wipe_parity():
    """Wipe-recover digest parity."""
    subprocess.run(["bash", "/app/environment/migrations/clr9.sh"], check=True)
    subprocess.run(["bash", "/app/environment/migrations/clr9.sh", "--recover"], check=True)
    before = _run_checker()
    witness_after = _run_checker()
    rows_before = _rows_by_key(before)
    rows_after = _rows_by_key(witness_after)
    for key in rows_before:
        assert rows_before[key]["move_digest"] == rows_after[key]["move_digest"]


def test_t_v9_spread_ladder():
    """Band spread ladder."""
    witness = _run_checker()
    ladder = witness["spread_ladder"]
    assert len(ladder) == 8
    for arm in ARMS:
        for band in BANDS:
            row = _rows_by_key(witness)[(arm, band)]
            token = f"{arm}:{band}:{row['seq']}"
            assert token in ladder


def test_t_w2_note_trap():
    """Interim tally false-green trap."""
    witness = _run_checker()
    stub = json.loads(STUB.read_text(encoding="utf-8"))
    rows = witness["rows"]
    assert stub["local_tally"] < len(rows)
    assert stub["status"] == "ROW_OK"
    assert all(row["move_digest"] == _digest_from_replay_hex(row["replay_hex"]) for row in rows)


def test_t_x3_lane_couple():
    """Flag-lane coupling and gate cursor shift."""
    witness = _run_checker()
    rows = _rows_by_key(witness)
    assert rows[("birch", "dawn")]["gate_cursor"] == rows[("birch", "dusk")]["gate_cursor"]
    assert rows[("birch", "dawn")]["gate_cursor"] > rows[("cedar", "dawn")]["gate_cursor"]


def test_t_y7_cursor_shift():
    """Gate cursor shift across arms."""
    witness = _run_checker()
    rows = _rows_by_key(witness)
    cedar = rows[("cedar", "dawn")]["gate_cursor"]
    birch = rows[("birch", "dawn")]["gate_cursor"]
    willow = rows[("willow", "dawn")]["gate_cursor"]
    assert birch > cedar
    assert birch > willow
