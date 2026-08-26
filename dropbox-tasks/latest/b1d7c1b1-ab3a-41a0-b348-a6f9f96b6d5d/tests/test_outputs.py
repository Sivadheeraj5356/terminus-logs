"""Verifier tests for the license-seat allocation CLI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

CLI = "/app/bin/seat-allocate"
DEFAULT_FEED = "/app/data/onboarding_requests.ndjson"


def run_cli(tmp_path: Path, lines: list[dict] | None = None) -> dict:
    """Run the real CLI on the default feed or a custom feed and load the report."""
    if lines is None:
        feed = DEFAULT_FEED
    else:
        feed_path = tmp_path / "feed.ndjson"
        feed_path.write_text("".join(json.dumps(line) + "\n" for line in lines))
        feed = str(feed_path)
    out_path = tmp_path / "nested" / "out" / "allocation.json"
    proc = subprocess.run(
        ["node", CLI, feed, str(out_path)], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(out_path.read_text())


def request(event_id: str, request_id: str, edition: str, needed: int, **extra) -> dict:
    return {
        "id": event_id,
        "type": "request",
        "requestId": request_id,
        "edition": edition,
        "seatsNeeded": needed,
        **extra,
    }


def suspend(event_id: str, seat_id: str) -> dict:
    return {"id": event_id, "type": "suspend", "seatId": seat_id, "reason": "flagged-audit"}


def cancel(event_id: str, target: str) -> dict:
    return {"id": event_id, "type": "cancel", "target": target}


def test_default_top_level_keys_and_summary(tmp_path: Path) -> None:
    """The default batch report has exactly four top-level keys and the pinned summary."""
    report = run_cli(tmp_path)
    assert list(report) == ["events", "allocations", "unusedSeats", "summary"]
    assert report["summary"] == {
        "allocatedSeats": 9,
        "cancelledRequests": 1,
        "expiredSeats": 2,
        "filledRequests": 8,
        "prioritySum": 7,
        "rejectedEvents": 1,
        "requestCount": 10,
        "suspendedSeats": 1,
        "totalEvents": 22,
        "unfilledRequests": 2,
        "usableSeats": 12,
    }
    assert list(report["summary"]) == sorted(report["summary"])
    assert all(isinstance(v, int) for v in report["summary"].values())


def test_default_scarcity_chain_reserves_universal_seat_for_exclusive_request(tmp_path: Path) -> None:
    """S-101 must reach R-12, the only request that can take nothing else, leaving R-2 unfilled."""
    report = run_cli(tmp_path)
    rows = {a["requestId"]: a["seatIds"] for a in report["allocations"]}
    assert rows["R-12"] == ["S-101"]
    assert "R-2" not in rows
    assert rows["R-14"] == ["S-114"]


def test_default_allocation_rows_in_feed_order_with_sorted_ids(tmp_path: Path) -> None:
    """Allocation rows follow request feed order and each seatIds list is sorted."""
    report = run_cli(tmp_path)
    assert [a["requestId"] for a in report["allocations"]] == [
        "R-1",
        "R-3",
        "R-4",
        "R-6",
        "R-7",
        "R-12",
        "R-14",
        "R-15",
    ]
    for a in report["allocations"]:
        assert a["seatIds"] == sorted(a["seatIds"])


def test_default_secure_tier_rows_use_exact_edition_seats(tmp_path: Path) -> None:
    """Both SECURE-tier requests receive exact-edition seats: the E-SUITE-P pair for R-3 and an E-CORE-P for R-4."""
    report = run_cli(tmp_path)
    rows = {a["requestId"]: a for a in report["allocations"]}
    assert rows["R-3"] == {"requestId": "R-3", "edition": "E-SUITE-P", "seatIds": ["S-105", "S-115"]}
    assert rows["R-4"] == {"requestId": "R-4", "edition": "E-CORE-P", "seatIds": ["S-106"]}


def test_default_priority_sum_decides_between_equal_fill_plans(tmp_path: Path) -> None:
    """Filling R-6 and R-14 (priorities 2 and 4) beats same-size plans that fill R-2 or R-8."""
    report = run_cli(tmp_path)
    rows = {a["requestId"]: a["seatIds"] for a in report["allocations"]}
    assert rows["R-6"] == ["S-108"]
    assert "R-8" not in rows
    assert report["summary"]["prioritySum"] == 7


def test_default_unused_excludes_suspended_and_expired(tmp_path: Path) -> None:
    """unusedSeats lists usable leftovers only; suspended and expired seats never appear."""
    report = run_cli(tmp_path)
    assert report["unusedSeats"] == ["S-102", "S-104", "S-107"]


def test_default_cancel_fixpoint_restores_request_r7(tmp_path: Path) -> None:
    """e13 cancels the cancel e11, so R-7 stands, is filled, and e11 reports cancelled."""
    report = run_cli(tmp_path)
    events = {row["id"]: row for row in report["events"]}
    assert events["e10"] == {
        "id": "e10",
        "type": "request",
        "decision": "request-accepted",
        "requestId": "R-7",
        "edition": "E-DATA-P",
    }
    assert events["e11"] == {
        "id": "e11",
        "type": "cancel",
        "decision": "cancelled",
        "cancelledBy": ["e13"],
    }
    assert events["e13"] == {
        "id": "e13",
        "type": "cancel",
        "decision": "cancel-applied",
        "target": "e11",
    }
    rows = {a["requestId"]: a["seatIds"] for a in report["allocations"]}
    assert rows["R-7"] == ["S-112"]
    assert events["e17"]["decision"] == "request-accepted"
    assert events["e17a"] == {
        "id": "e17a",
        "type": "cancel",
        "decision": "cancelled",
        "cancelledBy": ["e17b"],
    }
    assert rows["R-12"] == ["S-101"]


def test_default_event_rows_exact(tmp_path: Path) -> None:
    """Cancelled, ignored, and rejected rows match the documented field sets exactly."""
    report = run_cli(tmp_path)
    events = {row["id"]: row for row in report["events"]}
    assert events["e15"] == {
        "id": "e15",
        "type": "request",
        "decision": "cancelled",
        "cancelledBy": ["e16"],
    }
    assert events["e12"] == {
        "id": "e12",
        "type": "cancel",
        "decision": "cancel-ignored",
        "target": "e3",
        "reason": "invalid-target",
    }
    assert events["e8"] == {
        "id": "e8",
        "type": "request",
        "decision": "rejected",
        "requestId": "R-5",
        "reason": "unknown-edition",
    }
    assert events["e6"] == {
        "id": "e6",
        "type": "restore",
        "decision": "restore-applied",
        "suspendId": "e5",
    }
    assert events["e19"] == {
        "id": "e19",
        "type": "cancel",
        "decision": "cancel-ignored",
        "target": "zzz",
        "reason": "invalid-target",
    }


def test_default_active_until_horizon_shapes_eligibility(tmp_path: Path) -> None:
    """R-6 and R-15 carry activeUntil dates that push them off the earliest-covering seats."""
    report = run_cli(tmp_path)
    rows = {a["requestId"]: a["seatIds"] for a in report["allocations"]}
    assert rows["R-6"] == ["S-108"]
    assert rows["R-15"] == ["S-103"]
    assert rows["R-1"] == ["S-113"]


def test_active_until_is_strictly_after_and_beats_earliest_cover(tmp_path: Path) -> None:
    """A seat whose coverage ends on activeUntil itself is out, and the earliest eligible seat wins instead."""
    tight = run_cli(tmp_path, [request("q1", "R-H", "E-TEAM-P", 1, activeUntil="2027-02-20")])
    assert tight["allocations"] == [
        {"requestId": "R-H", "edition": "E-TEAM-P", "seatIds": ["S-112"]}
    ]
    exact_boundary = run_cli(tmp_path, [request("q1", "R-H", "E-TEAM-P", 1, activeUntil="2027-03-07")])
    assert exact_boundary["allocations"] == [
        {"requestId": "R-H", "edition": "E-TEAM-P", "seatIds": ["S-107"]}
    ]


def test_events_list_one_row_per_feed_line_in_input_order(tmp_path: Path) -> None:
    """The events list carries exactly one row per feed line, in feed order."""
    report = run_cli(tmp_path)
    assert [row["id"] for row in report["events"]] == [
        "e1", "e2", "e3", "e4", "e5", "e6", "e7", "e8", "e9", "e10",
        "e11", "e12", "e13", "e14", "e15", "e16", "e17", "e17a", "e17b",
        "e18", "e19", "e22",
    ]
    for row in report["events"]:
        assert list(row)[:3] == ["id", "type", "decision"]


def test_suspend_for_unknown_seat_is_rejected(tmp_path: Path) -> None:
    """A suspend naming a seat outside the inventory is rejected and suspends nothing."""
    report = run_cli(
        tmp_path,
        [
            {"id": "h1", "type": "suspend", "seatId": "S-999", "reason": "typo"},
            request("q1", "R-K", "E-DATA", 1),
        ],
    )
    events = {row["id"]: row for row in report["events"]}
    assert events["h1"] == {
        "id": "h1",
        "type": "suspend",
        "decision": "rejected",
        "reason": "unknown-seat",
        "seatId": "S-999",
    }
    assert report["summary"]["rejectedEvents"] == 1
    assert report["summary"]["suspendedSeats"] == 0
    assert report["allocations"] == [
        {"requestId": "R-K", "edition": "E-DATA", "seatIds": ["S-101"]}
    ]


def test_applied_suspend_event_row_carries_seat_id(tmp_path: Path) -> None:
    """A successful suspend is reported as a suspend-applied row carrying exactly the seatId."""
    report = run_cli(tmp_path, [suspend("h1", "S-104")])
    events = {row["id"]: row for row in report["events"]}
    assert events["h1"] == {
        "id": "h1",
        "type": "suspend",
        "decision": "suspend-applied",
        "seatId": "S-104",
    }
    assert report["summary"]["suspendedSeats"] == 1
    assert "S-104" not in report["unusedSeats"]


def test_triple_cancel_chain_cancels_request_again(tmp_path: Path) -> None:
    """A chain of three cancels settles with the request cancelled by the first cancel."""
    report = run_cli(
        tmp_path,
        [
            request("q1", "R-X", "E-TEAM-P", 1),
            cancel("c1", "q1"),
            cancel("c2", "c1"),
            cancel("c3", "c2"),
        ],
    )
    events = {row["id"]: row for row in report["events"]}
    assert events["q1"] == {
        "id": "q1",
        "type": "request",
        "decision": "cancelled",
        "cancelledBy": ["c1"],
    }
    assert events["c2"] == {"id": "c2", "type": "cancel", "decision": "cancelled", "cancelledBy": ["c3"]}
    assert report["allocations"] == []
    assert report["summary"]["requestCount"] == 0
    assert report["summary"]["cancelledRequests"] == 1


def test_even_cancel_chain_restores_request(tmp_path: Path) -> None:
    """A cancel of a cancel leaves the request standing and fillable."""
    report = run_cli(
        tmp_path,
        [request("q1", "R-X", "E-TEAM-P", 1), cancel("c1", "q1"), cancel("c2", "c1")],
    )
    events = {row["id"]: row for row in report["events"]}
    assert events["q1"]["decision"] == "request-accepted"
    assert report["allocations"] == [
        {"requestId": "R-X", "edition": "E-TEAM-P", "seatIds": ["S-113"]}
    ]
    assert report["summary"]["cancelledRequests"] == 0


def test_multi_suspend_requires_every_restore(tmp_path: Path) -> None:
    """A seat with two suspensions stays out after one restore and returns after both."""
    one_restore = run_cli(
        tmp_path,
        [
            suspend("h1", "S-102"),
            suspend("h2", "S-102"),
            {"id": "r1", "type": "restore", "suspendId": "h1"},
        ],
    )
    assert one_restore["summary"]["suspendedSeats"] == 1
    assert "S-102" not in one_restore["unusedSeats"]
    both_restored = run_cli(
        tmp_path,
        [
            suspend("h1", "S-102"),
            suspend("h2", "S-102"),
            {"id": "r1", "type": "restore", "suspendId": "h1"},
            {"id": "r2", "type": "restore", "suspendId": "h2"},
        ],
    )
    assert both_restored["summary"]["suspendedSeats"] == 0
    assert "S-102" in both_restored["unusedSeats"]


def test_restore_without_active_suspension_is_ignored(tmp_path: Path) -> None:
    """A restore naming an unknown or already-restored suspension changes nothing."""
    report = run_cli(
        tmp_path,
        [
            suspend("h1", "S-104"),
            {"id": "r1", "type": "restore", "suspendId": "h1"},
            {"id": "r2", "type": "restore", "suspendId": "h1"},
            {"id": "r3", "type": "restore", "suspendId": "zzz"},
        ],
    )
    events = {row["id"]: row for row in report["events"]}
    assert events["r1"]["decision"] == "restore-applied"
    assert events["r2"] == {
        "id": "r2",
        "type": "restore",
        "decision": "restore-ignored",
        "suspendId": "h1",
        "reason": "no-active-suspension",
    }
    assert events["r3"]["decision"] == "restore-ignored"


def test_late_cancel_removes_earlier_request(tmp_path: Path) -> None:
    """A cancel after the request still removes it from allocation and requestCount."""
    report = run_cli(tmp_path, [request("q1", "R-X", "E-TEAM-P", 1), cancel("c1", "q1")])
    events = {row["id"]: row for row in report["events"]}
    assert events["q1"] == {
        "id": "q1",
        "type": "request",
        "decision": "cancelled",
        "cancelledBy": ["c1"],
    }
    assert report["allocations"] == []
    assert report["summary"]["requestCount"] == 0
    assert report["summary"]["cancelledRequests"] == 1


def test_coverage_expiry_is_strict_and_expired_seat_never_fits(tmp_path: Path) -> None:
    """S-109's coverage ends on the allocation date itself, so a lone E-DATA request gets S-101 instead."""
    report = run_cli(tmp_path, [request("q1", "R-B", "E-DATA", 1)])
    assert report["allocations"] == [
        {"requestId": "R-B", "edition": "E-DATA", "seatIds": ["S-101"]}
    ]
    assert report["summary"]["expiredSeats"] == 2
    assert "S-109" not in report["unusedSeats"]


