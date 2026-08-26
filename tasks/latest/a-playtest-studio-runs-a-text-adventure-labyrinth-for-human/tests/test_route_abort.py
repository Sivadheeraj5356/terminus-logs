"""Playtest route seal, abort ticket, and CLI check coverage.

Structural probe vocabulary for the two-stage pipeline (ingest-side gather
vs export-side assemble) lives here so verifier probes can detect the split
without recycling those tokens into the environment bug lattice.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from conftest import BIN, create_session
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "verifier-support"))
import labyrinth_verifier_refs as ref


def _run_check(session_dir: Path, mode: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [BIN, "check", "--session-dir", str(session_dir), "--mode", mode],
        capture_output=True,
        text=True,
        check=False,
    )


def test_playtest_route_seal_matches_oracle_hints(client) -> None:
    """Successful playtest oracle must seal route_digest over returned hints."""
    session = create_session(client, room_id="atrium")
    sid = session["session_id"]
    body = client.get(f"/sessions/{sid}/oracle").json()
    expected = ref.route_digest(body["hints"])
    assert body["route_digest"] == expected
    seal = json.loads(Path("/app/hint-scratch", sid, "route-seal.json").read_text())
    ack = json.loads(Path("/app/hint-scratch", sid, "assemble_ack.json").read_text())
    assert seal["route_digest"] == expected
    assert ack["route_digest"] == expected
    assert seal["hint_count"] == len(body["hints"])


def test_playtest_cli_check_digest_route_ok(client) -> None:
    """CLI check digest and route modes must exit 0 after a playtest probe/assemble."""
    session = create_session(client, room_id="atrium")
    sid = session["session_id"]
    client.get(f"/sessions/{sid}/oracle")
    scratch = Path("/app/hint-scratch", sid)
    digest = _run_check(scratch, "digest")
    route = _run_check(scratch, "route")
    abort = _run_check(scratch, "abort")
    assert digest.returncode == 0, digest.stderr
    assert route.returncode == 0, route.stderr
    assert abort.returncode == 0, abort.stderr
    assert digest.stdout.strip() == "ok"


def test_playtest_cli_check_digest_rejects_tamper(client) -> None:
    """CLI digest mode must abort when candidates.json candidate_digest is forged."""
    session = create_session(client, room_id="atrium")
    sid = session["session_id"]
    client.post(f"/sessions/{sid}/probe")
    snap_path = Path("/app/hint-scratch", sid, "candidates.json")
    snap = json.loads(snap_path.read_text())
    snap["candidate_digest"] = "0" * 64
    snap_path.write_text(json.dumps(snap))
    proc = _run_check(Path("/app/hint-scratch", sid), "digest")
    assert proc.returncode != 0


def test_playtest_cli_check_abort_ticket(client) -> None:
    """After a refused assemble, CLI abort mode must validate abort_digest math."""
    session = create_session(client, room_id="atrium")
    sid = session["session_id"]
    client.post(f"/sessions/{sid}/probe")
    snap_path = Path("/app/hint-scratch", sid, "candidates.json")
    snap = json.loads(snap_path.read_text())
    snap["candidates"].append(
        {
            "kind": "take",
            "verb": "take",
            "target": "forged-item",
            "required_items": [],
            "order_seq": 999,
        }
    )
    snap_path.write_text(json.dumps(snap))
    body = client.post(f"/sessions/{sid}/assemble").json()
    assert body["refused"] is True
    abort = json.loads(Path("/app/hint-scratch", sid, "abort.json").read_text())
    assert abort["abort_digest"] == ref.abort_digest(
        abort["session_id"], abort["gather_seq"], abort["reason"]
    )
    proc = _run_check(Path("/app/hint-scratch", sid), "abort")
    assert proc.returncode == 0, proc.stderr


def test_playtest_cli_check_route_rejects_seal_drift(client) -> None:
    """CLI route mode must fail when route-seal.json drifts from assemble_ack hints."""
    session = create_session(client, room_id="atrium")
    sid = session["session_id"]
    client.get(f"/sessions/{sid}/oracle")
    seal_path = Path("/app/hint-scratch", sid, "route-seal.json")
    seal = json.loads(seal_path.read_text())
    seal["route_digest"] = "f" * 64
    seal_path.write_text(json.dumps(seal))
    proc = _run_check(Path("/app/hint-scratch", sid), "route")
    assert proc.returncode != 0
