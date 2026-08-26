"""Reference implementation of the CDSS v4 release gate.

Generated from rulebook.yaml by authoring/generate.py. Do not edit by hand.

Every predicate in this module mirrors a normative rule stated in the shipped
standard document. The property battery in test_outputs.py runs both the
Java service and this engine over the same scenarios and asserts that their
decisions agree.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


# Zone table: zone name -> (port_list set, list of (lo, hi) ranges).
ZONES = {'web': ({6379, 8443, 80, 8080, 443, 8444, 8445, 8446}, [(8000, 8999)]), 'internal': (set(), [(9000, 9999)]), 'loopback': (set(), [(7000, 7999)])}

# Ordered list of {id, code, title, applies_to, predicate}.
CLAUSES = [{'id': '§8.1', 'code': 'CDSS-SVC-008', 'title': 'Privileged containers forbidden', 'applies_to': 'all', 'predicate': 'no_privileged_true'}, {'id': '§9.4', 'code': 'CDSS-SVC-009', 'title': 'Capability drop required for non-infra services', 'applies_to': 'not_infra', 'predicate': 'caps_dropped_all'}, {'id': '§10.2', 'code': 'CDSS-SVC-010', 'title': 'Images pinned by digest', 'applies_to': 'all', 'predicate': 'image_pinned_sha256'}, {'id': '§11.1', 'code': 'CDSS-SVC-011', 'title': 'No secret material in environment', 'applies_to': 'all', 'predicate': 'no_secret_env_keys'}, {'id': '§12.3', 'code': 'CDSS-SVC-012', 'title': 'Read-only root filesystem for web-tier services', 'applies_to': 'web-tier', 'predicate': 'read_only_true'}, {'id': '§13.1', 'code': 'CDSS-SVC-013', 'title': 'Host networking forbidden except infra', 'applies_to': 'not_infra', 'predicate': 'no_host_network'}, {'id': '§14.5', 'code': 'CDSS-SVC-014', 'title': 'Bind mount source prefix allowlist', 'applies_to': 'all', 'predicate': 'bind_prefix_allowlist'}]

# Reason code emitted for compose-model absence (§24.9).
COMPOSE_MISSING_CODE = "CDSS-SVC-024"
COMPOSE_MISSING_CLAUSE = "§24.9"

HOOK_CODE = "CDSS-HOOK-022"
HOOK_CLAUSE = "§22.4"

KEY_APPROVAL_CODE = "CDSS-KEY-017"
KEY_APPROVAL_CLAUSE = "§17.1"

SIGNATURE_INVALID_CODE = "CDSS-KEY-INVSIG"
SIGNATURE_INVALID_CLAUSE = "§17.1"

NON_WAIVABLE_CLAUSES = {'§8.1', '§14.5'}

CAP_ALLOWLIST = {"NET_BIND_SERVICE", "CHOWN", "SETUID", "SETGID", "DAC_OVERRIDE"}

SECRET_KEY_SUBSTRINGS = ("password", "passwd", "secret", "token", "api_key",
                          "apikey", "private_key")

BIND_PREFIX_ALLOWLIST = ("/srv/gate/", "/var/opt/gate/", "/opt/gate-data/")

# Amendment 7: withdraws the §12.3 cache-class exemption for services
# reclassified as web-tier via port zone. effective_date determines whether
# a given exception window suspends the amendment's added obligation.
AMENDMENT_7_EFFECTIVE = datetime.fromisoformat("2026-05-01T00:00:00+00:00")
AMENDMENT_7_CLAUSE = "§12.3"
AMENDMENT_7_SCOPE = "cache_web_tier_via_port_zone"


# ---------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------

@dataclass
class ApprovedKey:
    fingerprint: str
    owner: str
    status: str
    approved_at: datetime
    revoked_at: datetime | None


@dataclass
class ExceptionWindow:
    id: int
    clause_id: str
    service_glob: str
    starts_at: datetime
    ends_at: datetime
    approved_at: datetime


@dataclass
class InfraRegistry:
    services: set[str] = field(default_factory=set)


@dataclass
class TagEvidence:
    signature_valid: bool
    fingerprint: str | None
    tag_created_at: datetime | None


@dataclass
class Repository:
    root: Path
    hooks_path: str | None
    pre_push_executable: bool
    pre_push_marker_sha: str | None
    resolved_services: dict


@dataclass
class DecisionReason:
    code: str
    clause_id: str
    service: str

    def sort_key(self):
        return (self.code, self.service, self.clause_id)


# ---------------------------------------------------------------------
# Compose merge
# ---------------------------------------------------------------------

def merge_compose(base: dict | None, override: dict | None) -> dict:
    """Apply CDSS v4 merge (§24.2-§24.5)."""
    if base is None and override is None:
        return {}
    if base is None:
        return dict(override or {})
    if override is None:
        return dict(base)
    result: dict = {}
    services: dict = {}
    for name, svc in (base.get("services") or {}).items():
        services[name] = dict(svc or {})
    for name, ov in (override.get("services") or {}).items():
        if name in services:
            services[name] = _merge_service(services[name], ov or {})
        else:
            services[name] = dict(ov or {})
    result["services"] = services
    for key in set((base or {}).keys()) | set((override or {}).keys()):
        if key == "services":
            continue
        if key in (override or {}):
            result[key] = (override or {}).get(key)
        else:
            result[key] = (base or {}).get(key)
    return result


def _merge_service(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if v is None:
            result.pop(k, None)
            continue
        if isinstance(v, list):
            # §24.4: list values in override REPLACE base list wholesale.
            result[k] = list(v)
        elif isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _merge_dict(result[k], v)
        else:
            result[k] = v
    return result


def _merge_dict(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if v is None:
            result.pop(k, None)
            continue
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _merge_dict(result[k], v)
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------
# Zone-derived tier
# ---------------------------------------------------------------------

def port_zone(port: int) -> str | None:
    for name, (plist, ranges) in ZONES.items():
        if port in plist:
            return name
        for lo, hi in ranges:
            if lo <= port <= hi:
                return name
    return None


def _iter_host_ports(service: dict):
    for entry in service.get("ports", []) or []:
        for p in _parse_port_entry(entry):
            yield p


def _parse_port_entry(entry: Any):
    if isinstance(entry, int):
        return []
    if isinstance(entry, str):
        text = entry
    elif isinstance(entry, dict):
        pub = entry.get("published")
        if pub is None:
            return []
        try:
            return [int(pub)]
        except (TypeError, ValueError):
            return []
    else:
        return []
    parts = text.split(":")
    if len(parts) >= 2:
        host = parts[-2]
    else:
        host = parts[-1]
    if "-" in host:
        lo, hi = host.split("-", 1)
        try:
            return list(range(int(lo), int(hi) + 1))
        except ValueError:
            return []
    try:
        return [int(host)]
    except ValueError:
        return []


def _normalize_labels(labels: Any) -> dict:
    if labels is None:
        return {}
    if isinstance(labels, dict):
        return {str(k): "" if v is None else str(v) for k, v in labels.items()}
    if isinstance(labels, list):
        out = {}
        for entry in labels:
            if isinstance(entry, str) and "=" in entry:
                k, _, v = entry.partition("=")
                out[k] = v
        return out
    return {}


def label_tier(service: dict) -> str | None:
    return _normalize_labels(service.get("labels")).get("cdss.tier")


def is_web_tier(service: dict) -> bool:
    # §1.3: port-zone derivation supersedes label. If any host-side port
    # falls in the web zone, the service is web-tier regardless of label.
    for p in _iter_host_ports(service):
        if port_zone(p) == "web":
            return True
    return label_tier(service) == "web"


def web_by_port_zone(service: dict) -> bool:
    """True if the service becomes web-tier by port-zone derivation."""
    for p in _iter_host_ports(service):
        if port_zone(p) == "web":
            return True
    return False


def is_cache_class(service: dict) -> bool:
    return _normalize_labels(service.get("labels")).get("cdss.class") == "cache"


def is_infra_tier(service_name: str, service: dict, infra: InfraRegistry) -> bool:
    has_label = _normalize_labels(service.get("labels")).get("cdss.tier") == "infra"
    return has_label and service_name in infra.services


# ---------------------------------------------------------------------
# Clause predicates
# ---------------------------------------------------------------------

def _no_privileged_true(service: dict) -> bool:
    return not bool(service.get("privileged"))


def _caps_dropped_all(service: dict) -> bool:
    drops = service.get("cap_drop") or []
    if isinstance(drops, str):
        drops = [drops]
    if "ALL" not in [str(x).upper() for x in drops]:
        return False
    for cap in service.get("cap_add") or []:
        if str(cap).upper() not in CAP_ALLOWLIST:
            return False
    return True


IMAGE_PIN_RE = re.compile(r"^[^\s]+@sha256:[0-9a-fA-F]{64}$")


def _image_pinned_sha256(service: dict) -> bool:
    image = service.get("image")
    if not isinstance(image, str) or not image:
        return False
    return bool(IMAGE_PIN_RE.match(image))


def _no_secret_env_keys(service: dict) -> bool:
    env = service.get("environment")
    if env is None:
        return True
    keys = []
    if isinstance(env, dict):
        keys = list(env.keys())
    elif isinstance(env, list):
        for entry in env:
            if isinstance(entry, str):
                keys.append(entry.split("=", 1)[0])
    for k in keys:
        low = str(k).lower()
        for needle in SECRET_KEY_SUBSTRINGS:
            if needle in low:
                return False
    return True


def _read_only_true(service: dict) -> bool:
    return service.get("read_only") is True


def _no_host_network(service: dict) -> bool:
    return service.get("network_mode") != "host"


def _bind_prefix_allowlist(service: dict) -> bool:
    vols = service.get("volumes") or []
    for entry in vols:
        source = _volume_source(entry)
        if source is None:
            continue
        if not source.startswith(("/", ".")):
            continue
        if source.startswith("."):
            return False
        if source == "/var/run/docker.sock":
            return False
        if not any(source.startswith(p) for p in BIND_PREFIX_ALLOWLIST):
            return False
    return True


def _volume_source(entry: Any) -> str | None:
    if isinstance(entry, str):
        parts = entry.split(":")
        return parts[0] if parts else None
    if isinstance(entry, dict):
        src = entry.get("source")
        return str(src) if src is not None else None
    return None


PREDICATES = {
    "no_privileged_true": _no_privileged_true,
    "caps_dropped_all": _caps_dropped_all,
    "image_pinned_sha256": _image_pinned_sha256,
    "no_secret_env_keys": _no_secret_env_keys,
    "read_only_true": _read_only_true,
    "no_host_network": _no_host_network,
    "bind_prefix_allowlist": _bind_prefix_allowlist,
}


# ---------------------------------------------------------------------
# Applicability + Amendment 7 conditional
# ---------------------------------------------------------------------

def _clause_applies(clause: dict, service_name: str, service: dict,
                    infra: InfraRegistry) -> tuple[bool, str]:
    """
    Return (applies, subject) where subject in {'base', 'a7'} for §12.3.
    subject is 'base' for the base §12.3 obligation (subject to cache-class
    exemption), and 'a7' for the Amendment 7-added obligation (no cache-class
    exemption when web-tier is derived via port zone).
    """
    scope = clause["applies_to"]
    if scope == "all":
        return True, "base"
    if scope == "not_infra":
        return not is_infra_tier(service_name, service, infra), "base"
    if scope == "web-tier":
        # §12.3 base rule: applies to web-tier services except cache-class.
        # Amendment 7 adds an obligation for the (cache-class, web-tier-by-port-zone) case.
        if not is_web_tier(service):
            return False, "base"
        if is_cache_class(service):
            if web_by_port_zone(service):
                # Amendment 7 obligation added — return with subject 'a7'.
                return True, "a7"
            return False, "base"
        return True, "base"
    return True, "base"


# ---------------------------------------------------------------------
# Exception-window suppression + temporal binding (§15.3)
# ---------------------------------------------------------------------

def _matching_windows(windows, clause_id: str, service_name: str,
                      eval_time: datetime):
    matched = []
    for w in windows:
        if w.clause_id != clause_id:
            continue
        if not fnmatch.fnmatchcase(service_name, w.service_glob):
            continue
        if not (w.starts_at <= eval_time < w.ends_at):
            continue
        matched.append(w)
    return matched


def _window_binds_a7(window: ExceptionWindow) -> bool:
    """§15.3 temporal binding: a window suspends an amendment's added
    obligation only if the window's approved_at is at or after the
    amendment's effective_date. Amendments dated before the window's
    approval extend automatically; amendments dated after do not."""
    return window.approved_at >= AMENDMENT_7_EFFECTIVE


def _is_non_waivable(clause_id: str) -> bool:
    return clause_id in NON_WAIVABLE_CLAUSES


# ---------------------------------------------------------------------
# Key approval
# ---------------------------------------------------------------------

def key_approves(evidence: TagEvidence, approved_keys) -> tuple[bool, str | None]:
    if not evidence.signature_valid or evidence.fingerprint is None:
        return False, SIGNATURE_INVALID_CODE
    if evidence.tag_created_at is None:
        return False, KEY_APPROVAL_CODE
    fp_norm = _norm_fp(evidence.fingerprint)
    row = None
    for k in approved_keys:
        if _norm_fp(k.fingerprint) == fp_norm:
            row = k
            break
    if row is None:
        return False, KEY_APPROVAL_CODE
    if row.approved_at > evidence.tag_created_at:
        return False, KEY_APPROVAL_CODE
    tag_time = evidence.tag_created_at
    if row.status == "active":
        return True, None
    if row.status == "rotated":
        if row.revoked_at is None:
            return True, None
        if tag_time < row.revoked_at:
            return True, None
        if tag_time < row.revoked_at + timedelta(hours=72):
            return True, None
        return False, KEY_APPROVAL_CODE
    if row.status == "compromised":
        if row.revoked_at is None:
            return True, None
        if tag_time < row.revoked_at:
            return True, None
        return False, KEY_APPROVAL_CODE
    return False, KEY_APPROVAL_CODE


def _norm_fp(fp: str) -> str:
    return "".join(fp.split()).upper()


# ---------------------------------------------------------------------
# Top-level evaluate
# ---------------------------------------------------------------------

def evaluate(*, repo: Repository, tag_evidence: TagEvidence,
             approved_keys, windows, infra, eval_time: datetime,
             standard_sha256: str) -> dict:
    reasons: list[DecisionReason] = []

    services = repo.resolved_services or {}
    if not services:
        reasons.append(DecisionReason(COMPOSE_MISSING_CODE,
                                       COMPOSE_MISSING_CLAUSE, ""))
        return _emit(reasons)

    for name in sorted(services.keys()):
        svc = services[name]
        for clause in CLAUSES:
            applies, subject = _clause_applies(clause, name, svc, infra)
            if not applies:
                continue
            pred = PREDICATES[clause["predicate"]]
            if pred(svc):
                continue
            cid = clause["id"]
            if _is_non_waivable(cid):
                reasons.append(DecisionReason(clause["code"], cid, name))
                continue
            # Exception-window suppression with §15.3 binding.
            windows_matched = _matching_windows(windows, cid, name, eval_time)
            if windows_matched:
                # Non-A7 clauses (or base subject on §12.3): any matching
                # window suppresses.
                if subject == "base":
                    continue
                # A7 subject: only windows with approved_at >= A7 effective
                # suspend the amendment's added obligation.
                if any(_window_binds_a7(w) for w in windows_matched):
                    continue
            reasons.append(DecisionReason(clause["code"], cid, name))

    hook_ok = True
    if repo.hooks_path != ".githooks":
        hook_ok = False
    if not repo.pre_push_executable:
        hook_ok = False
    if repo.pre_push_marker_sha is None:
        hook_ok = False
    elif _norm_hex(repo.pre_push_marker_sha) != _norm_hex(standard_sha256):
        hook_ok = False
    if not hook_ok:
        reasons.append(DecisionReason(HOOK_CODE, HOOK_CLAUSE, ""))

    ok, err = key_approves(tag_evidence, approved_keys)
    if not ok:
        reasons.append(DecisionReason(err or KEY_APPROVAL_CODE,
                                       KEY_APPROVAL_CLAUSE, ""))

    return _emit(reasons)


def _norm_hex(s: str) -> str:
    return "".join(s.split()).lower()


def _emit(reasons: list[DecisionReason]) -> dict:
    if not reasons:
        return {"decision": "approve", "reasons": []}
    reasons.sort(key=DecisionReason.sort_key)
    return {
        "decision": "deny",
        "reasons": [
            {"clauseId": r.clause_id, "code": r.code, "service": r.service}
            for r in reasons
        ],
    }


__all__ = [
    "ApprovedKey", "ExceptionWindow", "InfraRegistry", "TagEvidence",
    "Repository", "DecisionReason", "merge_compose", "evaluate",
    "is_web_tier", "is_cache_class", "is_infra_tier", "web_by_port_zone",
    "port_zone", "AMENDMENT_7_EFFECTIVE",
]