def test_exact_edition_tier_restricts_but_only_for_listed_tiers(tmp_path: Path) -> None:
    """With every E-CORE-P seat suspended, a SECURE E-CORE-P request goes unfilled while a plain one takes an E-CORE seat."""
    report = run_cli(
        tmp_path,
        [
            suspend("h1", "S-106"),
            suspend("h2", "S-107"),
            suspend("h3", "S-112"),
            request("q1", "R-N", "E-CORE-P", 1, tier="SECURE"),
            request("q2", "R-P", "E-CORE-P", 1),
        ],
    )
    assert report["allocations"] == [
        {"requestId": "R-P", "edition": "E-CORE-P", "seatIds": ["S-101"]}
    ]
    assert report["summary"]["unfilledRequests"] == 1


def test_whole_demand_or_nothing(tmp_path: Path) -> None:
    """A request needing more matching seats than the inventory holds is left unfilled."""
    report = run_cli(tmp_path, [request("q1", "R-W", "E-SUITE", 5)])
    assert report["allocations"] == []
    assert report["summary"]["unfilledRequests"] == 1
    assert "S-101" in report["unusedSeats"]
    assert "S-114" in report["unusedSeats"]


def test_two_seat_fill_uses_earliest_covering_pair(tmp_path: Path) -> None:
    """A lone E-SUITE request for two seats takes the two earliest-covering seats it can accept."""
    report = run_cli(tmp_path, [request("q1", "R-W", "E-SUITE", 2)])
    assert report["allocations"] == [
        {"requestId": "R-W", "edition": "E-SUITE", "seatIds": ["S-101", "S-113"]}
    ]
    assert report["summary"]["allocatedSeats"] == 2


