"""Hint snapshot contract checks against /app/hint-scratch/{session_id}, per
/app/docs/probe-assemble-pipeline.md and /app/docs/snapshot-attestation.md.
"""

from __future__ import annotations

import json
from pathlib import Path

from conftest import create_session
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "verifier-support"))
import labyrinth_verifier_refs as ref


def _scratch_path(session_id: str) -> Path:
    return Path("/app/hint-scratch", session_id, "candidates.json")


def _assemble_ack_path(session_id: str) -> Path:
    return Path("/app/hint-scratch", session_id, "assemble_ack.json")


def test_probe_writes_candidates_snapshot_with_documented_fields(client) -> None:
    """Probe writes candidates.json with every attested field from snapshot-attestation.md."""
    session = create_session(client, room_id="atrium")
    resp = client.post(f"/sessions/{session['session_id']}/probe")
    assert resp.status_code == 200

    snap = json.loads(_scratch_path(session["session_id"]).read_text())
    for field in (
        "session_id",
        "room",
        "world_id",
        "gather_seq",
        "chronicle_sha256",
        "session_state_sha256",
        "candidate_digest",
        "candidates",
    ):
        assert field in snap, field
    assert snap["room"] == "atrium"
    assert snap["world_id"] == "labyrinth"


def test_probe_candidate_count_covers_every_room_lane(client) -> None:
    """The Ember Sanctum has one action, zero exits, zero items. A probe
    that omits room actions from the gather stage would stage zero
    candidates here even though one action exists.
    """
    session = create_session(client, room_id="sanctum")
    client.post(f"/sessions/{session['session_id']}/probe")
    snap = json.loads(_scratch_path(session["session_id"]).read_text())
    assert len(snap["candidates"]) == 1
    assert snap["candidates"][0]["kind"] == "action"
    assert snap["candidates"][0]["target"] == "brazier"


def test_playtest_probe_gather_order_invariant(client) -> None:
    """gallery has exits, an action, and an item; candidate order_seq must
    follow the exit/action/item, ascending-by-id gather order documented
    in /app/docs/probe-assemble-pipeline.md, not on-disk file order.
    """
    session = create_session(client, room_id="gallery", inventory=["torch", "brass-key"])
    client.post(f"/sessions/{session['session_id']}/probe")
    snap = json.loads(_scratch_path(session["session_id"]).read_text())

    world = ref.load_world("labyrinth")
    expected = ref.gather_candidates(world, "gallery")
    actual = [{"kind": c["kind"], "verb": c["verb"], "target": c["target"]} for c in snap["candidates"]]
    expected_stripped = [{"kind": c["kind"], "verb": c["verb"], "target": c["target"]} for c in expected]
    assert actual == expected_stripped


def test_probe_chronicle_digest_matches_independent_sha256(client) -> None:
    """Staged chronicle_sha256 matches an independent SHA-256 of the chronicle file."""
    session = create_session(client, room_id="atrium")
    client.post(f"/sessions/{session['session_id']}/probe")
    snap = json.loads(_scratch_path(session["session_id"]).read_text())
    assert snap["chronicle_sha256"] == ref.chronicle_digest("labyrinth")


def test_playtest_assemble_refuses_stale_rematch_state(client) -> None:
    """Probing atrium, then moving to gallery before assembling, must make
    the assemble lane detect the stale session_state_sha256 and refuse with
    empty hints instead of assembling hints for the wrong room.
    """
    session = create_session(client, room_id="atrium")
    sid = session["session_id"]
    client.post(f"/sessions/{sid}/probe")

    move_resp = client.post(f"/sessions/{sid}/attempt", json={"verb": "go-gallery", "target": "gallery"})
    assert move_resp.json()["ok"] is True

    assemble_resp = client.post(f"/sessions/{sid}/assemble")
    assert assemble_resp.status_code == 200
    body = assemble_resp.json()
    assert body["refused"] is True
    assert body["hints"] in (None, [])
    assert not _assemble_ack_path(sid).exists()
    assert not Path("/app/hint-scratch", sid, "route-seal.json").exists()
    abort = json.loads(Path("/app/hint-scratch", sid, "abort.json").read_text())
    assert abort["reason"] == "stale-session-state"


def test_assemble_ack_written_only_after_successful_assembly(client) -> None:
    """assemble_ack.json and route-seal.json appear only after successful playtest assembly."""
    session = create_session(client, room_id="atrium")
    sid = session["session_id"]
    body = client.get(f"/sessions/{sid}/oracle").json()
    ack = json.loads(_assemble_ack_path(sid).read_text())
    seal = json.loads(Path("/app/hint-scratch", sid, "route-seal.json").read_text())
    assert ack["session_id"] == sid
    assert ack["gather_seq"] >= 1
    assert "route_digest" in ack
    assert ack["route_digest"] == body["route_digest"]
    assert seal["route_digest"] == body["route_digest"]
    assert not Path("/app/hint-scratch", sid, "abort.json").exists()


def test_gather_seq_increments_across_successive_probes(client) -> None:
    """Repeated probes of the same session must not report the same
    gather_seq value, or a gather counter is never actually advancing.
    """
    session = create_session(client, room_id="atrium")
    sid = session["session_id"]
    first = client.post(f"/sessions/{sid}/probe").json()["gather_seq"]
    second = client.post(f"/sessions/{sid}/probe").json()["gather_seq"]
    assert second > first
