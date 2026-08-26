"""Attestation digest checks against /app/docs/snapshot-attestation.md.
Each digest is recomputed independently in tests/verifier-support/labyrinth_verifier_refs.py and
compared byte-for-byte against what the running oracle staged.
"""

from __future__ import annotations

import json
from pathlib import Path

from conftest import create_session
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "verifier-support"))
import labyrinth_verifier_refs as ref


def _scratch_snapshot(session_id: str) -> dict:
    return json.loads(Path("/app/hint-scratch", session_id, "candidates.json").read_text())


def test_chronicle_digest_is_a_64_char_sha256_hex_string(client) -> None:
    """chronicle_sha256 is a lowercase SHA-256 hex digest of the resolved chronicle bytes."""
    session = create_session(client, room_id="atrium")
    client.post(f"/sessions/{session['session_id']}/probe")
    snap = _scratch_snapshot(session["session_id"])
    digest = snap["chronicle_sha256"]
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)
    assert digest == ref.chronicle_digest("labyrinth")


def test_session_state_digest_matches_reference_field_order(client) -> None:
    """session_state_sha256 must hash world_id, room, inventory, consumed,
    failed in that fixed key order with inventory/consumed sorted and
    failed sorted by verb then target, not whatever order a generic map
    serializer would choose.
    """
    session = create_session(client, room_id="gallery", inventory=["torch", "brass-key"])
    sid = session["session_id"]
    client.post(f"/sessions/{sid}/attempt", json={"verb": "sing", "target": "wall"})
    client.post(f"/sessions/{sid}/probe")

    snap = _scratch_snapshot(sid)
    expected = ref.session_state_digest(
        world_id="labyrinth",
        room="gallery",
        inventory=["torch", "brass-key"],
        consumed=[],
        failed=[("sing", "wall")],
    )
    assert snap["session_state_sha256"] == expected


def test_candidate_digest_matches_reference_sorted_encoding(client) -> None:
    """candidate_digest matches the independent sort_keys compact encoding."""
    session = create_session(client, room_id="crossing", inventory=["silver-key", "lantern"])
    sid = session["session_id"]
    client.post(f"/sessions/{sid}/probe")
    snap = _scratch_snapshot(sid)

    world = ref.load_world("labyrinth")
    candidates = ref.gather_candidates(world, "crossing")
    assert snap["candidate_digest"] == ref.candidate_digest(candidates)


def test_assemble_refuses_when_candidates_file_is_tampered(client) -> None:
    """Editing a staged candidates.json by hand after probing must make
    the recomputed candidate_digest disagree, and assemble must refuse
    rather than trust the tampered file.
    """
    session = create_session(client, room_id="atrium")
    sid = session["session_id"]
    client.post(f"/sessions/{sid}/probe")

    snap_path = Path("/app/hint-scratch", sid, "candidates.json")
    snap = json.loads(snap_path.read_text())
    snap["candidates"].append({"kind": "take", "verb": "take", "target": "forged-item", "required_items": [], "order_seq": 999})
    snap_path.write_text(json.dumps(snap))

    assemble_resp = client.post(f"/sessions/{sid}/assemble")
    body = assemble_resp.json()
    assert body["refused"] is True
    assert body["reason"] == "candidate-digest-mismatch"
    abort = json.loads(Path("/app/hint-scratch", sid, "abort.json").read_text())
    assert abort["reason"] == "candidate-digest-mismatch"
    assert len(abort["abort_digest"]) == 64


def test_assemble_ack_gather_seq_matches_the_probe_that_produced_it(client) -> None:
    """After three probes of the same session, assemble_ack.json's
    gather_seq must equal the third probe's gather_seq exactly, proving
    the assemble lane is reading the counter forward, not always stamping
    a fixed value.
    """
    session = create_session(client, room_id="atrium")
    sid = session["session_id"]
    client.post(f"/sessions/{sid}/probe")
    client.post(f"/sessions/{sid}/probe")
    third_seq = client.post(f"/sessions/{sid}/probe").json()["gather_seq"]

    client.post(f"/sessions/{sid}/assemble")
    ack_seq = json.loads(Path("/app/hint-scratch", sid, "assemble_ack.json").read_text())["gather_seq"]
    assert third_seq == 3
    assert ack_seq == third_seq