def test_reservation_case_from_contract(tmp_path: Path) -> None:
    """With only S-101 and S-102 usable, the E-TEAM-P request takes S-102 so E-DATA can take S-101."""
    held = ["S-103", "S-104", "S-105", "S-106", "S-107", "S-108", "S-112", "S-113", "S-114", "S-115"]
    suspensions = [suspend(f"h{i}", seat) for i, seat in enumerate(held, start=1)]
    report = run_cli(
        tmp_path,
        suspensions + [request("q1", "R-A", "E-TEAM-P", 1), request("q2", "R-B", "E-DATA", 1)],
    )
    assert report["allocations"] == [
        {"requestId": "R-A", "edition": "E-TEAM-P", "seatIds": ["S-102"]},
        {"requestId": "R-B", "edition": "E-DATA", "seatIds": ["S-101"]},
    ]


def test_priority_sum_breaks_fill_count_tie(tmp_path: Path) -> None:
    """When only one of two E-CORE requests can be filled, the higher-priority later one wins."""
    report = run_cli(
        tmp_path,
        [request("q1", "R-P1", "E-CORE", 1), request("q2", "R-P2", "E-CORE", 1, priority=3)],
    )
    assert report["allocations"] == [
        {"requestId": "R-P2", "edition": "E-CORE", "seatIds": ["S-101"]}
    ]
    assert report["summary"]["prioritySum"] == 3
    assert report["summary"]["unfilledRequests"] == 1


