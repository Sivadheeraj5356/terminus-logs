import hashlib
import hmac
import ipaddress
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


APP = Path("/app")
INPUT = APP / "input" / "inspection.json"
OUTPUT = APP / "output" / "report.json"
BIN = APP / "macaroon-audit"

PRIMARY_ORDER = [
    "unknown_root_key",
    "root_key_inactive",
    "revoked_identifier",
    "bad_primary_signature",
    "timestamp_skew",
    "replayed_nonce",
    "first_party_unsatisfied",
    "third_party_unsatisfied",
    "unused_discharge",
]
DISCHARGE_ORDER = [
    "unknown_discharge_key",
    "discharge_key_inactive",
    "revoked_identifier",
    "replayed_discharge",
    "bad_discharge_signature",
    "bad_binding",
    "first_party_unsatisfied",
]


def normalize_path(value):
    parts = []
    for part in value.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
        else:
            parts.append(part)
    return "/" + "/".join(parts)


def normalized_request(request):
    return {
        "method": request["method"].upper(),
        "path": normalize_path(request["path"]),
        "ip": str(ipaddress.ip_address(request["ip"])),
        "scopes": sorted(request["scopes"]),
        "body_sha256": hashlib.sha256(request["body"].encode()).hexdigest(),
    }


def canonical_caveat(caveat):
    kind = caveat["type"]
    if kind in ("time_before", "time_after"):
        return f"{kind}|{caveat['value']}"
    if kind == "method":
        return f"method|{caveat['value'].upper()}"
    if kind == "path_prefix":
        return f"path_prefix|{normalize_path(caveat['value'])}"
    if kind == "ip_cidr":
        return f"ip_cidr|{ipaddress.ip_network(caveat['value'], strict=False)}"
    if kind == "body_sha256":
        return f"body_sha256|{caveat['value'].lower()}"
    if kind == "scope":
        return f"scope|{caveat['value']}"
    if kind == "third_party":
        return f"third_party|{caveat['caveat_id']}|{caveat['location']}|{caveat['key_id']}"
    assert kind == "third_party_quorum"
    tail = "".join(f"|{authority['location']}|{authority['key_id']}" for authority in caveat["authorities"])
    return f"third_party_quorum|{caveat['caveat_id']}|{caveat['threshold']}{tail}"


def mac(key, message):
    return hmac.new(key, message, hashlib.sha256).digest()


def token_signature(secret, token, discharge):
    marker = "D1" if discharge else "M1"
    key_field = token["key_id"] if discharge else token["root_key_id"]
    replay = f"\n{token['replay_id']}" if discharge else ""
    current = mac(secret.encode(), f"{marker}\n{token['location']}\n{token['identifier']}\n{key_field}{replay}".encode())
    for caveat in token["caveats"]:
        current = mac(current, canonical_caveat(caveat).encode())
    return current.hex()


