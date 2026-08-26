"""Verifier for the transit fare closeout outputs."""

import csv
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest


OUTPUT_CSV = Path("/app/output/rider-day-settlement.csv")
OUTPUT_JSON = Path("/app/output/settlement-summary.json")
OUTPUT_ROUTE_LEDGER = Path("/app/output/route-family-ledger.csv")
OUTPUT_TAP_AUDIT = Path("/app/output/tap-audit-ledger.csv")
OUTPUT_ACCOUNT_LEDGER = Path("/app/output/account-cap-ledger.csv")
OUTPUT_DIR = Path("/app/output")
APP_DIR = Path("/app")
RECONCILE_SCRIPT = Path("/app/reconcile.js")
DB_PATH = Path("/app/contracts/fare_policy.sqlite")
CSV_HEADER = [
    "service_date",
    "rider_id",
    "total_charged_cents",
    "tap_count",
    "distinct_routes",
    "capping_applied",
    "pass_credit_cents",
    "disruption_credit_cents",
    "subsidy_credit_cents",
    "exception_credit_cents",
    "hold_credit_cents",
    "carryover_credit_cents",
    "account_cap_credit_cents",
    "account_credit_cents",
    "adjustment_cents",
    "unresolved_count",
]
ROUTE_LEDGER_HEADER = [
    "service_date",
    "rider_id",
    "route_family",
    "base_charged_cents",
    "express_charged_cents",
    "cap_credit_cents",
    "account_cap_credit_cents",
    "account_credit_cents",
    "tap_count",
]
ACCOUNT_LEDGER_HEADER = [
    "service_date",
    "account_id",
    "service_zone",
    "base_before_account_cap_cents",
    "account_cap_cents",
    "account_cap_credit_cents",
    "participating_rider_days",
]
TAP_AUDIT_HEADER = [
    "tap_id",
    "service_date",
    "original_tapped_at",
    "tapped_at",
    "original_rider_id",
    "rider_id",
    "original_route_id",
    "route_id",
    "original_station_id",
    "station_id",
    "original_device_status",
    "device_status",
    "unresolved_reason",
    "route_family",
    "base_after_discount_cents",
    "transfer_credit_cents",
    "pass_credit_cents",
    "disruption_credit_cents",
    "subsidy_credit_cents",
    "exception_credit_cents",
    "base_before_cap_cents",
    "express_before_cap_cents",
]
SUMMARY_KEYS = [
    "service_dates",
    "rider_day_count",
    "total_charged_cents",
    "total_pass_credit_cents",
    "total_disruption_credit_cents",
    "total_subsidy_credit_cents",
    "total_exception_credit_cents",
    "total_hold_credit_cents",
    "total_carryover_credit_cents",
    "total_account_cap_credit_cents",
    "total_account_credit_cents",
    "total_adjustment_cents",
    "capped_rider_days",
    "account_capped_groups",
    "total_fareable_taps",
    "corrected_tap_count",
    "unresolved_by_reason",
    "unresolved_events",
]

