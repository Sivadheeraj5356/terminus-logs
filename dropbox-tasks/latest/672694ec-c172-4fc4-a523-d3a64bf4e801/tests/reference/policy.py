"""Reference-measurement appraisal."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuleResult:
    rule_id: str
    rule_kind: str
    matched_event_sequences: list[int]
    status: str
    reason_or_null: str | None
    failed: bool


@dataclass
class AppraisalResult:
    rule_results: list[RuleResult]
    event_policy_status: dict[int, tuple[str, str | None]]  # seq -> (status, rule_id)
    matched_rule_count: int
    failed_rule_count: int
    reject_reason: str | None  # reference_measurement_mismatch or event_order_violation
    order_failed: tuple[str, str] | None


def appraise(
    policy: dict,
    events: list[dict],
) -> AppraisalResult:
    rules = policy["measurement_rules"]
    ordered_rule_ids = sorted(rules.keys())
    # Build selector -> rule_id
    selector_map: dict[tuple, str] = {}
    for rid, rule in rules.items():
        selector_map[(rule["pcr_index"], rule["event_type"], rule["component"])] = rid

    # Map events to rules
    matches: dict[str, list[dict]] = {rid: [] for rid in rules}
    event_status: dict[int, tuple[str, str | None]] = {}
    unknown_seqs: list[int] = []

    for ev in sorted(events, key=lambda e: e["event_seq"]):
        sel = (ev["pcr_index"], ev["event_type"], ev["component"])
        rid = selector_map.get(sel)
        if rid is None:
            unknown_seqs.append(ev["event_seq"])
            event_status[ev["event_seq"]] = ("pending_unknown", None)
        else:
            matches[rid].append(ev)
            event_status[ev["event_seq"]] = ("matched", rid)

    rule_results: list[RuleResult] = []
    reject_reason: str | None = None
    first_fail_done = False

    for rid in ordered_rule_ids:
        rule = rules[rid]
        evs = matches[rid]
        seqs = sorted(e["event_seq"] for e in evs)
        kind = rule["kind"]
        status = "matched"
        reason = None
        failed = False

        if kind == "forbidden":
            if evs:
                status = "forbidden_present"
                reason = "forbidden_event_present"
                failed = True
                for e in evs:
                    event_status[e["event_seq"]] = ("rejected", rid)
        elif kind == "required":
            if len(evs) == 0:
                status = "missing"
                reason = "required_event_missing"
                failed = True
            elif len(evs) > 1:
                status = "duplicate"
                reason = "multiple_matching_events"
                failed = True
                for e in evs:
                    event_status[e["event_seq"]] = ("rejected", rid)
            else:
                e = evs[0]
                if e["version"] not in rule["allowed_versions"]:
                    status = "version_mismatch"
                    reason = "event_version_not_allowed"
                    failed = True
                    event_status[e["event_seq"]] = ("rejected", rid)
                elif e["measurement_digest"] not in rule["allowed_digests"]:
                    status = "digest_mismatch"
                    reason = "event_digest_not_allowed"
                    failed = True
                    event_status[e["event_seq"]] = ("rejected", rid)
                else:
                    status = "matched"
                    event_status[e["event_seq"]] = ("matched", rid)
        else:  # optional
            if len(evs) == 0:
                status = "absent_allowed"
            elif len(evs) > 1:
                status = "duplicate"
                reason = "multiple_matching_events"
                failed = True
                for e in evs:
                    event_status[e["event_seq"]] = ("rejected", rid)
            else:
                e = evs[0]
                if e["version"] not in rule["allowed_versions"]:
                    status = "version_mismatch"
                    reason = "event_version_not_allowed"
                    failed = True
                    event_status[e["event_seq"]] = ("rejected", rid)
                elif e["measurement_digest"] not in rule["allowed_digests"]:
                    status = "digest_mismatch"
                    reason = "event_digest_not_allowed"
                    failed = True
                    event_status[e["event_seq"]] = ("rejected", rid)
                else:
                    status = "matched"
                    event_status[e["event_seq"]] = ("matched", rid)

        rule_results.append(
            RuleResult(
                rule_id=rid,
                rule_kind=kind,
                matched_event_sequences=seqs,
                status=status,
                reason_or_null=reason,
                failed=failed,
            )
        )
        if failed and not first_fail_done:
            reject_reason = "reference_measurement_mismatch"
            first_fail_done = True

    # Unknown events
    if policy["unknown_event_mode"] == "reject" and unknown_seqs and not first_fail_done:
        reject_reason = "reference_measurement_mismatch"
        first_fail_done = True
        for seq in unknown_seqs:
            event_status[seq] = ("rejected", None)
    else:
        for seq in unknown_seqs:
            if event_status.get(seq, ("", None))[0] == "pending_unknown":
                if policy["unknown_event_mode"] == "allow":
                    event_status[seq] = ("allowed_unknown", None)
                else:
                    event_status[seq] = ("rejected", None)

    # If measurement already failed, still emit rule rows; skip order? Spec says
    # evaluate order only after all measurement rules pass.
    order_failed = None
    if reject_reason is None:
        # Also fail if unknown reject already set — handled above
        # Check unknown reject path when mode=reject
        if policy["unknown_event_mode"] == "reject" and unknown_seqs:
            reject_reason = "reference_measurement_mismatch"
        else:
            constraints = sorted(
                policy["order_constraints"],
                key=lambda c: (c["before_rule_id"], c["after_rule_id"]),
            )
            for c in constraints:
                b_id = c["before_rule_id"]
                a_id = c["after_rule_id"]
                b_evs = matches[b_id]
                a_evs = matches[a_id]
                if len(b_evs) == 1 and len(a_evs) == 1:
                    if not (b_evs[0]["event_seq"] < a_evs[0]["event_seq"]):
                        reject_reason = "event_order_violation"
                        order_failed = (b_id, a_id)
                        break

    matched_rule_count = sum(1 for r in rule_results if r.status == "matched")
    failed_rule_count = sum(1 for r in rule_results if r.failed)

    # Normalize pending_unknown leftovers
    for seq, (st, _) in list(event_status.items()):
        if st == "pending_unknown":
            event_status[seq] = (
                "allowed_unknown" if policy["unknown_event_mode"] == "allow" else "rejected",
                None,
            )

    return AppraisalResult(
        rule_results=rule_results,
        event_policy_status=event_status,
        matched_rule_count=matched_rule_count,
        failed_rule_count=failed_rule_count,
        reject_reason=reject_reason,
        order_failed=order_failed,
    )