def strict_hex(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        return None
    return bytes.fromhex(value)


def expected_binding(primary_signature, discharge_signature):
    primary = strict_hex(primary_signature)
    discharge = strict_hex(discharge_signature)
    if primary is None or discharge is None:
        return None
    return mac(primary, discharge).hex()


def expected_attachment(parent_signature, caveat, discharge_signature):
    parent = strict_hex(parent_signature)
    discharge = strict_hex(discharge_signature)
    if parent is None or discharge is None:
        return None
    return mac(parent, canonical_caveat(caveat).encode() + b"\0" + discharge).hex()


def scope_covers(caveat_scope, requested_scope):
    if caveat_scope == "*":
        return True
    if caveat_scope.endswith(":*"):
        return requested_scope.startswith(caveat_scope[:-1])
    return caveat_scope == requested_scope


def first_party_ok(caveats, request, normalized):
    for caveat in caveats:
        kind = caveat["type"]
        if kind in ("third_party", "third_party_quorum"):
            continue
        if kind == "time_before" and not request["timestamp"] < caveat["value"]:
            return False
        if kind == "time_after" and not request["timestamp"] >= caveat["value"]:
            return False
        if kind == "method" and normalized["method"] != caveat["value"].upper():
            return False
        if kind == "path_prefix":
            prefix = normalize_path(caveat["value"])
            if prefix != "/" and normalized["path"] != prefix and not normalized["path"].startswith(prefix + "/"):
                return False
        if kind == "ip_cidr" and ipaddress.ip_address(normalized["ip"]) not in ipaddress.ip_network(caveat["value"], strict=False):
            return False
        if kind == "scope" and not all(scope_covers(caveat["value"], scope) for scope in request["scopes"]):
            return False
        if kind == "body_sha256" and normalized["body_sha256"] != caveat["value"].lower():
            return False
    return True


def key_maps(case):
    roots = {key["id"]: key for key in case["root_keys"]}
    discharges = {(key["location"], key["key_id"]): key for key in case["discharge_keys"]}
    return roots, discharges


def discharge_identity(token):
    return token["location"], token["key_id"], token["replay_id"]


def discharge_audits(case, request, normalized, spent):
    _, keys = key_maps(case)
    revoked = set(case["revoked_identifiers"])
    results = []
    usable = []
    for token in request["discharges"]:
        reasons = []
        key = keys.get((token["location"], token["key_id"]))
        if key is None:
            reasons.append("unknown_discharge_key")
        else:
            if not key["not_before"] <= request["timestamp"] <= key["not_after"]:
                reasons.append("discharge_key_inactive")
            if token["signature"] != token_signature(key["secret"], token, True):
                reasons.append("bad_discharge_signature")
        if token["identifier"] in revoked:
            reasons.append("revoked_identifier")
        if discharge_identity(token) in spent:
            reasons.append("replayed_discharge")
        binding = expected_binding(request["macaroon"]["signature"], token["signature"])
        if binding is None or token["binding"] != binding:
            reasons.append("bad_binding")
        if not first_party_ok(token["caveats"], request, normalized):
            reasons.append("first_party_unsatisfied")
        ordered = [reason for reason in DISCHARGE_ORDER if reason in reasons]
        is_usable = not ordered
        usable.append(is_usable)
        results.append({"instance_id": token["instance_id"], "usable": is_usable, "reasons": ordered})
    return results, usable


def third_caveats(caveats):
    return [caveat for caveat in caveats if caveat["type"] in ("third_party", "third_party_quorum")]


def find_assignment(primary, discharges, usable, require_all):
    initial = [(caveat, primary["signature"]) for caveat in third_caveats(primary["caveats"])]

    def visit(tasks, used, used_replay, sequence, indexes):
        if not tasks:
            if require_all and len(used) != len(discharges):
                return None
            return sequence, indexes
        caveat, parent_signature = tasks[0]
        candidates = []
        for index, token in enumerate(discharges):
            identity = discharge_identity(token)
            if index in used or identity in used_replay or not usable[index]:
                continue
            if caveat["type"] == "third_party":
                authority = token["location"] == caveat["location"] and token["key_id"] == caveat["key_id"]
            else:
                authority = {"location": token["location"], "key_id": token["key_id"]} in caveat["authorities"]
            attachment = expected_attachment(parent_signature, caveat, token["signature"])
            if token["identifier"] == caveat["caveat_id"] and authority and token["attachment"] == attachment:
                candidates.append(index)
        candidates.sort(key=lambda index: discharges[index]["instance_id"])

        if caveat["type"] == "third_party":
            for index in candidates:
                token = discharges[index]
                nested = [(child, token["signature"]) for child in third_caveats(token["caveats"])]
                result = visit(
                    nested + tasks[1:],
                    used | {index},
                    used_replay | {discharge_identity(token)},
                    sequence + [token["instance_id"]],
                    indexes + [index],
                )
                if result is not None:
                    return result
            return None

        combinations = []

        def choose(start, chosen, authorities, replay_ids):
            if len(chosen) == caveat["threshold"]:
                combinations.append(chosen)
                return
            for position in range(start, len(candidates)):
                index = candidates[position]
                token = discharges[index]
                authority = token["location"], token["key_id"]
                identity = discharge_identity(token)
                if authority in authorities or identity in replay_ids:
                    continue
                choose(position + 1, chosen + [index], authorities | {authority}, replay_ids | {identity})

        choose(0, [], set(), set())
        for combination in combinations:
            nested = []
            next_used = set(used)
            next_replay = set(used_replay)
            next_sequence = list(sequence)
            next_indexes = list(indexes)
            for index in combination:
                token = discharges[index]
                next_used.add(index)
                next_replay.add(discharge_identity(token))
                next_sequence.append(token["instance_id"])
                next_indexes.append(index)
                nested.extend((child, token["signature"]) for child in third_caveats(token["caveats"]))
            result = visit(nested + tasks[1:], next_used, next_replay, next_sequence, next_indexes)
            if result is not None:
                return result
        return None

    return visit(initial, set(), set(), [], [])


def expected_report(case):
    roots, _ = key_maps(case)
    revoked = set(case["revoked_identifiers"])
    reserved_nonces = [dict(item) for item in case["reserved_nonces"]]
    seen = {(item["identifier"], item["nonce"]) for item in reserved_nonces}
    spent_discharges = [dict(item) for item in case["spent_discharges"]]
    spent = {(item["location"], item["key_id"], item["replay_id"]) for item in spent_discharges}
    decisions = []
    counts = {}
    allowed = 0
    denied = 0

    for request in case["requests"]:
        normalized = normalized_request(request)
        primary = request["macaroon"]
        key = roots.get(primary["root_key_id"])
        reasons = []
        authenticated = False
        if key is None:
            reasons.append("unknown_root_key")
        else:
            if not key["not_before"] <= request["timestamp"] <= key["not_after"]:
                reasons.append("root_key_inactive")
            expected = token_signature(key["secret"], primary, False)
            authenticated = primary["signature"] == expected
            if not authenticated:
                reasons.append("bad_primary_signature")
        if primary["identifier"] in revoked:
            reasons.append("revoked_identifier")
        if abs(case["evaluation_time"] - request["timestamp"]) > case["max_skew_seconds"]:
            reasons.append("timestamp_skew")

        local_results, locally_usable = discharge_audits(case, request, normalized, spent)
        used_discharges = []
        if authenticated:
            replay_key = (primary["identifier"], request["nonce"])
            if replay_key in seen:
                reasons.append("replayed_nonce")
            else:
                reserved_nonces.append({"identifier": primary["identifier"], "nonce": request["nonce"]})
            seen.add(replay_key)
            if not first_party_ok(primary["caveats"], request, normalized):
                reasons.append("first_party_unsatisfied")
            partial = find_assignment(primary, request["discharges"], locally_usable, False)
            complete = find_assignment(primary, request["discharges"], locally_usable, True)
            if partial is None:
                reasons.append("third_party_unsatisfied")
            if complete is None:
                reasons.append("unused_discharge")
            chosen = complete if complete is not None else partial
            if chosen is not None:
                used_discharges, indexes = chosen
                for index in indexes:
                    token = request["discharges"][index]
                    identity = discharge_identity(token)
                    if identity not in spent:
                        spent.add(identity)
                        spent_discharges.append(
                            {"location": identity[0], "key_id": identity[1], "replay_id": identity[2]}
                        )

        reasons = [reason for reason in PRIMARY_ORDER if reason in reasons]
        decision = "allow" if not reasons else "deny"
        if decision == "allow":
            allowed += 1
        else:
            denied += 1
        for reason in reasons:
            counts[reason] = counts.get(reason, 0) + 1
        decisions.append(
            {
                "id": request["id"],
                "decision": decision,
                "reasons": reasons,
                "normalized": normalized,
                "primary_caveats": [canonical_caveat(caveat) for caveat in primary["caveats"]],
                "used_discharges": used_discharges,
                "discharge_results": local_results,
            }
        )
    return {
        "evaluated_at": case["evaluation_time"],
        "decisions": decisions,
        "summary": {"allowed": allowed, "denied": denied, "reason_counts": {key: counts[key] for key in sorted(counts)}},
        "final_state": {"reserved_nonces": reserved_nonces, "spent_discharges": spent_discharges},
    }


def third(caveat_id, location, key_id):
    return {"type": "third_party", "caveat_id": caveat_id, "location": location, "key_id": key_id}


def quorum(caveat_id, threshold, authorities):
    return {
        "type": "third_party_quorum",
        "caveat_id": caveat_id,
        "threshold": threshold,
        "authorities": [{"location": location, "key_id": key_id} for location, key_id in authorities],
    }


def token(instance_id, identifier, location, key_id, caveats, replay_id=None):
    return {
        "instance_id": instance_id,
        "replay_id": replay_id or instance_id,
        "identifier": identifier,
        "location": location,
        "key_id": key_id,
        "caveats": caveats,
        "signature": "",
        "binding": "",
        "attachment": "",
    }


def request_template(case, suffix, identifier, nonce, caveats, discharges, root_key_id="root-main"):
    seed = case["seed"]
    ipv6 = seed % 2 == 1
    request = {
        "id": f"{suffix}-{seed}",
        "timestamp": case["evaluation_time"] + 5,
        "method": "get",
        "path": f"//mesh/./svc-{seed}/api/../api/item/",
        "ip": f"2001:db8:{seed:x}::17" if ipv6 else f"10.{seed}.4.17",
        "scopes": ["svc:write", "svc:read"],
        "body": f"payload-{seed}",
        "nonce": nonce,
        "macaroon": {
            "identifier": identifier,
            "location": f"gateway-{seed}",
            "root_key_id": root_key_id,
            "caveats": caveats,
            "signature": "",
        },
        "discharges": discharges,
    }
    return request


def seal_request(
    case,
    request,
    corrupt_primary=False,
    corrupt_bindings=(),
    corrupt_discharges=(),
    corrupt_attachments=(),
    attachment_parents=None,
):
    attachment_parents = attachment_parents or {}
    roots, discharge_keys = key_maps(case)
    root = roots.get(request["macaroon"]["root_key_id"])
    request["macaroon"]["signature"] = "0" * 64 if root is None else token_signature(root["secret"], request["macaroon"], False)
    if corrupt_primary:
        request["macaroon"]["signature"] = ("1" if request["macaroon"]["signature"][0] != "1" else "2") + request["macaroon"]["signature"][1:]
    for discharge in request["discharges"]:
        key = discharge_keys.get((discharge["location"], discharge["key_id"]))
        discharge["signature"] = "0" * 64 if key is None else token_signature(key["secret"], discharge, True)
        if discharge["instance_id"] in corrupt_discharges:
            discharge["signature"] = ("1" if discharge["signature"][0] != "1" else "2") + discharge["signature"][1:]
        discharge["binding"] = expected_binding(request["macaroon"]["signature"], discharge["signature"]) or "0" * 64
        if discharge["instance_id"] in corrupt_bindings:
            discharge["binding"] = ("1" if discharge["binding"][0] != "1" else "2") + discharge["binding"][1:]
    by_instance = {token["instance_id"]: token for token in request["discharges"]}
    for discharge in request["discharges"]:
        parent_name = attachment_parents.get(discharge["instance_id"])
        parent = request["macaroon"] if parent_name is None else by_instance[parent_name]
        matching = []
        for caveat in third_caveats(parent["caveats"]):
            if caveat["caveat_id"] != discharge["identifier"]:
                continue
            if caveat["type"] == "third_party":
                allowed = caveat["location"] == discharge["location"] and caveat["key_id"] == discharge["key_id"]
            else:
                allowed = {"location": discharge["location"], "key_id": discharge["key_id"]} in caveat["authorities"]
            if allowed:
                matching.append(caveat)
        discharge["attachment"] = (
            expected_attachment(parent["signature"], matching[0], discharge["signature"])
            if matching
            else "0" * 64
        )
        if discharge["instance_id"] in corrupt_attachments:
            discharge["attachment"] = ("1" if discharge["attachment"][0] != "1" else "2") + discharge["attachment"][1:]
    return request


def generated_case(seed):
    now = 1900000000 + seed * 1000
    location = f"verifier-{seed}"
    key_id = f"vkey-{seed}"
    case = {
        "seed": seed,
        "evaluation_time": now,
        "max_skew_seconds": 120 + seed,
        "root_keys": [
            {"id": "root-main", "secret": f"root-secret-{seed}", "not_before": now - 500, "not_after": now + 500},
            {"id": "root-old", "secret": f"old-secret-{seed}", "not_before": now - 500, "not_after": now - 1},
        ],
        "discharge_keys": [
            {"location": location, "key_id": key_id, "secret": f"discharge-secret-{seed}", "not_before": now - 500, "not_after": now + 500},
            {"location": location, "key_id": "inactive", "secret": f"inactive-secret-{seed}", "not_before": now - 500, "not_after": now - 1},
            {"location": location, "key_id": f"vkey-b-{seed}", "secret": f"discharge-b-{seed}", "not_before": now - 500, "not_after": now + 500},
            {"location": f"backup-{seed}", "key_id": f"vkey-c-{seed}", "secret": f"discharge-c-{seed}", "not_before": now - 500, "not_after": now + 500},
        ],
        "revoked_identifiers": [f"revoked-{seed}", f"d-revoked-{seed}"],
        "reserved_nonces": [{"identifier": f"pre-reserved-{seed}", "nonce": f"pre-nonce-{seed}"}],
        "spent_discharges": [{"location": location, "key_id": key_id, "replay_id": f"pre-spent-{seed}"}],
        "requests": [],
    }
    ipv6 = seed % 2 == 1
    cidr = f"2001:db8:{seed:x}::99/64" if ipv6 else f"10.{seed}.4.99/24"
    body_hash = hashlib.sha256(f"payload-{seed}".encode()).hexdigest().upper()
    common = [
        {"type": "time_after", "value": now - 1},
        {"type": "time_before", "value": now + 100},
        {"type": "method", "value": "GET"},
        {"type": "path_prefix", "value": f"//mesh/svc-{seed}/./api"},
        {"type": "ip_cidr", "value": cidr},
        {"type": "scope", "value": "svc:*"},
        {"type": "scope", "value": "*"},
        {"type": "body_sha256", "value": body_hash},
    ]

    trap_discharges = [
        token("a-small", f"A-{seed}", location, key_id, []),
        token("a-tree", f"A-{seed}", location, key_id, [{"type": "time_after", "value": now}, third(f"B-{seed}", location, key_id)]),
        token("b-link", f"B-{seed}", location, key_id, [{"type": "method", "value": "get"}, third(f"A-{seed}", location, key_id), third(f"A-{seed}", location, key_id)]),
        token("a-leaf", f"A-{seed}", location, key_id, [{"type": "path_prefix", "value": f"/mesh/svc-{seed}"}]),
    ]
    trap = request_template(case, "complete-tree", f"mac-main-{seed}", f"nonce-{seed}", common + [third(f"A-{seed}", location, key_id)], trap_discharges)
    case["requests"].append(
        seal_request(
            case,
            trap,
            attachment_parents={"b-link": "a-tree", "a-leaf": "b-link", "a-small": "b-link"},
        )
    )

    replay = request_template(case, "replay", f"mac-main-{seed}", f"nonce-{seed}", common, [])
    case["requests"].append(seal_request(case, replay))

    multi_caveats = [{"type": "method", "value": "POST"}, {"type": "time_before", "value": now}]
    multi = request_template(case, "additive", f"revoked-{seed}", f"multi-{seed}", multi_caveats, [], root_key_id="root-old")
    multi["timestamp"] = now + case["max_skew_seconds"] + 1
    case["requests"].append(seal_request(case, multi))

    partial_discharges = [
        token("audit-good", f"audit-{seed}", location, key_id, [{"type": "scope", "value": "svc:*"}]),
        token("orphan", f"orphan-{seed}", location, key_id, []),
    ]
    partial = request_template(case, "orphan", f"partial-{seed}", f"partial-nonce-{seed}", [third(f"audit-{seed}", location, key_id)], partial_discharges)
    case["requests"].append(seal_request(case, partial))

    invalid_discharges = [
        token("bad-bind", f"audit-{seed}", location, key_id, []),
        token("inactive", f"audit-{seed}", location, "inactive", []),
    ]
    invalid = request_template(case, "invalid-set", f"invalid-{seed}", f"invalid-nonce-{seed}", [third(f"audit-{seed}", location, key_id)], invalid_discharges)
    case["requests"].append(seal_request(case, invalid, corrupt_bindings={"bad-bind"}))

    bad_primary = request_template(case, "bad-primary", f"bad-primary-{seed}", f"bad-primary-nonce-{seed}", [{"type": "method", "value": "POST"}], [], root_key_id="root-main")
    case["requests"].append(seal_request(case, bad_primary, corrupt_primary=True))

    unknown = request_template(case, "unknown-root", f"unknown-{seed}", f"unknown-nonce-{seed}", [], [], root_key_id="missing-root")
    unknown["timestamp"] = now - case["max_skew_seconds"] - 1
    case["requests"].append(seal_request(case, unknown))

    replayed_discharge = request_template(
        case,
        "replayed-discharge",
        f"replayed-proof-{seed}",
        f"replayed-proof-nonce-{seed}",
        [third(f"A-{seed}", location, key_id)],
        [token("reused-tree", f"A-{seed}", location, key_id, [], replay_id="a-tree")],
    )
    case["requests"].append(seal_request(case, replayed_discharge))

    quorum_caveat = quorum(
        f"quorum-{seed}",
        2,
        [(location, f"vkey-b-{seed}"), (f"backup-{seed}", f"vkey-c-{seed}")],
    )
    quorum_discharges = [
        token("q-b", f"quorum-{seed}", location, f"vkey-b-{seed}", []),
        token("q-c", f"quorum-{seed}", f"backup-{seed}", f"vkey-c-{seed}", []),
    ]
    quorum_request = request_template(
        case,
        "quorum",
        f"quorum-primary-{seed}",
        f"quorum-nonce-{seed}",
        [quorum_caveat],
        quorum_discharges,
    )
    case["requests"].append(seal_request(case, quorum_request))

    if seed > 0:
        boundary = request_template(case, "boundary", f"boundary-{seed}", f"boundary-nonce-{seed}", [], [])
        boundary["timestamp"] = now + case["max_skew_seconds"]
        boundary["path"] = "/../../mesh//svc/../edge/"
        boundary["scopes"] = []
        boundary["macaroon"]["caveats"] = [
            {"type": "time_after", "value": boundary["timestamp"]},
            {"type": "time_before", "value": boundary["timestamp"] + 1},
            {"type": "method", "value": "get"},
            {"type": "path_prefix", "value": "/"},
            {"type": "scope", "value": "not-present:*"},
        ]
        boundary = seal_request(case, boundary)

        local_discharges = [
            token("local-unknown", f"d-revoked-{seed}", location, "missing-key", [{"type": "method", "value": "POST"}]),
            token("local-bad-signature", f"local-{seed}", location, key_id, []),
        ]
        local = request_template(case, "local-audit", f"local-primary-{seed}", f"local-nonce-{seed}", [], local_discharges)
        local = seal_request(case, local, corrupt_discharges={"local-bad-signature"})
        local["discharges"][0]["binding"] = local["discharges"][0]["binding"].upper()

        uppercase = request_template(case, "uppercase-signature", f"uppercase-{seed}", f"uppercase-nonce-{seed}", [], [])
        uppercase = seal_request(case, uppercase)
        uppercase["macaroon"]["signature"] = uppercase["macaroon"]["signature"].upper()

        original = {request["id"].split(f"-{seed}")[0]: request for request in case["requests"]}
        if seed == 1:
            case["requests"] = [boundary, original["replay"]]
        elif seed == 2:
            case["requests"] = [original["additive"], original["bad-primary"], original["unknown-root"], uppercase]
        elif seed == 3:
            case["requests"] = [original["orphan"], local]
        elif seed == 4:
            case["requests"] = [original["invalid-set"], local]
        elif seed in (5, 6):
            case["requests"] = [original["complete-tree"]]
        elif seed in (7, 8):
            case["requests"] = [original["complete-tree"], original["replay"]]
        else:
            case["requests"].extend([boundary, local, uppercase])
    del case["seed"]
    return case


PUBLIC_CASE = generated_case(0)
CASES = {f"generated-{seed:02d}": generated_case(seed) for seed in range(1, 13)}


def adversarial_cases():
    cases = {}

    def base(seed):
        case = generated_case(seed)
        case["seed"] = seed
        case["requests"] = []
        return case

    def finish(case, name):
        case.pop("seed", None)
        cases[name] = case

    case = base(20)
    location, key_id = "verifier-20", "vkey-20"
    request = request_template(case, "bad-attachment", "attach-primary", "attach-nonce", [third("proof", location, key_id)], [token("proof-1", "proof", location, key_id, [])])
    case["requests"] = [seal_request(case, request, corrupt_attachments={"proof-1"})]
    finish(case, "attachment-mismatch-is-edge-failure")

    case = base(21)
    location, key_id = "verifier-21", "vkey-21"
    parent = token("parent", "A", location, key_id, [third("B", location, key_id)])
    child = token("child", "B", location, key_id, [])
    request = request_template(
        case, "wrong-parent", "wrong-parent-primary", "wrong-parent-nonce",
        [third("A", location, key_id), third("B", location, key_id)], [parent, child],
    )
    case["requests"] = [seal_request(case, request)]
    finish(case, "attachment-cannot-move-between-parent-edges")

    case = base(22)
    location, key_id = "verifier-22", "vkey-22"
    caveats = [third("A", location, key_id), third("A", location, key_id)]
    duplicates = [
        token("dup-a", "A", location, key_id, [], replay_id="same-proof"),
        token("dup-b", "A", location, key_id, [], replay_id="same-proof"),
    ]
    request = request_template(case, "duplicate-proof", "duplicate-primary", "duplicate-nonce", caveats, duplicates)
    case["requests"] = [seal_request(case, request)]
    finish(case, "duplicate-persistent-identity-cannot-fill-two-caveats")

    case = base(23)
    location = "verifier-23"
    authorities = [(location, "vkey-23"), (location, "vkey-b-23"), ("backup-23", "vkey-c-23")]
    caveat = quorum("Q", 2, authorities)
    tokens = [
        token("a-good", "Q", *authorities[0], []),
        token("b-bad-edge", "Q", *authorities[1], []),
        token("c-good", "Q", *authorities[2], []),
    ]
    request = request_template(case, "quorum-fallback", "quorum-fallback-primary", "quorum-fallback-nonce", [caveat], tokens)
    case["requests"] = [seal_request(case, request, corrupt_attachments={"b-bad-edge"})]
    finish(case, "quorum-skips-locally-usable-bad-attachment")

    case = base(24)
    location, key_id = "verifier-24", "vkey-24"
    caveat = quorum("Q", 2, [(location, key_id), (location, "vkey-b-24")])
    tokens = [token("same-a", "Q", location, key_id, []), token("same-b", "Q", location, key_id, [])]
    request = request_template(case, "quorum-authority", "quorum-authority-primary", "quorum-authority-nonce", [caveat], tokens)
    case["requests"] = [seal_request(case, request)]
    finish(case, "quorum-requires-distinct-authorities")

    case = base(25)
    location = "verifier-25"
    authorities = [(location, "vkey-25"), (location, "vkey-b-25")]
    caveat = quorum("Q", 1, authorities)
    tokens = [
        token("a-dead", "Q", *authorities[0], [third("missing", location, "vkey-25")]),
        token("z-good", "Q", *authorities[1], []),
    ]
    request = request_template(case, "quorum-backtrack", "quorum-backtrack-primary", "quorum-backtrack-nonce", [caveat], tokens)
    case["requests"] = [seal_request(case, request)]
    finish(case, "quorum-backtracks-after-nested-dead-end")

    case = base(26)
    location = "verifier-26"
    authorities = [(location, "vkey-26"), (location, "vkey-b-26")]
    q = quorum("Q", 2, authorities)
    tokens = [
        token("q-a", "Q", *authorities[0], [third("leaf", location, "vkey-26")]),
        token("q-b", "Q", *authorities[1], []),
        token("z-leaf", "leaf", location, "vkey-26", []),
    ]
    request = request_template(case, "quorum-order", "quorum-order-primary", "quorum-order-nonce", [q], tokens)
    case["requests"] = [seal_request(case, request, attachment_parents={"z-leaf": "q-a"})]
    finish(case, "quorum-members-are-contiguous-before-nested-traversal")

    case = base(27)
    location, key_id = "verifier-27", "vkey-27"
    caveat = third("proof", location, key_id)
    first_tokens = [token("chosen", "proof", location, key_id, []), token("orphan", "orphan", location, key_id, [])]
    first = request_template(case, "partial-spend", "partial-spend-primary", "partial-spend-nonce", [caveat], first_tokens)
    first = seal_request(case, first)
    second_token = token("replayed-copy", "proof", location, key_id, [], replay_id="chosen")
    second = request_template(case, "partial-replay", "partial-replay-primary", "partial-replay-nonce", [caveat], [second_token])
    second = seal_request(case, second)
    case["requests"] = [first, second]
    finish(case, "denied-partial-assignment-still-spends-selected-proof")

    case = base(28)
    location, key_id = "verifier-28", "vkey-28"
    caveat = third("proof", location, key_id)
    bad_token = token("bad-primary-proof", "proof", location, key_id, [], replay_id="shared-proof")
    bad = request_template(case, "bad-does-not-spend", "bad-spend-primary", "bad-spend-nonce", [caveat], [bad_token])
    bad = seal_request(case, bad, corrupt_primary=True)
    good_token = token("good-after-bad", "proof", location, key_id, [], replay_id="shared-proof")
    good = request_template(case, "good-after-bad", "good-spend-primary", "good-spend-nonce", [caveat], [good_token])
    good = seal_request(case, good)
    case["requests"] = [bad, good]
    finish(case, "bad-primary-does-not-spend-discharge")

    case = base(29)
    location, key_id = "verifier-29", "vkey-29"
    caveat = third("proof", location, key_id)
    inactive_token = token("inactive-use", "proof", location, key_id, [], replay_id="inactive-spend")
    inactive = request_template(case, "inactive-spend", "inactive-primary", "inactive-nonce", [caveat], [inactive_token], root_key_id="root-old")
    inactive["timestamp"] = case["evaluation_time"]
    inactive = seal_request(case, inactive)
    replay_token = token("after-inactive", "proof", location, key_id, [], replay_id="inactive-spend")
    after = request_template(case, "after-inactive", "after-inactive-primary", "after-inactive-nonce", [caveat], [replay_token])
    after = seal_request(case, after)
    case["requests"] = [inactive, after]
    finish(case, "authenticated-inactive-root-still-spends-discharge")

    case = base(30)
    location, key_id = "verifier-30", "inactive"
    replay_id = "pre-spent-30"
    case["spent_discharges"].append({"location": location, "key_id": key_id, "replay_id": replay_id})
    caveat = third("d-revoked-30", location, key_id)
    bad = token("all-local-reasons", "d-revoked-30", location, key_id, [{"type": "method", "value": "POST"}], replay_id=replay_id)
    request = request_template(case, "local-additive", "local-additive-primary", "local-additive-nonce", [caveat], [bad])
    request = seal_request(case, request, corrupt_discharges={"all-local-reasons"}, corrupt_bindings={"all-local-reasons"})
    case["requests"] = [request]
    finish(case, "local-reasons-include-persisted-replay-in-order")

    case = base(31)
    request = request_template(case, "preloaded-nonce", "pre-reserved-31", "pre-nonce-31", [], [])
    case["requests"] = [seal_request(case, request)]
    finish(case, "preloaded-nonce-state-causes-replay")

    return cases


CASES.update(adversarial_cases())


def run_case(case):
    with tempfile.TemporaryDirectory(prefix="macaroon-audit-trace-") as trace_directory:
        return run_case_with_trace(case, Path(trace_directory) / "execve.trace")


def stable_file_state(path):
    metadata = path.stat()
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def run_case_with_trace(case, trace_path=None):
    shutil.rmtree(APP / "input", ignore_errors=True)
    shutil.rmtree(APP / "output", ignore_errors=True)
    INPUT.parent.mkdir()
    OUTPUT.parent.mkdir()
    INPUT.write_text(json.dumps(case, indent=2), encoding="utf-8")
    input_bytes = INPUT.read_bytes()
    input_state = stable_file_state(INPUT)
    command = [str(BIN)]
    if trace_path is not None:
        command = [
            "/usr/bin/strace",
            "-f",
            "-qq",
            "-e",
            "trace=execve",
            "-o",
            str(trace_path),
            str(BIN),
        ]
    result = subprocess.run(command, cwd=APP, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    if trace_path is not None:
        exec_calls = [
            line
            for line in trace_path.read_text(encoding="utf-8").splitlines()
            if "execve(" in line
        ]
        assert len(exec_calls) == 1, "the decision engine delegated work to another executable"
        assert f'execve("{BIN}"' in exec_calls[0]
    assert INPUT.is_file(), "the program removed /app/input/inspection.json"
    assert INPUT.read_bytes() == input_bytes, "the program changed /app/input/inspection.json"
    assert stable_file_state(INPUT) == input_state, "the program rewrote or changed metadata on /app/input/inspection.json"
    assert OUTPUT.is_file(), "missing /app/output/report.json"
    with OUTPUT.open(encoding="utf-8") as handle:
        return json.load(handle)


def by_id(report):
    return {decision["id"]: decision for decision in report["decisions"]}


def test_native_artifact_executes_without_helper_process(tmp_path):
    assert BIN.read_bytes()[:4] == b"\x7fELF"
    trace_path = tmp_path / "execve.trace"
    assert run_case_with_trace(PUBLIC_CASE, trace_path) == expected_report(PUBLIC_CASE)


def test_public_full_report_and_preserves_input():
    assert run_case(PUBLIC_CASE) == expected_report(PUBLIC_CASE)


def test_public_complete_tree_defeats_local_greedy_choice():
    actual = by_id(run_case(PUBLIC_CASE))["complete-tree-0"]
    assert actual["decision"] == "allow"
    assert actual["used_discharges"] == ["a-tree", "b-link", "a-leaf", "a-small"]


def test_public_replay_and_additive_state_rules():
    actual = by_id(run_case(PUBLIC_CASE))
    assert actual["replay-0"]["reasons"] == ["replayed_nonce"]
    assert actual["additive-0"]["reasons"] == [
        "root_key_inactive",
        "revoked_identifier",
        "timestamp_skew",
        "first_party_unsatisfied",
    ]


def test_public_partial_and_impossible_discharge_sets():
    actual = by_id(run_case(PUBLIC_CASE))
    assert actual["orphan-0"]["used_discharges"] == ["audit-good"]
    assert actual["orphan-0"]["reasons"] == ["unused_discharge"]
    assert actual["invalid-set-0"]["used_discharges"] == []
    assert actual["invalid-set-0"]["reasons"] == ["third_party_unsatisfied", "unused_discharge"]


def test_public_signature_gates_and_local_discharge_audit():
    actual = by_id(run_case(PUBLIC_CASE))
    assert actual["bad-primary-0"]["reasons"] == ["bad_primary_signature"]
    assert actual["unknown-root-0"]["reasons"] == ["unknown_root_key", "timestamp_skew"]
    local = actual["invalid-set-0"]["discharge_results"]
    assert local[0]["reasons"] == ["bad_binding"]
    assert local[1]["reasons"] == ["discharge_key_inactive"]


def test_public_quorum_attachment_and_spent_replay_state():
    report = run_case(PUBLIC_CASE)
    actual = by_id(report)
    assert actual["quorum-0"]["decision"] == "allow"
    assert actual["quorum-0"]["used_discharges"] == ["q-b", "q-c"]
    replayed = actual["replayed-discharge-0"]
    assert replayed["reasons"] == ["third_party_unsatisfied", "unused_discharge"]
    assert replayed["discharge_results"][0]["reasons"] == ["replayed_discharge"]
    assert report["final_state"]["spent_discharges"][-2:] == [
        {"location": "verifier-0", "key_id": "vkey-b-0", "replay_id": "q-b"},
        {"location": "backup-0", "key_id": "vkey-c-0", "replay_id": "q-c"},
    ]


def test_report_schema_is_exact():
    report = run_case(PUBLIC_CASE)
    assert set(report) == {"evaluated_at", "decisions", "summary", "final_state"}
    assert set(report["summary"]) == {"allowed", "denied", "reason_counts"}
    assert set(report["final_state"]) == {"reserved_nonces", "spent_discharges"}
    decision_fields = {"id", "decision", "reasons", "normalized", "primary_caveats", "used_discharges", "discharge_results"}
    normalized_fields = {"method", "path", "ip", "scopes", "body_sha256"}
    assert all(set(row) == decision_fields and set(row["normalized"]) == normalized_fields for row in report["decisions"])
    assert all(set(row) == {"instance_id", "usable", "reasons"} for decision in report["decisions"] for row in decision["discharge_results"])


@pytest.mark.parametrize("name", sorted(CASES))
def test_generated_compatibility_case(name):
    case = CASES[name]
    assert run_case(case) == expected_report(case)


def test_generated_matrix_covers_protocol_dimensions():
    observed = set()
    for case in [PUBLIC_CASE, *CASES.values()]:
        report = run_case(case)
        for decision in report["decisions"]:
            observed.update(decision["reasons"])
            if ":" in decision["normalized"]["ip"]:
                observed.add("ipv6")
            if decision["used_discharges"] == ["a-tree", "b-link", "a-leaf", "a-small"]:
                observed.add("global_assignment")
            if any(caveat.startswith("third_party_quorum|") for caveat in decision["primary_caveats"]):
                observed.add("quorum")
            for result in decision["discharge_results"]:
                observed.update(result["reasons"])
    assert {
        "ipv6",
        "global_assignment",
        "quorum",
        "replayed_nonce",
        "root_key_inactive",
        "revoked_identifier",
        "timestamp_skew",
        "first_party_unsatisfied",
        "third_party_unsatisfied",
        "unused_discharge",
        "bad_binding",
        "unknown_discharge_key",
        "bad_discharge_signature",
        "discharge_key_inactive",
        "replayed_discharge",
    } <= observed