def test_feed_order_wins_when_priorities_tie(tmp_path: Path) -> None:
    """With equal priorities the earlier E-CORE request is the one that is filled."""
    report = run_cli(
        tmp_path,
        [
            request("q1", "R-P1", "E-CORE", 1, priority=2),
            request("q2", "R-P2", "E-CORE", 1, priority=2),
        ],
    )
    assert report["allocations"] == [
        {"requestId": "R-P1", "edition": "E-CORE", "seatIds": ["S-101"]}
    ]


def test_final_tie_breaker_assigns_per_request_sorted_seats(tmp_path: Path) -> None:
    """Same requests, same fitted seats: the per-request assignment tie-breaker decides."""
    held = ["S-101", "S-106", "S-107", "S-108", "S-112", "S-113"]
    suspensions = [suspend(f"h{i}", seat) for i, seat in enumerate(held, start=1)]
    report = run_cli(
        tmp_path,
        suspensions + [request("q1", "R-T1", "E-TEAM-P", 1), request("q2", "R-T2", "E-TEAM-P", 1)],
    )
    assert report["allocations"] == [
        {"requestId": "R-T1", "edition": "E-TEAM-P", "seatIds": ["S-102"]},
        {"requestId": "R-T2", "edition": "E-TEAM-P", "seatIds": ["S-103"]},
    ]
    assert report["summary"]["filledRequests"] == 2
    assert report["summary"]["allocatedSeats"] == 2


