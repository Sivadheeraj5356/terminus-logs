"""Session lifecycle and basic HTTP contract checks against the running
labyrinth-oracle service, per /app/docs/oracle-contract.md.
"""

from __future__ import annotations

from conftest import create_session


def test_health_reports_ok(client) -> None:
    """Health endpoint reports status ok for playtest clients."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_session_defaults_to_labyrinth_start_room(client) -> None:
    """POST /sessions defaults to the bundled labyrinth start room with empty inventory."""
    session = create_session(client)
    assert session["world_id"] == "labyrinth"
    assert session["room"] == "atrium"
    assert session["inventory"] == []
    assert session["consumed"] == []
    assert session["failed"] == []
    assert session["session_id"]


def test_create_session_honors_room_and_inventory(client) -> None:
    """POST /sessions honors room_id and inventory fields from the request body."""
    session = create_session(client, room_id="gallery", inventory=["torch"])
    assert session["room"] == "gallery"
    assert session["inventory"] == ["torch"]


def test_create_session_rejects_unknown_world(client) -> None:
    """Unknown world_id returns 400 per oracle-contract.md."""
    resp = client.post("/sessions", json={"world_id": "nonexistent-world"})
    assert resp.status_code == 400


def test_create_session_rejects_unknown_room(client) -> None:
    """Unknown room_id for a known world returns 400."""
    resp = client.post("/sessions", json={"world_id": "labyrinth", "room_id": "nowhere"})
    assert resp.status_code == 400


def test_oracle_on_unknown_session_is_not_found(client) -> None:
    """GET oracle for an unknown session_id returns 404."""
    resp = client.get("/sessions/does-not-exist/oracle")
    assert resp.status_code == 404


def test_attempt_take_updates_inventory(client) -> None:
    """Successful take attempt adds the item to session inventory."""
    session = create_session(client)
    resp = client.post(f"/sessions/{session['session_id']}/attempt", json={"verb": "take", "target": "lantern"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "lantern" in body["inventory"]


def test_attempt_unknown_verb_target_is_recorded_as_failed(client) -> None:
    """Failed attempts are recorded in the session failed list."""
    session = create_session(client)
    resp = client.post(f"/sessions/{session['session_id']}/attempt", json={"verb": "sing", "target": "nothing"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert {"verb": "sing", "target": "nothing"} in body["failed"]