EXPECTED_HASHES = {
    "/app/contracts/fare_policy.sqlite": "60042b53c43bac10e36a820573396c57b8321a7d785f7a4270ab08397fc12d92",
    "/app/data/corrections/tap-corrections-may.jsonl": "d00e4d06920dcfc3f29e80f9d59da1c510db08fe3ebaf6014d04b40f0331a42c",
    "/app/data/carryovers/carryovers-may.jsonl": "c4de237d3d191473f6769b17667ad43ed54e805a33b58abb2ade9c3f11fdb1a0",
    "/app/data/minimums/route-family-minimums-may.csv": "6b686a097698a28a9a9522b7e6c8bdb490ac18872bb8eaf31a11342fda16a355",
    "/app/data/cap-exclusions/cap-exclusions-may.jsonl": "a39e2583f6a175baf567ec60a13bec306c4e74c000210759dd1b5726f827f0ce",
    "/app/data/accounts/account-links-may.csv": "d664411e4b1e71a0111a1029d9bb99bc70565d001f308234b023e15081c0dd46",
    "/app/data/account-credits/account-credits-may.jsonl": "89b5a7b457afae8eb202eecb41c4b98fc3a0c2adb26e38b97f9ab5ba9bf49b86",
    "/app/data/credit-reversals/credit-reversals-may.jsonl": "4c35ddbc1160c6df4c75c4bec8d4facce3dd7c4a046b159e1439e025b7135957",
    "/app/data/adjustments/adjustments-central.jsonl": "150bafa8cf867d204bd9692de082b7dcd0da303e19253a04da018a7b3d764071",
    "/app/data/adjustments/adjustments-harbor.jsonl": "0de484e27a01338181f4f3bb42b3455d400118a15be6686a3b43378810a6dc79",
    "/app/data/adjustments/adjustments-north.jsonl": "a6cc4dd009976148eaacd5275ad4ed454045d8d3056c08917fe542c520440167",
    "/app/data/disruptions/service-disruptions-may.jsonl": "ddc46359aab18cbe49306a24501152742577ce23bddeb1f58ba2d964f03c50bc",
    "/app/data/exceptions/fare-exceptions-may.jsonl": "bfb9dd839483af12d515387495e163f4a526614f2c88728157e6c073718e3c6c",
    "/app/data/holds/settlement-holds-may.jsonl": "ab4424f2db93e597954512415e840271da9a3441c2d758f2fb5e21add0196e95",
    "/app/data/passes/pass-ledger-001.csv": "b2d5918796beccc88383f95fec6205251b1400fbba832408f4cb14fc7b20f8e5",
    "/app/data/passes/pass-ledger-002.csv": "6a0c972648adb86cd37ba34b6ad2e646fd690d49ea62cc454874e0a798a285cb",
    "/app/data/passes/pass-ledger-003.csv": "2ed88c814db7c8ba33dfb3381011b1ae8c39034ead8fbb708a7f62525dafbf31",
    "/app/data/subsidies/subsidy-ledger-may.csv": "d2da2181a3acfe9bab555ab7fc38c481e8f64591438914f0f5155ef73e4294ea",
    "/app/data/subsidy-recoveries/subsidy-recoveries-may.jsonl": "5b438130641e8a151a88447561e3ce16f4bd6b00686304535dbc9f2acea5d77e",
    "/app/data/taps/taps-2026-05-14-a.jsonl": "6f849ae29ed3413f750696c43e6cb4ac21c32d127e12b8b3bae1c8e99b158369",
    "/app/data/taps/taps-2026-05-14-b.jsonl": "2ca26e00dba34bf9169c2db245fd2c4a7d4c5d1d67c180cb300cad43a67fff8f",
    "/app/data/taps/taps-2026-05-14-c.jsonl": "4d9e95ed11c99c022fcedf17009f36de73e9d50c1f2ea720078a3a8f785cdecf",
    "/app/data/taps/taps-2026-05-14-d.jsonl": "ae6abe4738652a9dff2c29060226ffac3d53505ff72f73045ee5c088edf6356c",
    "/app/data/taps/taps-2026-05-15-a.jsonl": "af578a2fb3f692bbb2ba87d4bcd288843cedd6c31c161c46fbe7b5dca8e2f04e",
    "/app/data/taps/taps-2026-05-15-b.jsonl": "0501549685affd07f7dec30ff3bedda78d7940263c0c00e33e2a98e6727a61a1",
    "/app/data/taps/taps-2026-05-15-c.jsonl": "b441d2aeaba1889ebe54cc25cd3337944f6d840593a2ae99e081aa0a1bd59f8c",
    "/app/data/taps/taps-2026-05-16-a.jsonl": "274c4f63e7e07b9f7804ba2c59a6939811774ac7989b04b134a6d27d8fae5755",
    "/app/data/taps/taps-2026-05-16-b.jsonl": "02bb445bf758113e0a590bcb7dfa9a51e771088a844cee19b332ccbab6633674",
    "/app/data/taps/taps-2026-05-16-c.jsonl": "040531cdad0ba9665879d7b3226739e83f55bfd76ffc47131977fd7c482fac2b",
    "/app/data/taps/taps-2026-05-16-d.jsonl": "e04f40aeb6f939fffd9f4f094a4b3082b1cc0d539f3e485492222d13fcab21cd",
    "/app/data/taps/taps-2026-05-17-a.jsonl": "afe532cb2feb76b10660404aadda2b9f410914fa3c8351d2b55e6f0b9d7f1e87",
    "/app/data/taps/taps-2026-05-18-a.jsonl": "1f1e0e3b5fe584912ab7a9c2f12c65ca2c3b1e1f79acd12129f792d0a876f7aa",
    "/app/data/taps/taps-2026-05-18-b.jsonl": "7cb65a9bf2a09d5764b2ff23df972d2a82aa93bd72706bd02b84af0b1a5e0401",
    "/app/data/overrides/fare-overrides-may.csv": "076dc5f8c345847b9f9d0d36c622c51f7d54df12027d3a757c1a4b175b9b0ab8",
    "/app/data/zone-adjustments/zone-adjustments-may.csv": "4486a762d8587236d1c29e7418bc6686aec6a5555a934ccbdbee503796a70e65",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _clean_output_dir():
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _run_reconcile():
    _clean_output_dir()
    result = subprocess.run(
        ["node", str(RECONCILE_SCRIPT)],
        cwd=APP_DIR,
        text=True,
        capture_output=True,
        timeout=240,
        check=False,
    )
    assert result.returncode == 0, (
        "node /app/reconcile.js failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def _all_required_outputs_exist():
    return all(
        path.exists()
        for path in [
            OUTPUT_CSV,
            OUTPUT_ROUTE_LEDGER,
            OUTPUT_TAP_AUDIT,
            OUTPUT_ACCOUNT_LEDGER,
            OUTPUT_JSON,
        ]
    )


@pytest.fixture(scope="session", autouse=True)
def _fresh_reconcile_outputs():
    if os.environ.get("RECONCILE_ALREADY_RAN") == "1" and _all_required_outputs_exist():
        return
    _run_reconcile()


def _jsonl_records(folder: Path):
    records = []
    for path in sorted(folder.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


def _csv_records(folder: Path):
    records = []
    for path in sorted(folder.glob("*.csv")):
        with path.open(newline="") as handle:
            records.extend(csv.DictReader(handle))
    return records


def _table(name: str):
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(f"SELECT * FROM {name}")]


def _by_key(rows, key):
    return {row[key]: row for row in rows}


def _active_pass_covers(passes, rider_id, service_date, service_zone):
    return any(
        pass_row["rider_id"] == rider_id
        and pass_row["status"] == "active"
        and pass_row["active_from"] <= service_date <= pass_row["active_to"]
        and pass_row["service_zone"] in {service_zone, "all"}
        for pass_row in passes
    )


def _active_subsidy(subsidies, rider_id, service_date, service_zone):
    matches = [
        subsidy
        for subsidy in subsidies
        if subsidy["rider_id"] == rider_id
        and subsidy["status"] == "active"
        and subsidy["active_from"] <= service_date <= subsidy["active_to"]
        and subsidy["service_zone"] in {service_zone, "all"}
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda row: row["subsidy_id"])[-1]


def _subsidy_month_key(subsidy, service_date):
    return subsidy["rider_id"], subsidy["subsidy_id"], service_date[:7]


def _subsidy_recovery_usage(rows):
    usage = {}
    for row in rows:
        if row["approved"] is not True:
            continue
        key = (row["rider_id"], row["subsidy_id"], row["service_month"])
        usage[key] = usage.get(key, 0) + row["amount_cents"]
    return usage


def _credit_reversal_usage(rows):
    usage = {}
    for row in rows:
        if row["approved"] is not True:
            continue
        if row["target_kind"] == "carryover":
            key = ("carryover", row["rider_id"], row["carryover_id"])
        elif row["target_kind"] == "account_credit":
            key = ("account_credit", row["account_id"], row["credit_id"])
        else:
            continue
        usage[key] = usage.get(key, 0) + row["amount_cents"]
    return usage


def _approved_overrides_by_tap(rows):
    overrides = {}
    for row in rows:
        if row["approved"].strip().lower() != "true":
            continue
        by_action = overrides.setdefault(row["tap_id"], {})
        current = by_action.get(row["action"])
        if current is None or row["override_id"] > current["override_id"]:
            by_action[row["action"]] = row
    return overrides


def _approved_zone_adjustments_by_key(rows):
    adjustments = {}
    for row in rows:
        if row["approved"].strip().lower() != "true":
            continue
        key = (row["service_date"], row["route_id"], row["station_id"])
        adjustments.setdefault(key, []).append(row)
    return adjustments


def _effective_service_zone(adjustments, tap, route):
    matches = [
        row
        for row in adjustments.get((tap["service_date"], tap["route_id"], tap["station_id"]), [])
        if row["direction"] in {tap["direction"], "all"}
    ]
    if not matches:
        return route["service_zone"]
    selected = sorted(
        matches,
        key=lambda row: (row["direction"] == tap["direction"], row["zone_adjustment_id"]),
    )[-1]
    return selected["service_zone"]


def _approved_corrections_by_tap(rows):
    supported_fields = {"rider_id", "route_id", "station_id", "device_status", "tapped_at", "service_date"}
    corrections = {}
    for row in rows:
        if row["approved"] is not True or row["field"] not in supported_fields:
            continue
        by_field = corrections.setdefault(row["tap_id"], {})
        current = by_field.get(row["field"])
        if current is None or row["correction_id"] > current["correction_id"]:
            by_field[row["field"]] = row
    return corrections


def _apply_tap_corrections(taps, corrections):
    corrected_tap_ids = set()
    corrected_taps = []
    for tap in taps:
        updated = dict(tap)
        updated["_original"] = dict(tap)
        service_date_correction = None
        for field, correction in corrections.get(tap["tap_id"], {}).items():
            if field == "service_date":
                service_date_correction = correction
                continue
            if updated.get(field) != correction["value"]:
                updated[field] = correction["value"]
                corrected_tap_ids.add(tap["tap_id"])
        updated["service_date"] = _normalized_service_date(updated["tapped_at"])
        if service_date_correction and updated["service_date"] != service_date_correction["value"]:
            updated["service_date"] = service_date_correction["value"]
            corrected_tap_ids.add(tap["tap_id"])
        corrected_taps.append(updated)
    return corrected_taps, corrected_tap_ids


def _normalized_service_date(tapped_at):
    local_dt = datetime.fromisoformat(tapped_at)
    if local_dt.strftime("%H:%M:%S") < "03:00:00":
        local_dt -= timedelta(days=1)
    return local_dt.date().isoformat()


def _approved_exceptions_by_tap(rows):
    exceptions = {}
    for row in rows:
        if row["approved"] is not True:
            continue
        exceptions.setdefault(row["tap_id"], []).append(row)
    for tap_exceptions in exceptions.values():
        tap_exceptions.sort(key=lambda row: row["exception_id"])
    return exceptions


def _apply_exception_credits(exceptions, base_charge, express_cents):
    exception_credit = 0
    for exception in exceptions:
        remaining = int(exception["amount_cents"])
        if exception["scope"] in {"base", "both"}:
            reduction = min(base_charge, remaining)
            base_charge -= reduction
            exception_credit += reduction
            remaining -= reduction
        if remaining > 0 and exception["scope"] in {"surcharge", "both"}:
            reduction = min(express_cents, remaining)
            express_cents -= reduction
            exception_credit += reduction
    return base_charge, express_cents, exception_credit


def _approved_holds_by_family(rows):
    holds = {}
    for row in rows:
        if row["approved"] is not True:
            continue
        key = (row["service_date"], row["rider_id"], row["route_family"])
        holds.setdefault(key, []).append(row)
    for family_holds in holds.values():
        family_holds.sort(key=lambda row: row["hold_id"])
    return holds


def _apply_settlement_holds(day, holds):
    for route_family, family in day["route_families"].items():
        key = (day["service_date"], day["rider_id"], route_family)
        for hold in holds.get(key, []):
            remaining = int(hold["amount_cents"])
            hold_credit = 0
            if hold["scope"] in {"base", "both"}:
                reduction = min(family["pre_cap_base_cents"], remaining)
                family["pre_cap_base_cents"] -= reduction
                remaining -= reduction
                hold_credit += reduction
            if remaining > 0 and hold["scope"] in {"surcharge", "both"}:
                reduction = min(family["express_charged_cents"], remaining)
                family["express_charged_cents"] -= reduction
                hold_credit += reduction
            day["hold_credit_cents"] += hold_credit


def _approved_carryovers_by_rider(rows, reversals):
    carryovers = {}
    for row in rows:
        if row["approved"] is not True:
            continue
        daily_limit = row.get("daily_limit_cents")
        parsed_daily_limit = None if daily_limit in {None, "", "all"} else int(daily_limit)
        reversed_cents = reversals.get(("carryover", row["rider_id"], row["carryover_id"]), 0)
        carryovers.setdefault(row["rider_id"], []).append(
            {
                **row,
                "daily_limit_cents": parsed_daily_limit,
                "remaining_cents": max(0, int(row["amount_cents"]) - reversed_cents),
            }
        )
    for rider_carryovers in carryovers.values():
        rider_carryovers.sort(key=lambda row: (row["earned_service_date"], row["carryover_id"]))
    return carryovers


def _allocate_carryover_stage(families, amount, amount_key):
    allocations = {family["route_family"]: 0 for family in families}
    total = sum(family[amount_key] for family in families)
    credit = min(amount, total)
    if credit <= 0:
        return allocations

    remainders = []
    allocated = 0
    for family in families:
        raw_share = credit * family[amount_key]
        share = raw_share // total
        allocations[family["route_family"]] = share
        allocated += share
        remainders.append((raw_share % total, family["route_family"]))

    for _, route_family in sorted(remainders, key=lambda item: (-item[0], item[1]))[: credit - allocated]:
        allocations[route_family] += 1
    return allocations


def _matching_carryover_families(day, carryover, amount_key):
    if carryover["route_family"] == "all":
        families = day["route_families"].values()
    else:
        family = day["route_families"].get(carryover["route_family"])
        families = [] if family is None else [family]
    return sorted(
        [family for family in families if family[amount_key] > 0],
        key=lambda family: family["route_family"],
    )


def _reduce_carryover_stage(day, carryover, amount_key, date_remaining_cents):
    families = _matching_carryover_families(day, carryover, amount_key)
    if not families:
        return 0
    available = sum(family[amount_key] for family in families)
    reduction = min(carryover["remaining_cents"], date_remaining_cents, available)
    if reduction <= 0:
        return 0

    if carryover["route_family"] == "all":
        allocations = _allocate_carryover_stage(families, reduction, amount_key)
    else:
        allocations = {families[0]["route_family"]: reduction}

    applied = 0
    for family in families:
        allocated = allocations[family["route_family"]]
        family[amount_key] -= allocated
        applied += allocated
    carryover["remaining_cents"] -= applied
    day["carryover_credit_cents"] += applied
    return applied


def _apply_carryover_credits(days, carryovers):
    for day in sorted(days, key=lambda row: (row["service_date"], row["rider_id"])):
        for carryover in carryovers.get(day["rider_id"], []):
            if carryover["remaining_cents"] <= 0:
                continue
            if not (carryover["earned_service_date"] < day["service_date"] <= carryover["expires_service_date"]):
                continue

            if carryover["daily_limit_cents"] is None:
                date_remaining_cents = carryover["remaining_cents"]
            else:
                date_remaining_cents = min(carryover["remaining_cents"], carryover["daily_limit_cents"])
            if date_remaining_cents <= 0:
                continue

            if carryover["scope"] in {"base", "both"}:
                applied = _reduce_carryover_stage(day, carryover, "pre_cap_base_cents", date_remaining_cents)
                date_remaining_cents -= applied
            if (
                carryover["remaining_cents"] > 0
                and date_remaining_cents > 0
                and carryover["scope"] in {"surcharge", "both"}
            ):
                _reduce_carryover_stage(day, carryover, "express_charged_cents", date_remaining_cents)


def _approved_minimums_by_family(rows):
    minimums = {}
    for row in rows:
        if row["status"] != "active":
            continue
        key = (row["service_date"], row["rider_id"], row["route_family"])
        current = minimums.get(key)
        if current is None or row["minimum_id"] > current["minimum_id"]:
            minimums[key] = row
    return minimums


def _apply_family_minimums(days, minimums):
    for day in sorted(days, key=lambda row: (row["service_date"], row["rider_id"])):
        for route_family in sorted(day["route_families"]):
            family = day["route_families"][route_family]
            minimum = minimums.get((day["service_date"], day["rider_id"], route_family))
            if minimum is None:
                continue
            family["pre_cap_base_cents"] = max(
                family["pre_cap_base_cents"],
                int(minimum["min_base_cents"]),
            )
            family["express_charged_cents"] = max(
                family["express_charged_cents"],
                int(minimum["min_express_cents"]),
            )


def _approved_cap_exclusions_by_family(rows):
    exclusions = {}
    for row in rows:
        if row["approved"] is not True:
            continue
        key = (row["service_date"], row["rider_id"], row["route_family"])
        exclusions.setdefault(key, []).append(row)
    for family_exclusions in exclusions.values():
        family_exclusions.sort(key=lambda row: row["exclusion_id"])
    return exclusions


def _apply_cap_exclusions(days, cap_exclusions):
    for day in sorted(days, key=lambda row: (row["service_date"], row["rider_id"])):
        for route_family in sorted(day["route_families"]):
            family = day["route_families"][route_family]
            for exclusion in cap_exclusions.get((day["service_date"], day["rider_id"], route_family), []):
                eligible_base = max(0, family["pre_cap_base_cents"] - family["cap_excluded_base_cents"])
                excluded = min(eligible_base, int(exclusion["amount_cents"]))
                family["cap_excluded_base_cents"] += excluded


def _active_account_link(account_links, rider_id, service_date):
    matches = [
        link
        for link in account_links
        if link["rider_id"] == rider_id
        and link["status"] == "active"
        and link["active_from"] <= service_date <= link["active_to"]
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda row: row["account_id"])[-1]


def _allocate_account_cap_credit(families, cap_credit):
    allocations = {(row["day"]["rider_id"], row["family"]["route_family"]): 0 for row in families}
    if cap_credit <= 0:
        return allocations

    total_base = sum(row["family"]["cap_eligible_base_after_daily_cap_cents"] for row in families)
    if total_base <= 0:
        return allocations

    remainders = []
    allocated = 0
    for row in families:
        key = (row["day"]["rider_id"], row["family"]["route_family"])
        amount = row["family"]["cap_eligible_base_after_daily_cap_cents"]
        raw_share = cap_credit * amount
        share = raw_share // total_base
        allocations[key] = share
        allocated += share
        remainders.append((raw_share % total_base, key))

    for _, key in sorted(remainders, key=lambda item: (-item[0], item[1][0], item[1][1]))[: cap_credit - allocated]:
        allocations[key] += 1

    return allocations


def _apply_account_caps(days, account_links, account_caps):
    groups = {}
    for day in days:
        if day["tap_count"] <= 0:
            continue
        link = _active_account_link(account_links, day["rider_id"], day["service_date"])
        if link is None:
            continue
        key = (day["service_date"], link["account_id"])
        group = groups.setdefault(key, {"days": [], "zones": set()})
        group["days"].append(day)
        group["zones"].update(day["zones"])

    account_rows = []
    for (service_date, account_id), group in sorted(groups.items()):
        applicable_caps = [
            cap
            for cap in account_caps
            if cap["account_id"] == account_id and cap["service_zone"] in group["zones"]
        ]
        if not applicable_caps:
            continue
        selected_cap = sorted(applicable_caps, key=lambda row: (row["cap_cents"], row["service_zone"]))[-1]
        families = []
        for day in sorted(group["days"], key=lambda row: row["rider_id"]):
            for route_family in sorted(day["route_families"]):
                family = day["route_families"][route_family]
                if family["cap_eligible_base_after_daily_cap_cents"] > 0:
                    families.append({"day": day, "family": family})
        base_before_account_cap = sum(row["family"]["cap_eligible_base_after_daily_cap_cents"] for row in families)
        account_cap = int(selected_cap["cap_cents"])
        if base_before_account_cap <= account_cap:
            continue
        account_cap_credit = base_before_account_cap - account_cap
        allocations = _allocate_account_cap_credit(families, account_cap_credit)
        for row in families:
            day = row["day"]
            family = row["family"]
            key = (day["rider_id"], family["route_family"])
            allocated = allocations[key]
            family["cap_eligible_base_after_daily_cap_cents"] -= allocated
            family["base_after_daily_cap_cents"] -= allocated
            family["account_cap_credit_cents"] += allocated
            day["account_cap_credit_cents"] += allocated
        account_rows.append(
            {
                "service_date": service_date,
                "account_id": account_id,
                "service_zone": selected_cap["service_zone"],
                "base_before_account_cap_cents": str(base_before_account_cap),
                "account_cap_cents": str(account_cap),
                "account_cap_credit_cents": str(account_cap_credit),
                "participating_rider_days": str(len(group["days"])),
            }
        )
    return account_rows


def _approved_account_credits(rows, reversals):
    credits = {}
    for row in rows:
        if row["approved"] is not True:
            continue
        daily_limit = row.get("daily_limit_cents")
        if daily_limit in {None, "", "all"}:
            parsed_daily_limit = None
        else:
            parsed_daily_limit = int(daily_limit)
        reversed_cents = reversals.get(("account_credit", row["account_id"], row["credit_id"]), 0)
        credits.setdefault(row["account_id"], []).append(
            {
                **row,
                "daily_limit_cents": parsed_daily_limit,
                "remaining_cents": max(0, int(row["amount_cents"]) - reversed_cents),
            }
        )
    for account_credits in credits.values():
        account_credits.sort(key=lambda row: (row["earned_service_date"], row["credit_id"]))
    return credits


def _unrestricted_filter(value):
    return value is None or value == "" or value == "all"


def _account_credit_matches(credit, day, family):
    if not _unrestricted_filter(credit.get("rider_id")) and credit["rider_id"] != day["rider_id"]:
        return False
    if not _unrestricted_filter(credit.get("route_family")) and credit["route_family"] != family["route_family"]:
        return False
    if not _unrestricted_filter(credit.get("service_zone")) and credit["service_zone"] not in family["zones"]:
        return False
    return True


def _account_credit_families(days, amount_key, credit):
    families = []
    for day in sorted(days, key=lambda row: row["rider_id"]):
        for route_family in sorted(day["route_families"]):
            family = day["route_families"][route_family]
            if family[amount_key] > 0 and _account_credit_matches(credit, day, family):
                families.append({"day": day, "family": family})
    return families


def _allocate_account_stage_credit(families, amount, amount_key):
    allocations = {(row["day"]["rider_id"], row["family"]["route_family"]): 0 for row in families}
    if amount <= 0:
        return allocations

    total = sum(row["family"][amount_key] for row in families)
    if total <= 0:
        return allocations

    credit = min(amount, total)
    remainders = []
    allocated = 0
    for row in families:
        key = (row["day"]["rider_id"], row["family"]["route_family"])
        raw_share = credit * row["family"][amount_key]
        share = raw_share // total
        allocations[key] = share
        allocated += share
        remainders.append((raw_share % total, key))

    for _, key in sorted(remainders, key=lambda item: (-item[0], item[1][0], item[1][1]))[: credit - allocated]:
        allocations[key] += 1
    return allocations


def _reduce_account_credit_stage(days, credit, amount_key, date_remaining_cents):
    families = _account_credit_families(days, amount_key, credit)
    available = sum(row["family"][amount_key] for row in families)
    reduction = min(credit["remaining_cents"], date_remaining_cents, available)
    if reduction <= 0:
        return 0

    allocations = _allocate_account_stage_credit(families, reduction, amount_key)
    applied = 0
    for row in families:
        day = row["day"]
        family = row["family"]
        key = (day["rider_id"], family["route_family"])
        allocated = allocations[key]
        family[amount_key] -= allocated
        family["account_credit_cents"] += allocated
        day["account_credit_cents"] += allocated
        applied += allocated
    credit["remaining_cents"] -= applied
    return applied


def _apply_account_credits(days, account_links, account_credits):
    groups = {}
    for day in days:
        if day["tap_count"] <= 0:
            continue
        link = _active_account_link(account_links, day["rider_id"], day["service_date"])
        if link is None:
            continue
        key = (day["service_date"], link["account_id"])
        groups.setdefault(key, []).append(day)

    for (service_date, account_id), group_days in sorted(groups.items()):
        for credit in account_credits.get(account_id, []):
            if credit["remaining_cents"] <= 0:
                continue
            if not (credit["earned_service_date"] < service_date <= credit["expires_service_date"]):
                continue
            if credit["daily_limit_cents"] is None:
                date_remaining_cents = credit["remaining_cents"]
            else:
                date_remaining_cents = min(credit["remaining_cents"], credit["daily_limit_cents"])
            if date_remaining_cents <= 0:
                continue
            if credit["scope"] in {"base", "both"}:
                applied = _reduce_account_credit_stage(
                    group_days, credit, "base_after_daily_cap_cents", date_remaining_cents
                )
                date_remaining_cents -= applied
            if credit["remaining_cents"] > 0 and date_remaining_cents > 0 and credit["scope"] in {"surcharge", "both"}:
                _reduce_account_credit_stage(group_days, credit, "express_charged_cents", date_remaining_cents)


def _disruption_credit(disruptions, tap, route, base_charge):
    if base_charge <= 0:
        return 0
    tap_time = tap["tapped_at"][11:16]
    credit = sum(
        disruption["credit_cents"]
        for disruption in disruptions
        if disruption["approved"] is True
        and disruption["service_date"] == tap["service_date"]
        and disruption["route_family"] == route["route_family"]
        and disruption["start_time"] <= tap_time < disruption["end_time"]
    )
    return min(base_charge, credit)


def _station_pair_surcharge(station_pair_surcharges, previous, tap, route):
    if previous is None:
        return None
    matches = [
        row
        for row in station_pair_surcharges
        if row["active"] == 1
        and row["from_station_id"] == previous["station_id"]
        and row["to_station_id"] == tap["station_id"]
        and row["route_family"] == route["route_family"]
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda row: row["surcharge_id"])[-1]["amount_cents"]


def _minutes_between(first, second):
    started = datetime.fromisoformat(first)
    ended = datetime.fromisoformat(second)
    return int((ended - started).total_seconds() // 60)


def _day(days, service_date, rider_id):
    key = (service_date, rider_id)
    if key not in days:
        days[key] = {
            "service_date": service_date,
            "rider_id": rider_id,
            "base_charges": [],
            "express_cents": 0,
            "tap_count": 0,
            "distinct_routes": set(),
            "zones": set(),
            "pass_credit_cents": 0,
            "disruption_credit_cents": 0,
            "subsidy_credit_cents": 0,
            "exception_credit_cents": 0,
            "hold_credit_cents": 0,
            "carryover_credit_cents": 0,
            "account_cap_credit_cents": 0,
            "account_credit_cents": 0,
            "adjustment_cents": 0,
            "unresolved_count": 0,
            "last_fareable": None,
            "rider_type": None,
            "route_families": {},
        }
    return days[key]


def _route_family(day, route_family):
    if route_family not in day["route_families"]:
        day["route_families"][route_family] = {
            "service_date": day["service_date"],
            "rider_id": day["rider_id"],
            "route_family": route_family,
            "pre_cap_base_cents": 0,
            "cap_excluded_base_cents": 0,
            "cap_eligible_base_cents": 0,
            "cap_eligible_base_after_daily_cap_cents": 0,
            "base_after_daily_cap_cents": 0,
            "express_charged_cents": 0,
            "cap_credit_cents": 0,
            "account_cap_credit_cents": 0,
            "account_credit_cents": 0,
            "tap_count": 0,
            "zones": set(),
        }
    return day["route_families"][route_family]


def _allocate_cap_credit(route_families, cap_credit):
    allocations = {row["route_family"]: 0 for row in route_families}
    if cap_credit <= 0:
        return allocations

    total_base = sum(row["cap_eligible_base_cents"] for row in route_families)
    if total_base <= 0:
        return allocations

    remainders = []
    allocated = 0
    for row in route_families:
        raw_share = cap_credit * row["cap_eligible_base_cents"]
        share = raw_share // total_base
        allocations[row["route_family"]] = share
        allocated += share
        remainders.append((raw_share % total_base, row["route_family"]))

    for _, route_family in sorted(remainders, key=lambda item: (-item[0], item[1]))[: cap_credit - allocated]:
        allocations[route_family] += 1

    return allocations


def _tap_audit_row(
    tap,
    unresolved_reason="",
    route_family="",
    base_after_discount=0,
    transfer_credit=0,
    pass_credit=0,
    disruption_credit=0,
    subsidy_credit=0,
    exception_credit=0,
    base_before_cap=0,
    express_before_cap=0,
):
    original = tap["_original"]
    return {
        "tap_id": tap["tap_id"],
        "service_date": tap["service_date"],
        "original_tapped_at": original["tapped_at"],
        "tapped_at": tap["tapped_at"],
        "original_rider_id": original["rider_id"],
        "rider_id": tap["rider_id"],
        "original_route_id": original["route_id"],
        "route_id": tap["route_id"],
        "original_station_id": original["station_id"],
        "station_id": tap["station_id"],
        "original_device_status": original["device_status"],
        "device_status": tap["device_status"],
        "unresolved_reason": unresolved_reason,
        "route_family": route_family,
        "base_after_discount_cents": str(base_after_discount),
        "transfer_credit_cents": str(transfer_credit),
        "pass_credit_cents": str(pass_credit),
        "disruption_credit_cents": str(disruption_credit),
        "subsidy_credit_cents": str(subsidy_credit),
        "exception_credit_cents": str(exception_credit),
        "base_before_cap_cents": str(base_before_cap),
        "express_before_cap_cents": str(express_before_cap),
    }


def _expected_outputs():
    riders = _by_key(_table("riders"), "rider_id")
    discounts = _by_key(_table("rider_type_rules"), "rider_type")
    routes = _by_key(_table("routes"), "route_id")
    stations = _by_key(_table("stations"), "station_id")
    caps = _table("daily_caps")
    account_caps = _table("account_daily_caps")
    station_pair_surcharges = _table("station_pair_surcharges")
    transfer_rules = {
        (row["from_family"], row["to_family"]): row["minutes"]
        for row in _table("transfer_rules")
    }
    corrected_taps, corrected_tap_ids = _apply_tap_corrections(
        _jsonl_records(Path("/app/data/taps")),
        _approved_corrections_by_tap(_jsonl_records(Path("/app/data/corrections"))),
    )
    taps = sorted(
        corrected_taps,
        key=lambda row: (
            row["service_date"],
            row["rider_id"],
            row["tapped_at"],
            row["tap_id"],
        ),
    )
    passes = _csv_records(Path("/app/data/passes"))
    subsidies = _csv_records(Path("/app/data/subsidies"))
    subsidy_recoveries = _jsonl_records(Path("/app/data/subsidy-recoveries"))
    adjustments = _jsonl_records(Path("/app/data/adjustments"))
    disruptions = _jsonl_records(Path("/app/data/disruptions"))
    exceptions = _approved_exceptions_by_tap(_jsonl_records(Path("/app/data/exceptions")))
    holds = _approved_holds_by_family(_jsonl_records(Path("/app/data/holds")))
    credit_reversals = _credit_reversal_usage(_jsonl_records(Path("/app/data/credit-reversals")))
    carryovers = _approved_carryovers_by_rider(_jsonl_records(Path("/app/data/carryovers")), credit_reversals)
    minimums = _approved_minimums_by_family(_csv_records(Path("/app/data/minimums")))
    cap_exclusions = _approved_cap_exclusions_by_family(_jsonl_records(Path("/app/data/cap-exclusions")))
    account_links = _csv_records(Path("/app/data/accounts"))
    account_credits = _approved_account_credits(_jsonl_records(Path("/app/data/account-credits")), credit_reversals)
    overrides = _approved_overrides_by_tap(_csv_records(Path("/app/data/overrides")))
    zone_adjustments = _approved_zone_adjustments_by_key(_csv_records(Path("/app/data/zone-adjustments")))

    days = {}
    unresolved_events = []
    subsidy_usage = _subsidy_recovery_usage(subsidy_recoveries)
    audit_rows = []

    def record_unresolved(tap, reason):
        day = _day(days, tap["service_date"], tap["rider_id"])
        day["unresolved_count"] += 1
        unresolved_events.append(
            {
                "tap_id": tap["tap_id"],
                "rider_id": tap["rider_id"],
                "service_date": tap["service_date"],
                "reason": reason,
            }
        )
        audit_rows.append(_tap_audit_row(tap, unresolved_reason=reason))

    for tap in taps:
        if tap["device_status"] != "accepted":
            record_unresolved(tap, "rejected_device")
            continue

        rider = riders.get(tap["rider_id"])
        if rider is None:
            record_unresolved(tap, "unknown_rider")
            continue

        route = routes.get(tap["route_id"])
        if route is None or route["active"] != 1:
            record_unresolved(tap, "unknown_route")
            continue

        station = stations.get(tap["station_id"])
        if station is None or station["active"] != 1:
            record_unresolved(tap, "inactive_station")
            continue

        service_zone = _effective_service_zone(zone_adjustments, tap, route)
        day = _day(days, tap["service_date"], tap["rider_id"])
        day["rider_type"] = rider["rider_type"]
        day["tap_count"] += 1
        day["distinct_routes"].add(route["route_id"])
        day["zones"].add(service_zone)

        tap_overrides = overrides.get(tap["tap_id"], {})
        previous = day["last_fareable"]
        base_cents = route["base_cents"]
        if "base_override" in tap_overrides:
            base_cents = int(tap_overrides["base_override"]["amount_cents"])
        express_cents = route["express_surcharge_cents"]
        if "surcharge_override" in tap_overrides:
            express_cents = int(tap_overrides["surcharge_override"]["amount_cents"])
        station_pair_amount = _station_pair_surcharge(station_pair_surcharges, previous, tap, route)
        if station_pair_amount is not None:
            if "station_pair_surcharge_override" in tap_overrides:
                station_pair_amount = int(tap_overrides["station_pair_surcharge_override"]["amount_cents"])
            express_cents += station_pair_amount

        discount = discounts[rider["rider_type"]]["discount_percent"]
        base_after_discount = (base_cents * discount + 50) // 100
        base_charge = base_after_discount
        transfer_credit = 0
        if previous is not None:
            window = transfer_rules.get((previous["route_family"], route["route_family"]))
            if window is not None and _minutes_between(previous["tapped_at"], tap["tapped_at"]) <= window:
                transfer_credit = base_charge
                base_charge = 0

        pass_suppressed = "suppress_pass" in tap_overrides
        pass_credit = 0
        if (
            base_charge > 0
            and not pass_suppressed
            and _active_pass_covers(passes, tap["rider_id"], tap["service_date"], service_zone)
        ):
            pass_credit = base_charge
            day["pass_credit_cents"] += pass_credit
            base_charge = 0

        disruption_credit = _disruption_credit(disruptions, tap, route, base_charge)
        if disruption_credit:
            day["disruption_credit_cents"] += disruption_credit
            base_charge -= disruption_credit

        subsidy_credit = 0
        subsidy = _active_subsidy(subsidies, tap["rider_id"], tap["service_date"], service_zone)
        if base_charge > 0 and subsidy is not None:
            usage_key = _subsidy_month_key(subsidy, tap["service_date"])
            used = subsidy_usage.get(usage_key, 0)
            remaining_limit = max(0, int(subsidy["monthly_limit_cents"]) - used)
            requested_credit = (base_charge * int(subsidy["percent"]) + 50) // 100
            subsidy_credit = min(base_charge, requested_credit, remaining_limit)
            if subsidy_credit:
                day["subsidy_credit_cents"] += subsidy_credit
                subsidy_usage[usage_key] = used + subsidy_credit
                base_charge -= subsidy_credit

        base_charge, express_cents, exception_credit = _apply_exception_credits(
            exceptions.get(tap["tap_id"], []),
            base_charge,
            express_cents,
        )
        if exception_credit:
            day["exception_credit_cents"] += exception_credit

        audit_rows.append(
            _tap_audit_row(
                tap,
                route_family=route["route_family"],
                base_after_discount=base_after_discount,
                transfer_credit=transfer_credit,
                pass_credit=pass_credit,
                disruption_credit=disruption_credit,
                subsidy_credit=subsidy_credit,
                exception_credit=exception_credit,
                base_before_cap=base_charge,
                express_before_cap=express_cents,
            )
        )

        route_family = _route_family(day, route["route_family"])
        route_family["pre_cap_base_cents"] += base_charge
        route_family["express_charged_cents"] += express_cents
        route_family["tap_count"] += 1
        route_family["zones"].add(service_zone)

        day["base_charges"].append(base_charge)
        day["express_cents"] += express_cents
        day["last_fareable"] = {
            "route_family": route["route_family"],
            "station_id": tap["station_id"],
            "tapped_at": tap["tapped_at"],
        }

    for adjustment in adjustments:
        if adjustment["approved"] is not True:
            continue
        day = _day(days, adjustment["service_date"], adjustment["rider_id"])
        if day["rider_type"] is None and adjustment["rider_id"] in riders:
            day["rider_type"] = riders[adjustment["rider_id"]]["rider_type"]
        day["adjustment_cents"] += adjustment["amount_cents"]

    sorted_days = sorted(days.values(), key=lambda row: (row["service_date"], row["rider_id"]))
    for day in sorted_days:
        _apply_settlement_holds(day, holds)
    _apply_carryover_credits(sorted_days, carryovers)
    _apply_family_minimums(sorted_days, minimums)
    _apply_cap_exclusions(sorted_days, cap_exclusions)

    for day in sorted_days:
        route_families = list(day["route_families"].values())
        for family in route_families:
            family["cap_eligible_base_cents"] = max(
                0,
                family["pre_cap_base_cents"] - family["cap_excluded_base_cents"],
            )
        base_total = sum(row["cap_eligible_base_cents"] for row in route_families)
        day["express_total_cents"] = sum(row["express_charged_cents"] for row in route_families)
        capped_base = base_total
        day["capping_applied"] = False
        if day["rider_type"] and day["zones"]:
            applicable_caps = [
                cap["cap_cents"]
                for cap in caps
                if cap["rider_type"] == day["rider_type"] and cap["service_zone"] in day["zones"]
            ]
            if applicable_caps and base_total > max(applicable_caps):
                capped_base = max(applicable_caps)
                day["capping_applied"] = True
        cap_credit = base_total - capped_base
        cap_allocations = _allocate_cap_credit(route_families, cap_credit)
        for family in route_families:
            allocated_cap = cap_allocations[family["route_family"]]
            family["cap_credit_cents"] = allocated_cap
            family["cap_eligible_base_after_daily_cap_cents"] = (
                family["cap_eligible_base_cents"] - allocated_cap
            )
            family["base_after_daily_cap_cents"] = (
                family["cap_excluded_base_cents"]
                + family["cap_eligible_base_after_daily_cap_cents"]
            )

    account_cap_rows = _apply_account_caps(sorted_days, account_links, account_caps)
    _apply_account_credits(sorted_days, account_links, account_credits)

    csv_rows = []
    route_family_rows = []
    for day in sorted_days:
        base_after_account_credit = sum(
            row["base_after_daily_cap_cents"] for row in day["route_families"].values()
        )
        express_after_account_credit = sum(
            row["express_charged_cents"] for row in day["route_families"].values()
        )
        csv_rows.append(
            {
                "service_date": day["service_date"],
                "rider_id": day["rider_id"],
                "total_charged_cents": str(base_after_account_credit + express_after_account_credit + day["adjustment_cents"]),
                "tap_count": str(day["tap_count"]),
                "distinct_routes": str(len(day["distinct_routes"])),
                "capping_applied": "true" if day["capping_applied"] else "false",
                "pass_credit_cents": str(day["pass_credit_cents"]),
                "disruption_credit_cents": str(day["disruption_credit_cents"]),
                "subsidy_credit_cents": str(day["subsidy_credit_cents"]),
                "exception_credit_cents": str(day["exception_credit_cents"]),
                "hold_credit_cents": str(day["hold_credit_cents"]),
                "carryover_credit_cents": str(day["carryover_credit_cents"]),
                "account_cap_credit_cents": str(day["account_cap_credit_cents"]),
                "account_credit_cents": str(day["account_credit_cents"]),
                "adjustment_cents": str(day["adjustment_cents"]),
                "unresolved_count": str(day["unresolved_count"]),
            }
        )

        for route_family in sorted(day["route_families"]):
            family = day["route_families"][route_family]
            route_family_rows.append(
                {
                    "service_date": family["service_date"],
                    "rider_id": family["rider_id"],
                    "route_family": family["route_family"],
                    "base_charged_cents": str(family["base_after_daily_cap_cents"]),
                    "express_charged_cents": str(family["express_charged_cents"]),
                    "cap_credit_cents": str(family["cap_credit_cents"]),
                    "account_cap_credit_cents": str(family["account_cap_credit_cents"]),
                    "account_credit_cents": str(family["account_credit_cents"]),
                    "tap_count": str(family["tap_count"]),
                }
            )

    unresolved_events.sort(key=lambda row: (row["service_date"], row["tap_id"]))
    unresolved_by_reason = {}
    for event in unresolved_events:
        unresolved_by_reason[event["reason"]] = unresolved_by_reason.get(event["reason"], 0) + 1

    summary = {
        "service_dates": sorted({row["service_date"] for row in csv_rows}),
        "rider_day_count": len(csv_rows),
        "total_charged_cents": sum(int(row["total_charged_cents"]) for row in csv_rows),
        "total_pass_credit_cents": sum(int(row["pass_credit_cents"]) for row in csv_rows),
        "total_disruption_credit_cents": sum(int(row["disruption_credit_cents"]) for row in csv_rows),
        "total_subsidy_credit_cents": sum(int(row["subsidy_credit_cents"]) for row in csv_rows),
        "total_exception_credit_cents": sum(int(row["exception_credit_cents"]) for row in csv_rows),
        "total_hold_credit_cents": sum(int(row["hold_credit_cents"]) for row in csv_rows),
        "total_carryover_credit_cents": sum(int(row["carryover_credit_cents"]) for row in csv_rows),
        "total_account_cap_credit_cents": sum(int(row["account_cap_credit_cents"]) for row in csv_rows),
        "total_account_credit_cents": sum(int(row["account_credit_cents"]) for row in csv_rows),
        "total_adjustment_cents": sum(int(row["adjustment_cents"]) for row in csv_rows),
        "capped_rider_days": sum(row["capping_applied"] == "true" for row in csv_rows),
        "account_capped_groups": len(account_cap_rows),
        "total_fareable_taps": sum(int(row["tap_count"]) for row in csv_rows),
        "corrected_tap_count": len(corrected_tap_ids),
        "unresolved_by_reason": {key: unresolved_by_reason[key] for key in sorted(unresolved_by_reason)},
        "unresolved_events": unresolved_events,
    }
    return csv_rows, summary, route_family_rows, audit_rows, account_cap_rows


def _read_csv_rows():
    with OUTPUT_CSV.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    return reader.fieldnames, rows


def _read_route_family_rows():
    with OUTPUT_ROUTE_LEDGER.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    return reader.fieldnames, rows


def _read_account_cap_rows():
    with OUTPUT_ACCOUNT_LEDGER.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    return reader.fieldnames, rows


def _read_tap_audit_rows():
    with OUTPUT_TAP_AUDIT.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    return reader.fieldnames, rows


def test_raw_policy_and_input_files_are_unchanged():
    """The submitted solution must not change the raw inputs, disruption records, or policy database."""
    for filename, expected_hash in EXPECTED_HASHES.items():
        path = Path(filename)
        assert path.exists(), f"missing source file: {filename}"
        assert _sha256(path) == expected_hash, f"source file changed: {filename}"


def test_reconcile_reruns_against_verifier_owned_input_change():
    """A verifier-owned adjustment added after submission must be reflected by rerunning the script."""
    verifier_adjustment = Path("/app/data/adjustments/adjustments-verifier-owned.jsonl")
    assert not verifier_adjustment.exists(), "unexpected verifier adjustment file already exists"
    adjustment_row = {
        "adjustment_id": "A-VERIFIER-001",
        "rider_id": "R102",
        "service_date": "2026-05-19",
        "amount_cents": 37,
        "reason": "verifier rerun check",
        "approved": True,
    }

    try:
        verifier_adjustment.write_text(json.dumps(adjustment_row, separators=(",", ":")) + "\n")
        _run_reconcile()

        expected_rows, expected_summary, expected_route_rows, expected_audit_rows, expected_account_rows = (
            _expected_outputs()
        )
        _, rows = _read_csv_rows()
        _, route_rows = _read_route_family_rows()
        _, audit_rows = _read_tap_audit_rows()
        _, account_rows = _read_account_cap_rows()

        assert rows == expected_rows
        assert route_rows == expected_route_rows
        assert audit_rows == expected_audit_rows
        assert account_rows == expected_account_rows
        assert json.loads(OUTPUT_JSON.read_text()) == expected_summary
        assert any(
            row["service_date"] == "2026-05-19"
            and row["rider_id"] == "R102"
            and row["adjustment_cents"] == "37"
            and row["total_charged_cents"] == "37"
            for row in rows
        )
    finally:
        verifier_adjustment.unlink(missing_ok=True)
        _run_reconcile()


def test_required_output_files_exist_and_have_declared_format():
    """All output files must exist with exact CSV headers and the pretty JSON layout."""
    assert OUTPUT_CSV.exists(), "missing rider-day settlement CSV"
    assert OUTPUT_ROUTE_LEDGER.exists(), "missing route-family ledger CSV"
    assert OUTPUT_TAP_AUDIT.exists(), "missing tap audit ledger CSV"
    assert OUTPUT_ACCOUNT_LEDGER.exists(), "missing account cap ledger CSV"
    assert OUTPUT_JSON.exists(), "missing settlement summary JSON"
    header, rows = _read_csv_rows()
    assert header == CSV_HEADER
    assert rows, "settlement CSV has no data rows"
    route_header, route_rows = _read_route_family_rows()
    assert route_header == ROUTE_LEDGER_HEADER
    assert route_rows, "route-family ledger has no data rows"
    audit_header, audit_rows = _read_tap_audit_rows()
    assert audit_header == TAP_AUDIT_HEADER
    assert audit_rows, "tap audit ledger has no data rows"
    account_header, account_rows = _read_account_cap_rows()
    assert account_header == ACCOUNT_LEDGER_HEADER
    assert account_rows, "account cap ledger has no data rows"
    summary = json.loads(OUTPUT_JSON.read_text())
    assert list(summary.keys()) == SUMMARY_KEYS
    assert OUTPUT_JSON.read_text() == json.dumps(summary, indent=2) + "\n"


def test_rider_day_settlement_csv_matches_policy_calculation():
    """The rider-day CSV must match a fresh calculation from taps, passes, disruptions, adjustments, and policy tables."""
    _, rows = _read_csv_rows()
    expected_rows, _, _, _, _ = _expected_outputs()
    assert rows == expected_rows


def test_summary_totals_match_policy_calculation():
    """The JSON summary must aggregate the computed rider-day rows and all policy credit totals."""
    _, expected_summary, _, _, _ = _expected_outputs()
    assert json.loads(OUTPUT_JSON.read_text()) == expected_summary


def test_route_family_ledger_matches_cap_apportionment():
    """The route-family ledger must allocate daily cap credits by family using the policy tie-breaker."""
    _, rows = _read_route_family_rows()
    _, _, expected_rows, _, _ = _expected_outputs()
    assert rows == expected_rows

    _, rider_day_rows = _read_csv_rows()
    rider_day = {
        (row["service_date"], row["rider_id"]): row
        for row in rider_day_rows
    }
    assert rider_day[("2026-05-17", "R106")]["capping_applied"] == "true"
    assert rider_day[("2026-05-17", "R106")]["total_charged_cents"] == "1055"

    actual = {
        (row["service_date"], row["rider_id"], row["route_family"]): row
        for row in rows
    }
    assert actual[("2026-05-17", "R106", "crosstown")] == {
        "service_date": "2026-05-17",
        "rider_id": "R106",
        "route_family": "crosstown",
        "base_charged_cents": "168",
        "express_charged_cents": "0",
        "cap_credit_cents": "35",
        "account_cap_credit_cents": "41",
        "account_credit_cents": "56",
        "tap_count": "1",
    }
    assert actual[("2026-05-17", "R106", "express")] == {
        "service_date": "2026-05-17",
        "rider_id": "R106",
        "route_family": "express",
        "base_charged_cents": "468",
        "express_charged_cents": "100",
        "cap_credit_cents": "43",
        "account_cap_credit_cents": "49",
        "account_credit_cents": "100",
        "tap_count": "2",
    }
    assert actual[("2026-05-17", "R106", "ferry")] == {
        "service_date": "2026-05-17",
        "rider_id": "R106",
        "route_family": "ferry",
        "base_charged_cents": "89",
        "express_charged_cents": "95",
        "cap_credit_cents": "14",
        "account_cap_credit_cents": "17",
        "account_credit_cents": "0",
        "tap_count": "1",
    }
    assert actual[("2026-05-17", "R106", "local")] == {
        "service_date": "2026-05-17",
        "rider_id": "R106",
        "route_family": "local",
        "base_charged_cents": "135",
        "express_charged_cents": "0",
        "cap_credit_cents": "28",
        "account_cap_credit_cents": "33",
        "account_credit_cents": "44",
        "tap_count": "1",
    }


def test_account_level_caps_allocate_after_individual_daily_caps():
    """Account caps must aggregate linked active riders and allocate base credits by largest remainder."""
    _, rows = _read_csv_rows()
    rider_day = {(row["service_date"], row["rider_id"]): row for row in rows}
    _, account_rows = _read_account_cap_rows()
    _, _, _, _, expected_account_rows = _expected_outputs()

    assert account_rows == expected_account_rows
    assert account_rows == [
        {
            "service_date": "2026-05-14",
            "account_id": "FAM-ALPHA",
            "service_zone": "regional",
            "base_before_account_cap_cents": "730",
            "account_cap_cents": "650",
            "account_cap_credit_cents": "80",
            "participating_rider_days": "2",
        },
        {
            "service_date": "2026-05-16",
            "account_id": "FAM-BETA",
            "service_zone": "harbor",
            "base_before_account_cap_cents": "826",
            "account_cap_cents": "760",
            "account_cap_credit_cents": "66",
            "participating_rider_days": "3",
        },
        {
            "service_date": "2026-05-17",
            "account_id": "FAM-BETA",
            "service_zone": "harbor",
            "base_before_account_cap_cents": "900",
            "account_cap_cents": "760",
            "account_cap_credit_cents": "140",
            "participating_rider_days": "1",
        },
    ]

    assert rider_day[("2026-05-14", "R100")]["account_cap_credit_cents"] == "37"
    assert rider_day[("2026-05-14", "R102")]["account_cap_credit_cents"] == "43"
    assert rider_day[("2026-05-16", "R103")]["account_cap_credit_cents"] == "41"
    assert rider_day[("2026-05-16", "R105")]["account_cap_credit_cents"] == "25"
    assert rider_day[("2026-05-17", "R106")]["account_cap_credit_cents"] == "140"
    assert rider_day[("2026-05-18", "R,109")]["account_cap_credit_cents"] == "0"

    route_rows = {
        (row["service_date"], row["rider_id"], row["route_family"]): row
        for row in _read_route_family_rows()[1]
    }
    assert route_rows[("2026-05-14", "R100", "express")]["account_cap_credit_cents"] == "37"
    assert route_rows[("2026-05-14", "R102", "local")]["account_cap_credit_cents"] == "42"
    assert route_rows[("2026-05-14", "R102", "night")]["account_cap_credit_cents"] == "1"
    assert route_rows[("2026-05-16", "R103", "local")]["account_cap_credit_cents"] == "27"
    assert route_rows[("2026-05-16", "R105", "ferry")]["account_cap_credit_cents"] == "25"
    assert route_rows[("2026-05-18", "R,109", "express")]["account_cap_credit_cents"] == "0"
    assert route_rows[("2026-05-18", "R,109", "local")]["account_cap_credit_cents"] == "0"

    summary = json.loads(OUTPUT_JSON.read_text())
    assert summary["total_account_cap_credit_cents"] == 286
    assert summary["account_capped_groups"] == 3


def test_cap_exclusions_stay_charged_but_skip_cap_allocation():
    """Cap exclusions must leave base charged while removing it from individual and account cap math."""
    rider_day = {(row["service_date"], row["rider_id"]): row for row in _read_csv_rows()[1]}
    route_rows = {
        (row["service_date"], row["rider_id"], row["route_family"]): row
        for row in _read_route_family_rows()[1]
    }
    account_rows = {
        (row["service_date"], row["account_id"]): row
        for row in _read_account_cap_rows()[1]
    }
    audit_by_tap = {row["tap_id"]: row for row in _read_tap_audit_rows()[1]}
    summary = json.loads(OUTPUT_JSON.read_text())

    assert rider_day[("2026-05-17", "R106")]["total_charged_cents"] == "1055"
    assert rider_day[("2026-05-17", "R106")]["account_cap_credit_cents"] == "140"
    assert route_rows[("2026-05-17", "R106", "express")]["base_charged_cents"] == "468"
    assert route_rows[("2026-05-17", "R106", "express")]["cap_credit_cents"] == "43"
    assert route_rows[("2026-05-17", "R106", "express")]["account_cap_credit_cents"] == "49"

    assert ("2026-05-18", "FAM,DELTA") not in account_rows
    assert route_rows[("2026-05-18", "R,109", "local")]["base_charged_cents"] == "217"
    assert route_rows[("2026-05-18", "R,109", "local")]["account_cap_credit_cents"] == "0"
    assert audit_by_tap["t043"]["base_before_cap_cents"] == "340"
    assert summary["total_account_cap_credit_cents"] == 286


def test_account_credits_apply_after_account_caps_before_adjustments():
    """Account credits must carry balances while respecting filters, daily limits, and account-cap ordering."""
    rider_day = {(row["service_date"], row["rider_id"]): row for row in _read_csv_rows()[1]}
    route_rows = {
        (row["service_date"], row["rider_id"], row["route_family"]): row
        for row in _read_route_family_rows()[1]
    }
    summary = json.loads(OUTPUT_JSON.read_text())

    assert summary["total_account_credit_cents"] == 600
    assert rider_day[("2026-05-14", "R100")]["account_credit_cents"] == "47"
    assert rider_day[("2026-05-14", "R102")]["account_credit_cents"] == "53"

    assert rider_day[("2026-05-16", "R103")]["account_credit_cents"] == "300"
    assert rider_day[("2026-05-16", "R105")]["account_credit_cents"] == "0"
    assert rider_day[("2026-05-16", "R105")]["total_charged_cents"] == "215"
    assert rider_day[("2026-05-17", "R106")]["account_credit_cents"] == "200"

    assert route_rows[("2026-05-16", "R103", "crosstown")]["account_credit_cents"] == "105"
    assert route_rows[("2026-05-16", "R103", "local")]["account_credit_cents"] == "195"
    assert route_rows[("2026-05-16", "R103", "express")]["account_credit_cents"] == "0"
    assert route_rows[("2026-05-16", "R105", "express")]["account_credit_cents"] == "0"
    assert route_rows[("2026-05-16", "R105", "ferry")]["account_credit_cents"] == "0"

    assert rider_day[("2026-05-18", "R,109")]["account_credit_cents"] == "0"
    assert route_rows[("2026-05-18", "R,109", "crosstown")]["express_charged_cents"] == "45"
    assert route_rows[("2026-05-18", "R,109", "express")]["express_charged_cents"] == "160"


def test_temporary_zone_adjustments_drive_zone_dependent_policy():
    """Temporary zone adjustments must use exact direction before fallback rows and feed cap and credit filters."""
    rider_day = {(row["service_date"], row["rider_id"]): row for row in _read_csv_rows()[1]}
    route_rows = {
        (row["service_date"], row["rider_id"], row["route_family"]): row
        for row in _read_route_family_rows()[1]
    }
    account_rows = {
        (row["service_date"], row["account_id"]): row
        for row in _read_account_cap_rows()[1]
    }
    audit_by_tap = {row["tap_id"]: row for row in _read_tap_audit_rows()[1]}

    assert rider_day[("2026-05-18", "R,109")]["account_credit_cents"] == "0"
    assert route_rows[("2026-05-18", "R,109", "express")]["account_credit_cents"] == "0"
    assert route_rows[("2026-05-18", "R,109", "express")]["express_charged_cents"] == "160"
    assert ("2026-05-18", "FAM,DELTA") not in account_rows
    assert audit_by_tap["t043"]["route_id"] == "E1"
    assert audit_by_tap["t043"]["station_id"] == "S201"


def test_credit_reversals_preconsume_carryover_and_account_credit_balances():
    """Approved credit reversals must reduce carryover and account-credit starting balances before settlement."""
    rider_day = {(row["service_date"], row["rider_id"]): row for row in _read_csv_rows()[1]}
    route_rows = {
        (row["service_date"], row["rider_id"], row["route_family"]): row
        for row in _read_route_family_rows()[1]
    }
    summary = json.loads(OUTPUT_JSON.read_text())

    assert summary["total_carryover_credit_cents"] == 320
    assert summary["total_account_credit_cents"] == 600
    assert rider_day[("2026-05-17", "R106")]["carryover_credit_cents"] == "90"
    assert rider_day[("2026-05-17", "R106")]["account_credit_cents"] == "200"
    assert rider_day[("2026-05-18", "R,109")]["carryover_credit_cents"] == "140"
    assert rider_day[("2026-05-18", "R,109")]["account_credit_cents"] == "0"
    assert route_rows[("2026-05-17", "R106", "express")]["express_charged_cents"] == "100"
    assert route_rows[("2026-05-18", "R,109", "express")]["account_credit_cents"] == "0"


def test_csv_outputs_quote_identifier_fields_with_commas():
    """Identifier values containing commas must be preserved through parsing, settlement, and output CSV quoting."""
    assert '"R,109"' in OUTPUT_CSV.read_text()
    assert '"R,109"' in OUTPUT_ROUTE_LEDGER.read_text()
    assert '"R,109"' in OUTPUT_TAP_AUDIT.read_text()

    rider_day = {(row["service_date"], row["rider_id"]): row for row in _read_csv_rows()[1]}
    assert rider_day[("2026-05-18", "R,109")] == {
        "service_date": "2026-05-18",
        "rider_id": "R,109",
        "total_charged_cents": "842",
        "tap_count": "3",
        "distinct_routes": "3",
        "capping_applied": "false",
        "pass_credit_cents": "0",
        "disruption_credit_cents": "0",
        "subsidy_credit_cents": "0",
        "exception_credit_cents": "0",
        "hold_credit_cents": "0",
        "carryover_credit_cents": "140",
        "account_cap_credit_cents": "0",
        "account_credit_cents": "0",
        "adjustment_cents": "0",
        "unresolved_count": "0",
    }

    route_rows = {
        (row["service_date"], row["rider_id"], row["route_family"]): row
        for row in _read_route_family_rows()[1]
    }
    assert route_rows[("2026-05-18", "R,109", "crosstown")] == {
        "service_date": "2026-05-18",
        "rider_id": "R,109",
        "route_family": "crosstown",
        "base_charged_cents": "0",
        "express_charged_cents": "45",
        "cap_credit_cents": "0",
        "account_cap_credit_cents": "0",
        "account_credit_cents": "0",
        "tap_count": "1",
    }
    assert route_rows[("2026-05-18", "R,109", "express")] == {
        "service_date": "2026-05-18",
        "rider_id": "R,109",
        "route_family": "express",
        "base_charged_cents": "420",
        "express_charged_cents": "160",
        "cap_credit_cents": "0",
        "account_cap_credit_cents": "0",
        "account_credit_cents": "0",
        "tap_count": "1",
    }
    assert route_rows[("2026-05-18", "R,109", "local")] == {
        "service_date": "2026-05-18",
        "rider_id": "R,109",
        "route_family": "local",
        "base_charged_cents": "217",
        "express_charged_cents": "0",
        "cap_credit_cents": "0",
        "account_cap_credit_cents": "0",
        "account_credit_cents": "0",
        "tap_count": "1",
    }

    audit_by_tap = {row["tap_id"]: row for row in _read_tap_audit_rows()[1]}
    assert audit_by_tap["t042"]["rider_id"] == "R,109"
    assert audit_by_tap["t042"]["transfer_credit_cents"] == "300"
    assert audit_by_tap["t042"]["express_before_cap_cents"] == "45"
    assert audit_by_tap["t043"]["base_before_cap_cents"] == "340"


def test_tap_audit_ledger_tracks_original_values_and_charge_stages():
    """The tap audit ledger must expose original values, corrected values, and each per-tap policy stage."""
    _, rows = _read_tap_audit_rows()
    expected_rows = _expected_outputs()[3]
    assert rows == expected_rows

    actual = {row["tap_id"]: row for row in rows}
    assert actual["t004"]["original_route_id"] == "ZX"
    assert actual["t004"]["route_id"] == "E1"
    assert actual["t004"]["base_after_discount_cents"] == "340"
    assert actual["t004"]["transfer_credit_cents"] == "340"
    assert actual["t004"]["base_before_cap_cents"] == "0"

    assert actual["t028"]["original_rider_id"] == "R107"
    assert actual["t028"]["rider_id"] == "R106"
    assert actual["t028"]["base_after_discount_cents"] == "50"
    assert actual["t028"]["exception_credit_cents"] == "50"

    assert actual["t034"]["unresolved_reason"] == "rejected_device"
    assert actual["t034"]["route_family"] == ""
    assert actual["t034"]["base_before_cap_cents"] == "0"


def test_subsidy_credits_obey_active_zone_and_monthly_limits():
    """Subsidy credits must respect status, zone matching, recoveries, tap order, and monthly caps."""
    _, rows = _read_csv_rows()
    actual = {(row["service_date"], row["rider_id"]): row for row in rows}
    assert actual[("2026-05-15", "R100")]["subsidy_credit_cents"] == "75"
    assert actual[("2026-05-14", "R102")]["subsidy_credit_cents"] == "100"
    assert actual[("2026-05-16", "R105")]["subsidy_credit_cents"] == "150"
    assert actual[("2026-05-14", "R101")]["subsidy_credit_cents"] == "0"
    assert actual[("2026-05-15", "R103")]["subsidy_credit_cents"] == "0"
    assert json.loads(OUTPUT_JSON.read_text())["total_subsidy_credit_cents"] == 325


def test_subsidy_recoveries_preconsume_monthly_limits():
    """Approved recovery rows must consume monthly subsidy limits without acting like charges."""
    _, rows = _read_csv_rows()
    actual = {(row["service_date"], row["rider_id"]): row for row in rows}
    summary = json.loads(OUTPUT_JSON.read_text())

    assert actual[("2026-05-15", "R100")]["subsidy_credit_cents"] == "75"
    assert actual[("2026-05-15", "R100")]["total_charged_cents"] == "400"
    assert actual[("2026-05-14", "R102")]["subsidy_credit_cents"] == "100"
    assert actual[("2026-05-14", "R102")]["total_charged_cents"] == "414"
    assert actual[("2026-05-16", "R105")]["subsidy_credit_cents"] == "150"
    assert summary["total_adjustment_cents"] == -295


def test_exception_credits_apply_after_subsidies_and_before_caps():
    """Exception credits must clamp against remaining base and surcharge charges without touching unresolved taps."""
    _, rows = _read_csv_rows()
    actual = {(row["service_date"], row["rider_id"]): row for row in rows}
    assert actual[("2026-05-14", "R100")]["exception_credit_cents"] == "50"
    assert actual[("2026-05-14", "R102")]["exception_credit_cents"] == "90"
    assert actual[("2026-05-15", "R104")]["exception_credit_cents"] == "200"
    assert actual[("2026-05-16", "R105")]["exception_credit_cents"] == "450"
    assert actual[("2026-05-16", "R106")]["exception_credit_cents"] == "50"
    assert ("2026-05-16", "R107") not in actual
    assert json.loads(OUTPUT_JSON.read_text())["total_exception_credit_cents"] == 840


def test_settlement_holds_apply_after_exception_credits_and_before_caps():
    """Settlement holds must reduce route-family totals after tap audit values and before cap allocation."""
    _, rows = _read_csv_rows()
    rider_day = {(row["service_date"], row["rider_id"]): row for row in rows}
    route_rows = {
        (row["service_date"], row["rider_id"], row["route_family"]): row
        for row in _read_route_family_rows()[1]
    }
    audit_by_tap = {row["tap_id"]: row for row in _read_tap_audit_rows()[1]}
    summary = json.loads(OUTPUT_JSON.read_text())

    assert rider_day[("2026-05-15", "R100")]["hold_credit_cents"] == "40"
    assert rider_day[("2026-05-16", "R103")]["hold_credit_cents"] == "200"
    assert rider_day[("2026-05-16", "R103")]["capping_applied"] == "false"
    assert rider_day[("2026-05-17", "R106")]["hold_credit_cents"] == "695"
    assert summary["total_hold_credit_cents"] == 935
    assert summary["capped_rider_days"] == 1

    assert audit_by_tap["t016"]["base_before_cap_cents"] == "104"
    assert audit_by_tap["t016"]["express_before_cap_cents"] == "130"
    assert route_rows[("2026-05-16", "R103", "express")]["base_charged_cents"] == "0"
    assert route_rows[("2026-05-16", "R103", "express")]["express_charged_cents"] == "80"
    assert route_rows[("2026-05-16", "R103", "express")]["account_credit_cents"] == "0"
    assert route_rows[("2026-05-17", "R106", "ferry")]["base_charged_cents"] == "89"
    assert route_rows[("2026-05-17", "R106", "ferry")]["express_charged_cents"] == "95"


def test_carryover_credits_apply_after_holds_and_before_caps():
    """Carryovers must consume balances across eligible days before cap allocation without changing tap audit rows."""
    _, rows = _read_csv_rows()
    rider_day = {(row["service_date"], row["rider_id"]): row for row in rows}
    route_rows = {
        (row["service_date"], row["rider_id"], row["route_family"]): row
        for row in _read_route_family_rows()[1]
    }
    audit_by_tap = {row["tap_id"]: row for row in _read_tap_audit_rows()[1]}
    summary = json.loads(OUTPUT_JSON.read_text())

    assert rider_day[("2026-05-15", "R100")]["hold_credit_cents"] == "40"
    assert rider_day[("2026-05-15", "R100")]["carryover_credit_cents"] == "90"
    assert rider_day[("2026-05-17", "R106")]["carryover_credit_cents"] == "90"
    assert rider_day[("2026-05-18", "R,109")]["carryover_credit_cents"] == "140"
    assert summary["total_carryover_credit_cents"] == 320

    assert route_rows[("2026-05-15", "R100", "local")]["base_charged_cents"] == "355"
    assert route_rows[("2026-05-17", "R106", "express")]["express_charged_cents"] == "100"
    assert route_rows[("2026-05-17", "R106", "local")]["base_charged_cents"] == "135"
    assert route_rows[("2026-05-17", "R106", "local")]["account_credit_cents"] == "44"
    assert route_rows[("2026-05-18", "R,109", "local")]["base_charged_cents"] == "217"
    assert route_rows[("2026-05-18", "R,109", "express")]["base_charged_cents"] == "420"
    assert audit_by_tap["t037"]["express_before_cap_cents"] == "180"
    assert audit_by_tap["t043"]["base_before_cap_cents"] == "340"


def test_route_family_minimums_apply_after_carryovers_before_caps():
    """Minimum rows must raise route-family totals after credits without changing tap audit stages."""
    rider_day = {(row["service_date"], row["rider_id"]): row for row in _read_csv_rows()[1]}
    route_rows = {
        (row["service_date"], row["rider_id"], row["route_family"]): row
        for row in _read_route_family_rows()[1]
    }
    account_rows = {
        (row["service_date"], row["account_id"]): row
        for row in _read_account_cap_rows()[1]
    }
    audit_by_tap = {row["tap_id"]: row for row in _read_tap_audit_rows()[1]}

    assert rider_day[("2026-05-16", "R103")]["total_charged_cents"] == "300"
    assert route_rows[("2026-05-16", "R103", "express")]["express_charged_cents"] == "80"
    assert route_rows[("2026-05-16", "R103", "express")]["account_credit_cents"] == "0"
    assert audit_by_tap["t016"]["express_before_cap_cents"] == "130"

    assert rider_day[("2026-05-17", "R106")]["total_charged_cents"] == "1055"
    assert route_rows[("2026-05-17", "R106", "ferry")] == {
        "service_date": "2026-05-17",
        "rider_id": "R106",
        "route_family": "ferry",
        "base_charged_cents": "89",
        "express_charged_cents": "95",
        "cap_credit_cents": "14",
        "account_cap_credit_cents": "17",
        "account_credit_cents": "0",
        "tap_count": "1",
    }
    assert audit_by_tap["t036"]["express_before_cap_cents"] == "55"

    assert route_rows[("2026-05-18", "R,109", "express")]["base_charged_cents"] == "420"
    assert route_rows[("2026-05-18", "R,109", "express")]["express_charged_cents"] == "160"
    assert route_rows[("2026-05-18", "R,109", "express")]["account_credit_cents"] == "0"
    assert ("2026-05-18", "FAM,DELTA") not in account_rows
    assert audit_by_tap["t043"]["base_before_cap_cents"] == "340"
    assert audit_by_tap["t043"]["express_before_cap_cents"] == "130"


def test_unresolved_events_are_complete_and_sorted():
    """Every unresolved tap must be listed with a policy reason and stable service-date/tap-id sort order."""
    summary = json.loads(OUTPUT_JSON.read_text())
    events = summary["unresolved_events"]
    expected_events = _expected_outputs()[1]["unresolved_events"]
    assert events == expected_events
    assert events == sorted(events, key=lambda row: (row["service_date"], row["tap_id"]))


def test_unresolved_only_rider_days_stay_in_settlement_csv():
    """Rider-days with only unresolved taps must still appear with zero fareable counts."""
    _, rows = _read_csv_rows()
    actual = {(row["service_date"], row["rider_id"]): row for row in rows}
    expected_rows = _expected_outputs()[0]
    expected = {(row["service_date"], row["rider_id"]): row for row in expected_rows}

    for key in [("2026-05-16", "R102"), ("2026-05-16", "R108")]:
        assert actual[key] == expected[key]
        assert actual[key]["tap_count"] == "0"
        assert actual[key]["distinct_routes"] == "0"
        assert actual[key]["unresolved_count"] == "1"


def test_approved_fare_overrides_are_applied_in_the_policy_order():
    """Approved overrides must affect base fares, surcharges, and pass coverage without applying to unresolved taps."""
    _, rows = _read_csv_rows()
    actual = {(row["service_date"], row["rider_id"]): row for row in rows}
    expected, summary, _, _, _ = _expected_outputs()
    expected_by_day = {(row["service_date"], row["rider_id"]): row for row in expected}
    for key in [("2026-05-14", "R100"), ("2026-05-15", "R100"), ("2026-05-14", "R102")]:
        assert actual[key] == expected_by_day[key]
    assert actual[("2026-05-14", "R102")]["capping_applied"] == "false"
    assert summary["unresolved_by_reason"]["unknown_rider"] == 1


def test_quoted_csv_fields_are_parsed_without_shifting_columns():
    """Quoted comma values in CSV identifiers must not change pass, subsidy, or override columns."""
    rider_day = {
        (row["service_date"], row["rider_id"]): row
        for row in _read_csv_rows()[1]
    }
    audit_by_tap = {row["tap_id"]: row for row in _read_tap_audit_rows()[1]}

    assert rider_day[("2026-05-14", "R101")]["pass_credit_cents"] == "140"
    assert rider_day[("2026-05-14", "R102")]["subsidy_credit_cents"] == "100"
    assert audit_by_tap["t003"]["express_before_cap_cents"] == "95"
    assert audit_by_tap["t006"]["express_before_cap_cents"] == "10"


def test_station_pair_surcharges_follow_corrected_fareable_order():
    """Station-pair surcharges must use the previous fareable corrected tap and approved override amounts."""
    audit_by_tap = {row["tap_id"]: row for row in _read_tap_audit_rows()[1]}

    assert audit_by_tap["t002"]["express_before_cap_cents"] == "35"
    assert audit_by_tap["t006"]["express_before_cap_cents"] == "10"
    assert audit_by_tap["t036"]["express_before_cap_cents"] == "55"
    assert audit_by_tap["t037"]["express_before_cap_cents"] == "180"
    assert audit_by_tap["t015"]["express_before_cap_cents"] == "0"

    route_rows = {
        (row["service_date"], row["rider_id"], row["route_family"]): row
        for row in _read_route_family_rows()[1]
    }
    assert route_rows[("2026-05-14", "R101", "crosstown")]["express_charged_cents"] == "10"
    assert route_rows[("2026-05-17", "R106", "express")]["express_charged_cents"] == "100"
    assert route_rows[("2026-05-17", "R106", "ferry")]["express_charged_cents"] == "95"


def test_late_tap_corrections_apply_before_classification_and_transfers():
    """Late tap corrections must change tap fields before unresolved checks, sorting, and transfer decisions."""
    _, rows = _read_csv_rows()
    actual = {(row["service_date"], row["rider_id"]): row for row in rows}
    expected, summary, _, _, _ = _expected_outputs()
    expected_by_day = {(row["service_date"], row["rider_id"]): row for row in expected}
    actual_summary = json.loads(OUTPUT_JSON.read_text())
    assert actual_summary["corrected_tap_count"] == 7
    assert actual[("2026-05-15", "R106")] == expected_by_day[("2026-05-15", "R106")]
    assert actual[("2026-05-16", "R106")] == expected_by_day[("2026-05-16", "R106")]
    assert actual[("2026-05-16", "R103")]["total_charged_cents"] == expected_by_day[("2026-05-16", "R103")]["total_charged_cents"]
    assert actual[("2026-05-16", "R103")]["total_charged_cents"] == "300"
    audit_by_tap = {row["tap_id"]: row for row in _read_tap_audit_rows()[1]}
    assert audit_by_tap["t016"]["service_date"] == "2026-05-16"
    assert audit_by_tap["t016"]["disruption_credit_cents"] == "100"
    assert audit_by_tap["t016"]["base_before_cap_cents"] == "104"
    assert audit_by_tap["t016"]["express_before_cap_cents"] == "130"
    assert actual_summary["unresolved_by_reason"] == summary["unresolved_by_reason"]
    assert actual_summary["unresolved_by_reason"] == {
        "inactive_station": 1,
        "rejected_device": 1,
        "unknown_rider": 1,
        "unknown_route": 1,
    }


def test_overnight_taps_use_normalized_service_dates():
    """Early-morning taps must bill to the previous service day before grouping and capping."""
    _, rider_rows = _read_csv_rows()
    rider_day = {(row["service_date"], row["rider_id"]): row for row in rider_rows}
    expected, _, route_rows, audit_rows, _ = _expected_outputs()
    expected_by_day = {(row["service_date"], row["rider_id"]): row for row in expected}

    assert rider_day[("2026-05-16", "R100")] == expected_by_day[("2026-05-16", "R100")]
    assert ("2026-05-17", "R100") not in rider_day
    assert rider_day[("2026-05-17", "R106")]["tap_count"] == "5"

    actual_route_rows = {
        (row["service_date"], row["rider_id"], row["route_family"]): row
        for row in _read_route_family_rows()[1]
    }
    expected_route_rows = {
        (row["service_date"], row["rider_id"], row["route_family"]): row
        for row in route_rows
    }
    assert actual_route_rows[("2026-05-17", "R106", "local")] == expected_route_rows[
        ("2026-05-17", "R106", "local")
    ]

    audit_by_tap = {row["tap_id"]: row for row in _read_tap_audit_rows()[1]}
    expected_audit_by_tap = {row["tap_id"]: row for row in audit_rows}
    assert audit_by_tap["t039"] == expected_audit_by_tap["t039"]
    assert audit_by_tap["t039"]["service_date"] == "2026-05-16"
    assert audit_by_tap["t040"] == expected_audit_by_tap["t040"]
    assert audit_by_tap["t040"]["service_date"] == "2026-05-17"
