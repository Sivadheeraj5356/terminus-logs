"""Hidden catacombs world checks. These use a world.json and chronicle.md
that ship only under /opt/verifier-fixtures, never under /app, so they
exercise a different world_id and a different forbidden-rule set than the
bundled labyrinth world the other test modules cover.
"""

from __future__ import annotations

from conftest import create_session
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "verifier-support"))
import labyrinth_verifier_refs as ref


def test_catacombs_session_defaults_to_its_own_start_room(client) -> None:
    """Hidden catacombs under /opt/verifier-fixtures start in that world's start_room."""
    session = create_session(client, world_id="catacombs")
    assert session["world_id"] == "catacombs"
    assert session["room"] == "entry"


def test_playtest_hidden_world_entry_hints_rematch(client) -> None:
    """Playtest hints for /opt/verifier-fixtures catacombs entry match the reference."""
    session = create_session(client, world_id="catacombs", room_id="entry")
    resp = client.get(f"/sessions/{session['session_id']}/oracle")
    assert resp.status_code == 200
    hints = resp.json()["hints"]

    world = ref.load_world("catacombs")
    forbidden = ref.load_forbidden_rules("catacombs")
    expected = ref.expected_hints(world, "entry", [], [], forbidden)
    assert hints == expected


def test_catacombs_drain_sluice_is_forbidden_by_its_own_chronicle(client) -> None:
    """The /opt/verifier-fixtures catacombs chronicle forbids cistern drain sluice."""
    session = create_session(client, world_id="catacombs", room_id="cistern", inventory=["rope-coil"])
    resp = client.post(
        f"/sessions/{session['session_id']}/attempt",
        json={"verb": "drain", "target": "sluice"},
    )
    body = resp.json()
    assert body["ok"] is False
    assert body["reason"] == "forbidden"


def test_playtest_route_abyss_multi_item_invariant(client) -> None:
    """Hidden /opt/verifier-fixtures reliquary-to-abyss exit needs both items."""
    only_whistle = create_session(client, world_id="catacombs", room_id="reliquary", inventory=["bone-whistle"])
    resp = client.get(f"/sessions/{only_whistle['session_id']}/oracle")
    hints = resp.json()["hints"]
    assert {"kind": "move", "verb": "go-abyss", "target": "abyss"} not in hints

    both_items = create_session(
        client, world_id="catacombs", room_id="reliquary", inventory=["bone-whistle", "iron-hook"]
    )
    resp2 = client.get(f"/sessions/{both_items['session_id']}/oracle")
    hints2 = resp2.json()["hints"]
    assert {"kind": "move", "verb": "go-abyss", "target": "abyss"} in hints2


def test_catacombs_ossuary_search_niche_forbidden_needs_second_rule(client) -> None:
    """Second /opt/verifier-fixtures catacombs @RULE forbids ossuary search niche."""
    session = create_session(client, world_id="catacombs", room_id="ossuary", inventory=["tallow-candle"])
    resp = client.post(
        f"/sessions/{session['session_id']}/attempt",
        json={"verb": "search", "target": "niche"},
    )
    body = resp.json()
    assert body["ok"] is False
    assert body["reason"] == "forbidden"