def test_multi_cancel_lists_all_active_cancel_ids_sorted(tmp_path: Path) -> None:
    """A request hit by several cancels reports every active cancel id, sorted."""
    report = run_cli(
        tmp_path,
        [
            request("q1", "R-M", "E-DATA-P", 1),
            cancel("c9", "q1"),
            cancel("c2", "q1"),
            cancel("c5", "q1"),
            cancel("k1", "c5"),
        ],
    )
    events = {row["id"]: row for row in report["events"]}
    assert events["q1"] == {
        "id": "q1",
        "type": "request",
        "decision": "cancelled",
        "cancelledBy": ["c2", "c9"],
    }
    assert events["c5"] == {
        "id": "c5",
        "type": "cancel",
        "decision": "cancelled",
        "cancelledBy": ["k1"],
    }
    assert events["c9"]["decision"] == "cancel-applied"
    assert events["c2"]["decision"] == "cancel-applied"
    assert report["allocations"] == []
    assert report["summary"]["cancelledRequests"] == 1
    assert report["summary"]["requestCount"] == 0


def test_lone_request_takes_earliest_covering_seat(tmp_path: Path) -> None:
    """With nothing else competing, an E-TEAM-P request receives the earliest-covering eligible seat."""
    report = run_cli(tmp_path, [request("q1", "R-F", "E-TEAM-P", 1)])
    assert report["allocations"] == [
        {"requestId": "R-F", "edition": "E-TEAM-P", "seatIds": ["S-113"]}
    ]


