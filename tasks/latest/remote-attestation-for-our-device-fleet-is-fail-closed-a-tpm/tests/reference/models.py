"""Input loading and structural validation (fatal errors).

`allowed_versions` and `allowed_digests` accept any unique order and are
normalized to sorted order on load (physical input order is irrelevant).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .binary import decode_lower_hex, require_exact_hex
from .p256 import parse_sec1_public_key
from .protected_inputs import ProtectedInputSnapshot
from .quote import SUPPORTED_PCRS


class FatalError(Exception):
    pass


def _norm_id(v: Any, field: str) -> str:
    if not isinstance(v, str):
        raise FatalError(f"{field} must be string")
    s = v.strip()
    if not s:
        raise FatalError(f"{field} empty")
    return s


def _u32(v: Any, field: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise FatalError(f"{field} must be integer")
    if v < 0 or v > 0xFFFFFFFF:
        raise FatalError(f"{field} out of u32 range")
    return v


def _u64(v: Any, field: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise FatalError(f"{field} must be integer")
    if v < 0 or v > 0xFFFFFFFFFFFFFFFF:
        raise FatalError(f"{field} out of u64 range")
    return v


def _expect_keys(obj: dict, required: set[str], label: str) -> None:
    if not isinstance(obj, dict):
        raise FatalError(f"{label} must be object")
    keys = set(obj.keys())
    missing = required - keys
    extra = keys - required
    if missing:
        raise FatalError(f"{label} missing fields: {sorted(missing)}")
    if extra:
        raise FatalError(f"{label} unknown fields: {sorted(extra)}")


def _sorted_unique_strs(arr: Any, field: str, *, nonempty_items: bool = True) -> list[str]:
    if not isinstance(arr, list):
        raise FatalError(f"{field} must be array")
    out: list[str] = []
    seen: set[str] = set()
    for i, x in enumerate(arr):
        if not isinstance(x, str):
            raise FatalError(f"{field}[{i}] must be string")
        s = x.strip() if nonempty_items else x
        if nonempty_items and not s:
            raise FatalError(f"{field}[{i}] empty")
        item = s if nonempty_items else x
        if item in seen:
            raise FatalError(f"{field} duplicate")
        seen.add(item)
        out.append(item)
    # Normalize to sorted order (physical input order is irrelevant).
    return sorted(out)


def _has_cycle(edges: list[tuple[str, str]]) -> bool:
    from collections import defaultdict, deque

    graph: dict[str, list[str]] = defaultdict(list)
    nodes: set[str] = set()
    for a, b in edges:
        graph[a].append(b)
        nodes.add(a)
        nodes.add(b)
    indeg = {n: 0 for n in nodes}
    for a, b in edges:
        indeg[b] = indeg.get(b, 0) + 1
        indeg.setdefault(a, indeg.get(a, 0))
    q = deque([n for n, d in indeg.items() if d == 0])
    seen = 0
    while q:
        n = q.popleft()
        seen += 1
        for m in graph.get(n, []):
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    return seen != len(nodes)


@dataclass
class Dataset:
    devices: dict[str, dict]
    keys: dict[str, dict]
    policies: dict[str, dict]
    event_logs: dict[str, dict]
    nonces: dict[str, dict]
    requests: list[dict]
    policy_limits: dict
    raw_files: dict[str, bytes] = field(default_factory=dict)


def load_dataset(snapshot: ProtectedInputSnapshot) -> Dataset:
    import json

    def jload(name: str) -> Any:
        try:
            return json.loads(snapshot.get(name).decode("utf-8"))
        except Exception as e:
            raise FatalError(f"unreadable JSON {name}: {e}") from e

    limits = jload("policy.json")
    _expect_keys(
        limits,
        {
            "maximum_devices",
            "maximum_attestation_keys",
            "maximum_reference_policies",
            "maximum_event_logs",
            "maximum_events_per_log",
            "maximum_total_events",
            "maximum_nonce_challenges",
            "maximum_requests",
            "maximum_quote_bytes",
            "maximum_signature_bytes",
        },
        "policy.json",
    )
    for k, v in limits.items():
        limits[k] = _u32(v, k)

    devices_raw = jload("devices.json")
    if not isinstance(devices_raw, list):
        raise FatalError("devices.json must be array")
    if len(devices_raw) > limits["maximum_devices"]:
        raise FatalError("maximum_devices exceeded")
    devices: dict[str, dict] = {}
    for i, rec in enumerate(devices_raw):
        _expect_keys(
            rec,
            {"device_id", "device_class", "last_reset_count", "last_restart_count", "last_clock"},
            f"devices[{i}]",
        )
        did = _norm_id(rec["device_id"], "device_id")
        if did in devices:
            raise FatalError(f"duplicate device_id {did}")
        devices[did] = {
            "device_id": did,
            "device_class": _norm_id(rec["device_class"], "device_class"),
            "last_reset_count": _u32(rec["last_reset_count"], "last_reset_count"),
            "last_restart_count": _u32(rec["last_restart_count"], "last_restart_count"),
            "last_clock": _u64(rec["last_clock"], "last_clock"),
        }

    keys_raw = jload("attestation_keys.json")
    if not isinstance(keys_raw, list):
        raise FatalError("attestation_keys.json must be array")
    if len(keys_raw) > limits["maximum_attestation_keys"]:
        raise FatalError("maximum_attestation_keys exceeded")
    keys: dict[str, dict] = {}
    for i, rec in enumerate(keys_raw):
        _expect_keys(
            rec,
            {
                "attestation_key_id",
                "device_id",
                "qualified_name_hex",
                "public_key_sec1_hex",
                "valid_from",
                "valid_until",
            },
            f"keys[{i}]",
        )
        kid = _norm_id(rec["attestation_key_id"], "attestation_key_id")
        if kid in keys:
            raise FatalError(f"duplicate attestation_key_id {kid}")
        did = _norm_id(rec["device_id"], "device_id")
        if did not in devices:
            raise FatalError(f"unknown device_id in key {kid}")
        qn = require_exact_hex(rec["qualified_name_hex"], 34)
        pk = require_exact_hex(rec["public_key_sec1_hex"], 65)
        try:
            parse_sec1_public_key(pk)
        except ValueError as e:
            raise FatalError(f"invalid public key {kid}: {e}") from e
        vf = _u64(rec["valid_from"], "valid_from")
        vu = _u64(rec["valid_until"], "valid_until")
        if vf > vu:
            raise FatalError(f"valid_from > valid_until for {kid}")
        keys[kid] = {
            "attestation_key_id": kid,
            "device_id": did,
            "qualified_name_hex": rec["qualified_name_hex"],
            "qualified_name": qn,
            "public_key_sec1_hex": rec["public_key_sec1_hex"],
            "public_key_sec1": pk,
            "valid_from": vf,
            "valid_until": vu,
        }

    pols_raw = jload("reference_policies.json")
    if not isinstance(pols_raw, list):
        raise FatalError("reference_policies.json must be array")
    if len(pols_raw) > limits["maximum_reference_policies"]:
        raise FatalError("maximum_reference_policies exceeded")
    policies: dict[str, dict] = {}
    for i, rec in enumerate(pols_raw):
        _expect_keys(
            rec,
            {
                "policy_id",
                "allowed_device_classes",
                "required_pcrs",
                "allowed_firmware_versions",
                "require_safe",
                "unknown_event_mode",
                "measurement_rules",
                "order_constraints",
            },
            f"policies[{i}]",
        )
        pid = _norm_id(rec["policy_id"], "policy_id")
        if pid in policies:
            raise FatalError(f"duplicate policy_id {pid}")
        if not isinstance(rec["allowed_device_classes"], list) or not rec["allowed_device_classes"]:
            raise FatalError(f"allowed_device_classes for {pid}")
        classes = [_norm_id(x, "device_class") for x in rec["allowed_device_classes"]]
        if len(classes) != len(set(classes)):
            raise FatalError("duplicate allowed_device_classes")
        if not isinstance(rec["required_pcrs"], list) or not rec["required_pcrs"]:
            raise FatalError("required_pcrs empty")
        req_pcrs: list[int] = []
        for p in rec["required_pcrs"]:
            p = _u32(p, "pcr")
            if p not in SUPPORTED_PCRS:
                raise FatalError("unsupported required pcr")
            if p in req_pcrs:
                raise FatalError("duplicate required pcr")
            req_pcrs.append(p)
        req_pcrs_sorted = sorted(req_pcrs)
        if not isinstance(rec["require_safe"], bool):
            raise FatalError("require_safe must be bool")
        mode = rec["unknown_event_mode"]
        if mode not in ("allow", "reject"):
            raise FatalError("unknown_event_mode")
        if not isinstance(rec["allowed_firmware_versions"], list):
            raise FatalError("allowed_firmware_versions")
        fw: list[int] = []
        for x in rec["allowed_firmware_versions"]:
            fw.append(_u64(x, "firmware"))
        if len(fw) != len(set(fw)):
            raise FatalError("duplicate firmware versions")
        if not isinstance(rec["measurement_rules"], list):
            raise FatalError("measurement_rules")
        rules: dict[str, dict] = {}
        selectors: set[tuple] = set()
        for j, rule in enumerate(rec["measurement_rules"]):
            _expect_keys(
                rule,
                {
                    "rule_id",
                    "kind",
                    "pcr_index",
                    "event_type",
                    "component",
                    "allowed_versions",
                    "allowed_digests",
                },
                f"rule[{j}]",
            )
            rid = _norm_id(rule["rule_id"], "rule_id")
            if rid in rules:
                raise FatalError(f"duplicate rule_id {rid}")
            kind = rule["kind"]
            if kind not in ("required", "optional", "forbidden"):
                raise FatalError("rule kind")
            pcr = _u32(rule["pcr_index"], "pcr_index")
            if pcr not in SUPPORTED_PCRS:
                raise FatalError("unsupported pcr in rule")
            et = _norm_id(rule["event_type"], "event_type")
            comp = _norm_id(rule["component"], "component")
            sel = (pcr, et, comp)
            if sel in selectors:
                raise FatalError("duplicate measurement rule selector")
            selectors.add(sel)
            vers = rule["allowed_versions"]
            digs = rule["allowed_digests"]
            if not isinstance(vers, list) or not isinstance(digs, list):
                raise FatalError("allow lists must be arrays")
            if kind == "forbidden":
                if vers or digs:
                    raise FatalError("forbidden rule arrays must be empty")
                versions: list[str] = []
                digests: list[str] = []
            else:
                versions = _sorted_unique_strs(vers, "allowed_versions")
                if not versions:
                    raise FatalError("allowed_versions nonempty required")
                digests = []
                seen_d: set[str] = set()
                for d in digs:
                    if not isinstance(d, str):
                        raise FatalError("digest must be string")
                    require_exact_hex(d, 32)
                    if d in seen_d:
                        raise FatalError("duplicate digest")
                    seen_d.add(d)
                    digests.append(d)
                digests = sorted(digests)
                if not digests:
                    raise FatalError("allowed_digests nonempty required")
            rules[rid] = {
                "rule_id": rid,
                "kind": kind,
                "pcr_index": pcr,
                "event_type": et,
                "component": comp,
                "allowed_versions": versions,
                "allowed_digests": digests,
            }
        if not isinstance(rec["order_constraints"], list):
            raise FatalError("order_constraints")
        constraints: list[dict] = []
        seen_c: set[tuple[str, str]] = set()
        edges: list[tuple[str, str]] = []
        for c in rec["order_constraints"]:
            _expect_keys(c, {"before_rule_id", "after_rule_id"}, "order_constraint")
            b = _norm_id(c["before_rule_id"], "before_rule_id")
            a = _norm_id(c["after_rule_id"], "after_rule_id")
            if b not in rules or a not in rules:
                raise FatalError("unknown order-constraint rule")
            if b == a:
                raise FatalError("self order constraint")
            if rules[b]["kind"] == "forbidden" or rules[a]["kind"] == "forbidden":
                raise FatalError("order constraint on forbidden rule")
            key = (b, a)
            if key in seen_c:
                raise FatalError("duplicate order constraint")
            seen_c.add(key)
            edges.append(key)
            constraints.append({"before_rule_id": b, "after_rule_id": a})
        if _has_cycle(edges):
            raise FatalError("cyclic order constraints")
        policies[pid] = {
            "policy_id": pid,
            "allowed_device_classes": classes,
            "required_pcrs": req_pcrs_sorted,
            "allowed_firmware_versions": fw,
            "require_safe": rec["require_safe"],
            "unknown_event_mode": mode,
            "measurement_rules": rules,
            "order_constraints": constraints,
        }

    logs_raw = jload("event_logs.json")
    if not isinstance(logs_raw, list):
        raise FatalError("event_logs.json must be array")
    if len(logs_raw) > limits["maximum_event_logs"]:
        raise FatalError("maximum_event_logs exceeded")
    event_logs: dict[str, dict] = {}
    total_events = 0
    for i, rec in enumerate(logs_raw):
        _expect_keys(rec, {"event_log_id", "device_id", "events"}, f"event_logs[{i}]")
        lid = _norm_id(rec["event_log_id"], "event_log_id")
        if lid in event_logs:
            raise FatalError(f"duplicate event_log_id {lid}")
        did = _norm_id(rec["device_id"], "device_id")
        if did not in devices:
            raise FatalError(f"unknown device in event log {lid}")
        if not isinstance(rec["events"], list):
            raise FatalError("events must be array")
        if len(rec["events"]) > limits["maximum_events_per_log"]:
            raise FatalError("maximum_events_per_log exceeded")
        events = []
        seqs: set[int] = set()
        for j, ev in enumerate(rec["events"]):
            _expect_keys(
                ev,
                {
                    "event_seq",
                    "pcr_index",
                    "event_type",
                    "component",
                    "version",
                    "measurement_digest",
                },
                f"event[{j}]",
            )
            seq = _u32(ev["event_seq"], "event_seq")
            if seq in seqs:
                raise FatalError("duplicate event_seq")
            seqs.add(seq)
            pcr = _u32(ev["pcr_index"], "pcr_index")
            if pcr not in SUPPORTED_PCRS:
                raise FatalError("unsupported PCR index in event")
            ver = ev["version"]
            if not isinstance(ver, str) or not ver:
                raise FatalError("version nonempty")
            require_exact_hex(ev["measurement_digest"], 32)
            events.append(
                {
                    "event_seq": seq,
                    "pcr_index": pcr,
                    "event_type": _norm_id(ev["event_type"], "event_type"),
                    "component": _norm_id(ev["component"], "component"),
                    "version": ver,
                    "measurement_digest": ev["measurement_digest"],
                }
            )
            total_events += 1
        if total_events > limits["maximum_total_events"]:
            raise FatalError("maximum_total_events exceeded")
        event_logs[lid] = {"event_log_id": lid, "device_id": did, "events": events}

    nonces_raw = jload("nonce_challenges.json")
    if not isinstance(nonces_raw, list):
        raise FatalError("nonce_challenges.json must be array")
    if len(nonces_raw) > limits["maximum_nonce_challenges"]:
        raise FatalError("maximum_nonce_challenges exceeded")
    nonces: dict[str, dict] = {}
    for i, rec in enumerate(nonces_raw):
        _expect_keys(
            rec,
            {
                "nonce_id",
                "device_id",
                "nonce_hex",
                "issued_at",
                "expires_at",
                "initially_consumed_by_request_id_or_null",
            },
            f"nonces[{i}]",
        )
        nid = _norm_id(rec["nonce_id"], "nonce_id")
        if nid in nonces:
            raise FatalError(f"duplicate nonce_id {nid}")
        did = _norm_id(rec["device_id"], "device_id")
        if did not in devices:
            raise FatalError(f"unknown device in nonce {nid}")
        require_exact_hex(rec["nonce_hex"], 32)
        issued = _u64(rec["issued_at"], "issued_at")
        expires = _u64(rec["expires_at"], "expires_at")
        if issued > expires:
            raise FatalError("issued_at > expires_at")
        init = rec["initially_consumed_by_request_id_or_null"]
        if init is not None:
            if not isinstance(init, str) or not init.strip():
                raise FatalError("initially_consumed invalid")
            init = init.strip()
        nonces[nid] = {
            "nonce_id": nid,
            "device_id": did,
            "nonce_hex": rec["nonce_hex"],
            "nonce_bytes": decode_lower_hex(rec["nonce_hex"]),
            "issued_at": issued,
            "expires_at": expires,
            "initially_consumed_by_request_id_or_null": init,
        }

    try:
        text = snapshot.get("quote_requests.ndjson").decode("utf-8")
    except Exception as e:
        raise FatalError(f"unreadable NDJSON: {e}") from e
    requests: list[dict] = []
    seen_rid: set[str] = set()
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except Exception as e:
            raise FatalError(f"bad NDJSON line {line_no}: {e}") from e
        _expect_keys(
            rec,
            {
                "request_id",
                "received_at",
                "device_id",
                "attestation_key_id",
                "nonce_id",
                "policy_id",
                "event_log_id",
                "quote_hex",
                "signature_hex",
            },
            f"request line {line_no}",
        )
        rid = _norm_id(rec["request_id"], "request_id")
        if rid in seen_rid:
            raise FatalError(f"duplicate request_id {rid}")
        seen_rid.add(rid)
        qh = rec["quote_hex"]
        sh = rec["signature_hex"]
        if not isinstance(qh, str) or not isinstance(sh, str):
            raise FatalError("quote/signature hex must be strings")
        try:
            qb = decode_lower_hex(qh)
            sb = decode_lower_hex(sh)
        except ValueError as e:
            raise FatalError(f"malformed request hex {rid}: {e}") from e
        if len(qb) > limits["maximum_quote_bytes"]:
            raise FatalError("maximum_quote_bytes exceeded")
        if len(sb) > limits["maximum_signature_bytes"]:
            raise FatalError("maximum_signature_bytes exceeded")
        requests.append(
            {
                "request_id": rid,
                "received_at": _u64(rec["received_at"], "received_at"),
                "device_id": _norm_id(rec["device_id"], "device_id"),
                "attestation_key_id": _norm_id(rec["attestation_key_id"], "attestation_key_id"),
                "nonce_id": _norm_id(rec["nonce_id"], "nonce_id"),
                "policy_id": _norm_id(rec["policy_id"], "policy_id"),
                "event_log_id": _norm_id(rec["event_log_id"], "event_log_id"),
                "quote_hex": qh,
                "signature_hex": sh,
                "quote_bytes": qb,
                "signature_bytes": sb,
            }
        )
    if len(requests) > limits["maximum_requests"]:
        raise FatalError("maximum_requests exceeded")

    return Dataset(
        devices=devices,
        keys=keys,
        policies=policies,
        event_logs=event_logs,
        nonces=nonces,
        requests=requests,
        policy_limits=limits,
        raw_files=dict(snapshot.files),
    )
