"""Hint validity, forbidden-rule, and sort-order checks against the
labyrinth world, compared to the independent reference implementation in
tests/verifier-support/labyrinth_verifier_refs.py.
"""

from __future__ import annotations

from conftest import create_session
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "verifier-support"))
import labyrinth_verifier_refs as ref


def _hints_for(client, room_id: str, inventory: list[str] | None = None) -> list[dict]:
    session = create_session(client, room_id=room_id, inventory=inventory)
    resp = client.get(f"/sessions/{session['session_id']}/oracle")
    assert resp.status_code == 200
    return resp.json()["hints"]


def test_playtest_atrium_hints_match_independent_reference(client) -> None:
    """A fresh atrium session's hints exactly match the reference gather
    plus filter over the bundled labyrinth world and chronicle.
    """
    hints = _hints_for(client, "atrium")
    world = ref.load_world("labyrinth")
    forbidden = ref.load_forbidden_rules("labyrinth")
    expected = ref.expected_hints(world, "atrium", [], [], forbidden)
    assert hints == expected


def test_playtest_gallery_forbidden_search_invariant(client) -> None:
    """The chronicle's first forbidden rule (gallery search urn) must
    remove that action hint even when the required torch is held.
    """
    hints = _hints_for(client, "gallery", inventory=["torch"])
    assert {"kind": "action", "verb": "search", "target": "urn"} not in hints


def test_playtest_vault_second_rule_invariant(client) -> None:
    """The chronicle's second forbidden rule (vault go-atrium) must also
    be enforced, not just its first rule.
    """
    hints = _hints_for(client, "vault", inventory=["brass-key"])
    assert {"kind": "move", "verb": "go-atrium", "target": "atrium"} not in hints


def test_sanctum_action_hint_requires_only_missing_action_lane(client) -> None:
    """The Ember Sanctum offers only a room action (no exit, no item), so
    the sanctum's light-brazier hint is the sole signal that the action
    gather lane produced anything at all.
    """
    hints = _hints_for(client, "sanctum", inventory=["lantern"])
    assert {"kind": "action", "verb": "light", "target": "brazier"} in hints


def test_playtest_route_gate_requires_every_item(client) -> None:
    """go-sanctum requires both silver-key and lantern; holding only one
    of the two must not satisfy the exit's required_items gate.
    """
    only_lantern = _hints_for(client, "crossing", inventory=["lantern"])
    assert {"kind": "move", "verb": "go-sanctum", "target": "sanctum"} not in only_lantern

    both_items = _hints_for(client, "crossing", inventory=["lantern", "silver-key"])
    assert {"kind": "move", "verb": "go-sanctum", "target": "sanctum"} in both_items


def test_attempt_enforces_every_forbidden_rule_not_just_the_first(client) -> None:
    """The labyrinth chronicle lists two forbidden rules. An attempt
    against the second rule (vault go-atrium) must be refused exactly
    like an attempt against the first (gallery search urn), proving the
    chronicle parser is not silently stopping after one match.
    """
    first_rule_session = create_session(client, room_id="gallery", inventory=["torch"])
    first_resp = client.post(
        f"/sessions/{first_rule_session['session_id']}/attempt",
        json={"verb": "search", "target": "urn"},
    )
    assert first_resp.json()["ok"] is False

    second_rule_session = create_session(client, room_id="vault", inventory=["brass-key"])
    second_resp = client.post(
        f"/sessions/{second_rule_session['session_id']}/attempt",
        json={"verb": "go-atrium", "target": "atrium"},
    )
    assert second_resp.json()["ok"] is False
    assert second_resp.json()["reason"] == "forbidden"


def test_playtest_rematch_take_and_consume_clears_hints(client) -> None:
    """After a successful take, the same item must not still be offered
    as a take hint; after a successful action, the same target must not
    still be offered as an action hint.
    """
    session = create_session(client, room_id="atrium")
    sid = session["session_id"]

    take_resp = client.post(f"/sessions/{sid}/attempt", json={"verb": "take", "target": "lantern"})
    assert take_resp.json()["ok"] is True

    hints = client.get(f"/sessions/{sid}/oracle").json()["hints"]
    assert {"kind": "take", "verb": "take", "target": "lantern"} not in hints

    action_resp = client.post(f"/sessions/{sid}/attempt", json={"verb": "read", "target": "plaque"})
    assert action_resp.json()["ok"] is True

    hints_after_action = client.get(f"/sessions/{sid}/oracle").json()["hints"]
    assert {"kind": "action", "verb": "read", "target": "plaque"} not in hints_after_action