def test_priority_sum_counts_filled_requests_only(tmp_path: Path) -> None:
    """An unfilled priority request contributes nothing to prioritySum."""
    report = run_cli(
        tmp_path,
        [
            request("q1", "R-P1", "E-DATA", 1, priority=1),
            request("q2", "R-P2", "E-SUITE", 5, priority=5),
        ],
    )
    assert report["summary"]["prioritySum"] == 1
    assert report["summary"]["unfilledRequests"] == 1


def test_cli_creates_output_directory_for_custom_feed(tmp_path: Path) -> None:
    """A custom feed path writes into a missing nested directory and still uses /app/data inventory."""
    report = run_cli(tmp_path, [request("q1", "R-C", "E-SUITE-P", 1)])
    assert (tmp_path / "nested" / "out" / "allocation.json").exists()
    assert report["allocations"] == [
        {"requestId": "R-C", "edition": "E-SUITE-P", "seatIds": ["S-113"]}
    ]


def test_parse_module_exports(tmp_path: Path) -> None:
    """license/parse.js exports readFeed and parseLine with documented behavior."""
    script = (
        "const {readFeed, parseLine} = require('/app/license/parse');"
        "const events = readFeed('{\"id\":\"a\",\"type\":\"suspend\"}\\n\\n{\"id\":\"b\",\"type\":\"cancel\"}\\n');"
        "console.log(JSON.stringify([events.length, events[1].id, parseLine('{\"id\":\"c\",\"type\":\"request\"}').type]));"
    )
    proc = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == [2, "b", "request"]


def test_entitlement_module_applies_exact_edition_tiers(tmp_path: Path) -> None:
    """license/entitlement.js filters by the matrix normally and exactly for exactEditionTiers."""
    script = (
        "const {eligibleSeats} = require('/app/license/entitlement');"
        "const rules = JSON.parse(require('fs').readFileSync('/app/data/entitlements.json','utf8'));"
        "const config = JSON.parse(require('fs').readFileSync('/app/data/station_config.json','utf8'));"
        "const seats = [{seatId:'X1',edition:'E-CORE-P'},{seatId:'X2',edition:'E-CORE'}];"
        "const plain = eligibleSeats({edition:'E-CORE-P',seatsNeeded:1}, seats, rules, config).map(s=>s.seatId);"
        "const secure = eligibleSeats({edition:'E-CORE-P',seatsNeeded:1,tier:'SECURE'}, seats, rules, config).map(s=>s.seatId);"
        "console.log(JSON.stringify([plain, secure]));"
    )
    proc = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == [["X1", "X2"], ["X1"]]


def test_allocate_module_returns_report_shape(tmp_path: Path) -> None:
    """license/allocate.js exports planAllocation returning the four-key report object."""
    script = (
        "const {planAllocation} = require('/app/license/allocate');"
        "const fs = require('fs');"
        "const inventory = JSON.parse(fs.readFileSync('/app/data/seat_inventory.json','utf8'));"
        "const rules = JSON.parse(fs.readFileSync('/app/data/entitlements.json','utf8'));"
        "const config = JSON.parse(fs.readFileSync('/app/data/station_config.json','utf8'));"
        "const report = planAllocation([{id:'q1',type:'request',requestId:'R-Z',edition:'E-DATA',seatsNeeded:1}], inventory, rules, config);"
        "console.log(JSON.stringify([Object.keys(report), report.allocations]));"
    )
    proc = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    keys, allocations = json.loads(proc.stdout)
    assert keys == ["events", "allocations", "unusedSeats", "summary"]
    assert allocations == [{"requestId": "R-Z", "edition": "E-DATA", "seatIds": ["S-101"]}]
