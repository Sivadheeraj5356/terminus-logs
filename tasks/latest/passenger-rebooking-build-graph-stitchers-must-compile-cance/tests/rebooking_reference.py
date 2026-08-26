"""Independent passenger rebooking reference for passenger-rebooking-engine tests."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

APP = Path("/app")


def data_dir() -> Path:
    override = os.environ.get("TB3_DATA_DIR", "")
    if override.startswith("/"):
        return Path(override)
    return APP / "data"


def state_dir() -> Path:
    override = os.environ.get("TB3_STATE_DIR", "")
    if override.startswith("/"):
        return Path(override)
    return APP / "state"


def output_dir() -> Path:
    override = os.environ.get("TB3_OUTPUT_DIR", "")
    if override.startswith("/"):
        return Path(override)
    return APP / "output"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_bundle(root: Path) -> dict[str, Any]:
    return {
        "passengers": _read_json(root / "passengers.json")["passengers"],
        "cancellations": _read_json(root / "flight-cancellations.json")["cancellations"],
        "flights": _read_json(root / "seat-inventory.json")["flights"],
        "alliances": _read_json(root / "alliance-agreements.json"),
        "policy": _read_json(root / "airline-policies.json"),
    }


def sort_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: sort_keys(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [sort_keys(v) for v in value]
    return value


def fingerprint(body: Any) -> str:
    import hashlib

    canonical = json.dumps(sort_keys(body), separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def collapse_cancellations(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for e in events:
        fid = e["flight_id"]
        cur = best.get(fid)
        if cur is None or e["revision"] > cur["revision"] or (
            e["revision"] == cur["revision"] and e["event_id"] < cur["event_id"]
        ):
            best[fid] = e
    out = list(best.values())
    out.sort(key=lambda x: (x["recorded_utc"], x["event_id"]))
    return out


def priority_score(pax: dict[str, Any], policy: dict[str, Any]) -> int:
    lw = policy["priority_weight"]["loyalty"][pax["loyalty_tier"]]
    fw = policy["priority_weight"]["fare_class"][pax["fare_class"]]
    return lw + fw


def pick_mode(policy: dict[str, Any]) -> str:
    if policy.get("priority_pick_mode") == "manifest_passenger_order":
        return "manifest_passenger_order"
    return "priority_score"


def alliance_ok(orig: str, repl: str, alliances: dict[str, Any]) -> bool:
    if orig == repl:
        return True
    partners = alliances.get("carriers", {}).get(orig, {}).get("partners", [])
    return repl in partners


def leg_fare(leg: dict[str, Any], pax: dict[str, Any]) -> str:
    return leg.get("fare_class") or pax["fare_class"]


def fare_ok(orig: str, repl: str, policy: dict[str, Any]) -> bool:
    ranks = policy["fare_class_rank"]
    orank = ranks[orig]
    rrank = ranks[repl]
    if rrank == orank:
        return True
    if rrank < orank:
        return False
    if policy.get("upgrade_on_cancel") and rrank - orank <= policy.get("max_fare_upgrade_steps", 0):
        return True
    return False


def connection_ok(repl_arrival: str, next_dep: str, policy: dict[str, Any]) -> bool:
    from datetime import datetime, timedelta

    arr = datetime.fromisoformat(repl_arrival.replace("Z", "+00:00"))
    dep = datetime.fromisoformat(next_dep.replace("Z", "+00:00"))
    mins = policy["connection_protection_minutes"]
    return arr + timedelta(minutes=mins) <= dep


def build_candidates(leg: dict[str, Any], cancel: dict[str, Any], flights: dict[str, Any]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []

    def add(fid: str, carrier: str, fc: str) -> None:
        key = f"{fid}:{fc}"
        if key in seen or fid not in flights:
            return
        seen.add(key)
        f = flights[fid]
        out.append(
            {
                "flight_id": fid,
                "carrier": carrier,
                "fare_class": fc,
                "departure_utc": f["departure_utc"],
                "arrival_utc": f["arrival_utc"],
            }
        )

    for opt in cancel["replacement_pool"]:
        add(opt["flight_id"], opt["carrier"], opt["fare_class"])
    for f in flights.values():
        if f["origin"] == leg["origin"] and f["destination"] == leg["destination"]:
            for fc in f["inventory"]:
                add(f["flight_id"], f["carrier"], fc)
    out.sort(key=lambda x: (x["flight_id"], x["fare_class"]))
    return out


def disruption_date(collapsed: list[dict[str, Any]]) -> str:
    if not collapsed:
        return "1970-01-01"
    latest = max(c["recorded_utc"] for c in collapsed)
    return latest[:10]


def stage_bundle(bundle: dict[str, Any], stage_sequence: int = 1) -> tuple[dict[str, Any], dict[str, Any]]:
    collapsed = collapse_cancellations(bundle["cancellations"])
    cancel_by_flight = {c["flight_id"]: c for c in collapsed}
    cancelled = set(cancel_by_flight)
    cancelled_flights = sorted(cancelled)

    flights = {f["flight_id"]: f for f in bundle["flights"]}
    remaining: dict[str, dict[str, int]] = {
        fid: copy.deepcopy(f["inventory"]) for fid, f in flights.items()
    }

    passengers = list(bundle["passengers"])
    if pick_mode(bundle["policy"]) == "priority_score":
        passengers.sort(
            key=lambda p: (-priority_score(p, bundle["policy"]), p["passenger_id"])
        )

    records: list[dict[str, Any]] = []
    auto_rebooked: list[str] = []

    for pax in passengers:
        score = priority_score(pax, bundle["policy"])
        rebooked: list[dict[str, Any]] = []
        affected = False
        legs = sorted(pax["itinerary"], key=lambda x: x["leg_seq"])

        for leg in legs:
            if leg["flight_id"] not in cancelled:
                continue
            affected = True
            cancel = cancel_by_flight[leg["flight_id"]]
            orig_fare = leg_fare(leg, pax)
            cands = build_candidates(leg, cancel, flights)
            next_leg = next((nxt for nxt in legs if nxt["leg_seq"] == leg["leg_seq"] + 1), None)

            assigned = False
            for cand in cands:
                if not alliance_ok(leg["carrier"], cand["carrier"], bundle["alliances"]):
                    continue
                if not fare_ok(orig_fare, cand["fare_class"], bundle["policy"]):
                    continue
                if next_leg is not None and not connection_ok(
                    cand["arrival_utc"], next_leg["departure_utc"], bundle["policy"]
                ):
                    continue
                if remaining[cand["flight_id"]][cand["fare_class"]] <= 0:
                    continue
                remaining[cand["flight_id"]][cand["fare_class"]] -= 1
                rebooked.append(
                    {
                        "leg_seq": leg["leg_seq"],
                        "original_flight": leg["flight_id"],
                        "replacement_flight": cand["flight_id"],
                        "carrier": cand["carrier"],
                        "fare_class": cand["fare_class"],
                        "departure_utc": cand["departure_utc"],
                        "arrival_utc": cand["arrival_utc"],
                    }
                )
                assigned = True
                break
            if not assigned:
                pass

        if not affected:
            status = "unaffected"
        else:
            all_ok = all(
                any(rb["leg_seq"] == leg["leg_seq"] for rb in rebooked)
                for leg in legs
                if leg["flight_id"] in cancelled
            )
            if all_ok and rebooked:
                status = "rebooked"
                auto_rebooked.append(pax["passenger_id"])
            else:
                status = "standby"

        records.append(
            {
                "passenger_id": pax["passenger_id"],
                "status": status,
                "priority_score": score,
                "rebooked_legs": rebooked,
            }
        )

    pruned: dict[str, dict[str, int]] = {}
    for fid, classes in remaining.items():
        inner = {fc: n for fc, n in classes.items() if n > 0}
        if inner:
            pruned[fid] = inner

    snap_body = {
        "snapshot_version": 1,
        "disruption_date": disruption_date(collapsed),
        "collapsed_cancellation_count": len(collapsed),
        "auto_rebooked_passenger_ids": sorted(auto_rebooked),
        "passenger_records": records,
        "remaining_seats": pruned,
        "cancelled_flights": cancelled_flights,
    }
    snap = dict(snap_body)
    snap["snapshot_fingerprint"] = fingerprint(snap_body)

    digest_body = {
        "passengers": bundle["passengers"],
        "cancellations": bundle["cancellations"],
        "flights": bundle["flights"],
        "alliances": bundle["alliances"],
        "policy": bundle["policy"],
    }
    led = {
        "ledger_version": 1,
        "input_digest": fingerprint(digest_body),
        "stage_sequence": stage_sequence,
        "priority_pick_mode": pick_mode(bundle["policy"]),
        "remaining_seat_map": pruned,
    }
    return snap, led


def export_outputs(snap: dict[str, Any], led: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    entries = []
    for i, rec in enumerate(snap["passenger_records"], start=1):
        entries.append(
            {
                "passenger_id": rec["passenger_id"],
                "status": rec["status"],
                "priority_score": rec["priority_score"],
                "rebooked_legs": rec["rebooked_legs"],
                "rebook_rank": i,
            }
        )
    plan_body = {"entries": entries}
    plan = {
        "plan_version": 1,
        "plan_fingerprint": fingerprint(plan_body),
        "ledger_stage_sequence": led["stage_sequence"],
        "entries": entries,
    }
    rebooked = sum(1 for r in snap["passenger_records"] if r["status"] == "rebooked")
    standby = sum(1 for r in snap["passenger_records"] if r["status"] == "standby")
    unaffected = sum(1 for r in snap["passenger_records"] if r["status"] == "unaffected")
    summary = {
        "summary_version": 1,
        "disruption_date": snap["disruption_date"],
        "total_passengers": len(snap["passenger_records"]),
        "rebooked_count": rebooked,
        "standby_count": standby,
        "unaffected_count": unaffected,
        "priority_pick_mode": led["priority_pick_mode"],
        "cancelled_flight_list": snap["cancelled_flights"],
    }
    return plan, summary


def build_outputs(root: Path | None = None, stage_sequence: int = 1) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    bundle = load_bundle(root or data_dir())
    snap, led = stage_bundle(bundle, stage_sequence=stage_sequence)
    plan, summary = export_outputs(snap, led)
    return snap, led, plan, summary
