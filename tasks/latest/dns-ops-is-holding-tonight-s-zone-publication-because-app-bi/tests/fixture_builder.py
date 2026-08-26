"""Deterministic DNS publication fixture builder and Python reference oracle."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

SUPPORTED_TYPES = {
    "SOA", "NS", "A", "AAAA", "CNAME", "MX", "TXT", "CAA", "DS", "DNSKEY", "RRSIG", "NSEC"
}
DNSSEC_SIDE = {"RRSIG", "NSEC"}
ACTIONS = {"add", "delete", "replace"}
FINDING_CODES = {
    "SERIAL_NOT_ADVANCED", "APEX_CNAME", "SOA_COUNT", "CNAME_CONFLICT",
    "DELEGATION_GLUE_MISSING", "WILDCARD_BELOW_DELEGATION", "FREEZE_WINDOW",
    "TXT_CANONICAL", "TTL_OUT_OF_RANGE", "UNKNOWN_DELETE",
}
MOD = 2**32
MAX_STEP = 2147483647
FREEZE_HEADER = ["freeze_id", "zone", "owner_suffix", "record_type", "start_utc", "end_utc", "reason"]
EXCEPTION_HEADER = [
    "exception_id", "zone", "owner_suffix", "record_type", "code", "start_utc", "end_utc", "reason"
]


class FatalInput(Exception):
    """Fatal contract/input error."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def normalize_name(name: str) -> str:
    return name.lower()


def absolute_name(name: str) -> bool:
    return isinstance(name, str) and name.endswith(".") and name != ""


def matches_suffix(name: str, suffix: str) -> bool:
    n = normalize_name(name)
    s = normalize_name(suffix)
    if n == s:
        return True
    return n.endswith("." + s)


def parse_utc(value: str, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise FatalInput(f"invalid timestamp for {label}")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError as exc:
        raise FatalInput(f"invalid timestamp for {label}") from exc


def serial_advanced(original: int, candidate: int) -> bool:
    o = original % MOD
    c = candidate % MOD
    if c == o:
        return False
    return ((c - o) % MOD) <= MAX_STEP and ((c - o) % MOD) != 0


def canonicalize_txt(rdata: str) -> str:
    out: list[str] = []
    i = 0
    pending_space = False
    started = False
    while i < len(rdata):
        ch = rdata[i]
        if ch == '"':
            if pending_space and started:
                out.append(" ")
            pending_space = False
            out.append('"')
            i += 1
            while i < len(rdata):
                c2 = rdata[i]
                if c2 == "\\" and i + 1 < len(rdata):
                    out.append(c2)
                    out.append(rdata[i + 1])
                    i += 2
                    continue
                out.append(c2)
                i += 1
                if c2 == '"':
                    break
            started = True
        elif ch.isspace():
            pending_space = True
            i += 1
        else:
            if pending_space and started:
                out.append(" ")
            pending_space = False
            out.append(ch)
            started = True
            i += 1
    return "".join(out)


@dataclass
class RR:
    owner: str
    ttl: int
    type: str
    rdata: str


@dataclass
class Change:
    change_id: str
    seq: int
    action: str
    zone: str
    owner: str
    ttl: int
    record_type: str
    rdata: str
    effective_utc: datetime
    correction_of: str
    reason: str


@dataclass
class Freeze:
    freeze_id: str
    zone: str
    owner_suffix: str
    record_type: str
    start_utc: datetime
    end_utc: datetime
    reason: str


@dataclass
class ExceptionRow:
    exception_id: str
    zone: str
    owner_suffix: str
    record_type: str
    code: str
    start_utc: datetime
    end_utc: datetime
    reason: str


@dataclass
class Finding:
    zone: str
    owner: str
    record_type: str
    code: str
    severity: str
    evidence: str
    exception_id: str | None = None
    reason: str | None = None


EVIDENCE = {
    "SERIAL_NOT_ADVANCED": "candidate SOA serial is not advanced",
    "APEX_CNAME": "CNAME present at zone apex",
    "SOA_COUNT": "apex SOA count is not exactly one",
    "CNAME_CONFLICT": "CNAME owner has conflicting non-DNSSEC records",
    "DELEGATION_GLUE_MISSING": "in-zone delegated nameserver lacks glue",
    "WILDCARD_BELOW_DELEGATION": "wildcard owner lies below a delegated zone cut",
    "FREEZE_WINDOW": "active change overlaps freeze window",
    "TXT_CANONICAL": "TXT rdata is not in canonical form",
    "TTL_OUT_OF_RANGE": "TTL outside allowed range 30..86400",
    "UNKNOWN_DELETE": "delete targets a record absent from the candidate",
}


def evidence_for(code: str, detail: str | None = None) -> str:
    msg = EVIDENCE.get(code, code)
    return f"{msg} {detail}" if detail else msg


def parse_zone_text(text: str) -> list[RR]:
    rows: list[RR] = []
    for idx, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        parts = stripped.split(None, 4)
        if len(parts) < 5:
            raise FatalInput(f"malformed zone RR on line {idx}")
        owner, ttl_s, klass, typ, rdata = parts
        if not absolute_name(owner):
            raise FatalInput("malformed owner name")
        try:
            ttl = int(ttl_s)
        except ValueError as exc:
            raise FatalInput("malformed TTL") from exc
        if not 30 <= ttl <= 86400:
            raise FatalInput("malformed TTL")
        if klass != "IN":
            raise FatalInput("class must be IN")
        typ_u = typ.upper()
        if typ_u not in SUPPORTED_TYPES:
            raise FatalInput(f"unknown record type {typ}")
        rows.append(RR(normalize_name(owner), ttl, typ_u, rdata.strip()))
    return rows


def resolve_journal(raw: list[Change]) -> list[Change]:
    best: dict[str, Change] = {}
    for r in raw:
        cur = best.get(r.change_id)
        if cur is None:
            best[r.change_id] = r
        elif r.seq > cur.seq:
            best[r.change_id] = r
        elif r.seq == cur.seq:
            raise FatalInput(f"duplicate change_id {r.change_id} with identical seq {r.seq}")

    correctors = sorted([r for r in best.values() if r.correction_of], key=lambda c: c.seq)
    for r in correctors:
        target = best.get(r.correction_of)
        if target is None:
            raise FatalInput(f"correction references unknown change_id {r.correction_of}")
        if r.seq <= target.seq:
            continue
        merged = deepcopy(r)
        merged.change_id = target.change_id
        merged.correction_of = ""
        best[target.change_id] = merged
        if r.change_id != target.change_id:
            best.pop(r.change_id, None)
    return sorted(best.values(), key=lambda c: c.change_id)


def parse_journal_text(text: str) -> list[Change]:
    rows: list[Change] = []
    for idx, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise FatalInput(f"malformed NDJSON journal record on line {idx}") from exc
        if not isinstance(obj, dict):
            raise FatalInput(f"malformed NDJSON journal record on line {idx}")
        required = [
            "change_id", "seq", "action", "zone", "owner", "ttl", "record_type",
            "rdata", "effective_utc", "correction_of", "reason",
        ]
        for key in required:
            if key not in obj:
                raise FatalInput(f"missing journal field {key}")
        action = str(obj["action"])
        if action not in ACTIONS:
            raise FatalInput(f"unknown action {action}")
        typ = str(obj["record_type"]).upper()
        if typ not in SUPPORTED_TYPES:
            raise FatalInput(f"unknown record type {obj['record_type']}")
        if not absolute_name(obj["zone"]) or not absolute_name(obj["owner"]):
            raise FatalInput("malformed owner name")
        try:
            ttl = int(obj["ttl"])
            seq = int(obj["seq"])
        except (TypeError, ValueError) as exc:
            raise FatalInput("malformed TTL") from exc
        if action != "delete" and not 30 <= ttl <= 86400:
            raise FatalInput("malformed TTL")
        if action == "delete" and ttl != 0 and not 30 <= ttl <= 86400:
            raise FatalInput("malformed TTL")
        rows.append(
            Change(
                change_id=str(obj["change_id"]),
                seq=seq,
                action=action,
                zone=normalize_name(obj["zone"]),
                owner=normalize_name(obj["owner"]),
                ttl=ttl,
                record_type=typ,
                rdata=str(obj["rdata"]),
                effective_utc=parse_utc(obj["effective_utc"], "journal"),
                correction_of=str(obj["correction_of"]),
                reason=str(obj["reason"]),
            )
        )
    return resolve_journal(rows)


def parse_freezes(text: str) -> list[Freeze]:
    table = csv.DictReader(StringIO(text))
    if table.fieldnames != FREEZE_HEADER:
        raise FatalInput("freeze CSV headers must be exact and ordered")
    rows: list[Freeze] = []
    for row in table:
        for h in FREEZE_HEADER:
            if row.get(h) is None:
                raise FatalInput(f"missing freeze field {h}")
        typ = row["record_type"].upper() if row["record_type"] != "*" else "*"
        if typ != "*" and typ not in SUPPORTED_TYPES:
            raise FatalInput(f"unknown record type {row['record_type']}")
        if not absolute_name(row["zone"]) or not absolute_name(row["owner_suffix"]):
            raise FatalInput("malformed owner name")
        rows.append(
            Freeze(
                freeze_id=row["freeze_id"],
                zone=normalize_name(row["zone"]),
                owner_suffix=normalize_name(row["owner_suffix"]),
                record_type=typ,
                start_utc=parse_utc(row["start_utc"], "freeze"),
                end_utc=parse_utc(row["end_utc"], "freeze"),
                reason=row["reason"],
            )
        )
    return rows


def parse_exceptions(text: str) -> list[ExceptionRow]:
    table = csv.DictReader(StringIO(text))
    if table.fieldnames != EXCEPTION_HEADER:
        raise FatalInput("exception CSV headers must be exact and ordered")
    rows: list[ExceptionRow] = []
    for row in table:
        for h in EXCEPTION_HEADER:
            if row.get(h) is None:
                raise FatalInput(f"missing exception field {h}")
        typ = row["record_type"].upper() if row["record_type"] != "*" else "*"
        if typ != "*" and typ not in SUPPORTED_TYPES:
            raise FatalInput(f"unknown record type {row['record_type']}")
        code = row["code"]
        if code not in FINDING_CODES:
            raise FatalInput(f"unknown finding code {code}")
        if not absolute_name(row["zone"]) or not absolute_name(row["owner_suffix"]):
            raise FatalInput("malformed owner name")
        rows.append(
            ExceptionRow(
                exception_id=row["exception_id"],
                zone=normalize_name(row["zone"]),
                owner_suffix=normalize_name(row["owner_suffix"]),
                record_type=typ,
                code=code,
                start_utc=parse_utc(row["start_utc"], "exception"),
                end_utc=parse_utc(row["end_utc"], "exception"),
                reason=row["reason"],
            )
        )
    return rows


def apply_changes(zone: list[RR], changes: list[Change]) -> tuple[list[RR], list[Finding]]:
    records = deepcopy(zone)
    findings: list[Finding] = []
    for ch in sorted(changes, key=lambda c: c.change_id):
        if ch.action == "add":
            records.append(RR(ch.owner, ch.ttl, ch.record_type, ch.rdata))
        elif ch.action == "delete":
            before = len(records)
            records = [
                rr for rr in records
                if not (rr.owner == ch.owner and rr.type == ch.record_type and rr.rdata == ch.rdata)
            ]
            if len(records) == before:
                findings.append(
                    Finding(ch.zone, ch.owner, ch.record_type, "UNKNOWN_DELETE", "blocking",
                            evidence_for("UNKNOWN_DELETE"))
                )
        elif ch.action == "replace":
            records = [rr for rr in records if not (rr.owner == ch.owner and rr.type == ch.record_type)]
            records.append(RR(ch.owner, ch.ttl, ch.record_type, ch.rdata))
    return records, findings


def delegation_owners(zone: str, records: list[RR]) -> list[str]:
    out = []
    for rr in records:
        if rr.type == "NS" and rr.owner != zone:
            out.append(rr.owner)
    return sorted(set(out))


def evaluate_policies(
    zone: str,
    original: list[RR],
    candidate: list[RR],
    changes: list[Change],
    freezes: list[Freeze],
) -> list[Finding]:
    findings: list[Finding] = []

    orig_soa = [rr for rr in original if rr.owner == zone and rr.type == "SOA"]
    cand_soa = [rr for rr in candidate if rr.owner == zone and rr.type == "SOA"]
    if len(cand_soa) != 1:
        findings.append(Finding(zone, zone, "SOA", "SOA_COUNT", "blocking", evidence_for("SOA_COUNT")))
    elif len(orig_soa) == 1:
        o_serial = int(orig_soa[0].rdata.split()[2])
        c_serial = int(cand_soa[0].rdata.split()[2])
        if not serial_advanced(o_serial, c_serial):
            findings.append(
                Finding(zone, zone, "SOA", "SERIAL_NOT_ADVANCED", "blocking", evidence_for("SERIAL_NOT_ADVANCED"))
            )

    by_owner: dict[str, list[RR]] = {}
    for rr in candidate:
        by_owner.setdefault(rr.owner, []).append(rr)
    for owner, rrs in by_owner.items():
        types = {rr.type for rr in rrs}
        if owner == zone and "CNAME" in types:
            findings.append(Finding(zone, owner, "CNAME", "APEX_CNAME", "blocking", evidence_for("APEX_CNAME")))
        if "CNAME" in types:
            others = types - {"CNAME"}
            if others - DNSSEC_SIDE:
                findings.append(
                    Finding(zone, owner, "CNAME", "CNAME_CONFLICT", "blocking", evidence_for("CNAME_CONFLICT"))
                )

    for owner, rrs in by_owner.items():
        if owner == zone:
            continue
        ns_rrs = [rr for rr in rrs if rr.type == "NS"]
        for ns in ns_rrs:
            ns_name = normalize_name(ns.rdata.split()[0])
            if not matches_suffix(ns_name, owner):
                continue
            has_glue = any(
                rr.owner == ns_name and rr.type in {"A", "AAAA"} for rr in candidate
            )
            if not has_glue:
                findings.append(
                    Finding(
                        zone, owner, "NS", "DELEGATION_GLUE_MISSING", "blocking",
                        evidence_for("DELEGATION_GLUE_MISSING", ns_name),
                    )
                )

    cuts = delegation_owners(zone, candidate)
    for rr in candidate:
        if not rr.owner.startswith("*."):
            continue
        if any(matches_suffix(rr.owner, cut) for cut in cuts):
            findings.append(
                Finding(zone, rr.owner, rr.type, "WILDCARD_BELOW_DELEGATION", "blocking",
                        evidence_for("WILDCARD_BELOW_DELEGATION"))
            )

    for rr in candidate:
        if not 30 <= rr.ttl <= 86400:
            findings.append(
                Finding(zone, rr.owner, rr.type, "TTL_OUT_OF_RANGE", "blocking", evidence_for("TTL_OUT_OF_RANGE"))
            )
        if rr.type == "TXT" and canonicalize_txt(rr.rdata) != rr.rdata:
            findings.append(
                Finding(zone, rr.owner, "TXT", "TXT_CANONICAL", "blocking", evidence_for("TXT_CANONICAL"))
            )

    for ch in changes:
        for fz in freezes:
            if fz.zone != ch.zone:
                continue
            if not matches_suffix(ch.owner, fz.owner_suffix):
                continue
            if fz.record_type != "*" and fz.record_type != ch.record_type:
                continue
            if not (fz.start_utc <= ch.effective_utc <= fz.end_utc):
                continue
            findings.append(
                Finding(
                    ch.zone, ch.owner, ch.record_type, "FREEZE_WINDOW", "blocking",
                    evidence_for("FREEZE_WINDOW", fz.freeze_id),
                )
            )
    # unique wildcard findings
    uniq: list[Finding] = []
    seen = set()
    for f in findings:
        key = (f.zone, f.owner, f.record_type, f.code, f.evidence)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)
    return uniq


def partition_exceptions(
    findings: list[Finding], exceptions: list[ExceptionRow], changes: list[Change]
) -> tuple[list[Finding], list[Finding]]:
    blocked: list[Finding] = []
    suppressed: list[Finding] = []

    def matching_effective(f: Finding) -> datetime | None:
        exact = [c for c in changes if c.owner == f.owner and c.record_type == f.record_type]
        if exact:
            return max(c.effective_utc for c in exact)
        if changes:
            return min(c.effective_utc for c in changes)
        return None

    for f in findings:
        eff = matching_effective(f)
        matched = None
        for ex in exceptions:
            if ex.zone != f.zone:
                continue
            if not matches_suffix(f.owner, ex.owner_suffix):
                continue
            if ex.record_type != "*" and ex.record_type != f.record_type:
                continue
            if ex.code != f.code:
                continue
            if eff is None or not (ex.start_utc <= eff <= ex.end_utc):
                continue
            matched = ex
            break
        if matched:
            suppressed.append(
                Finding(
                    f.zone, f.owner, f.record_type, f.code, f.severity, f.evidence,
                    exception_id=matched.exception_id, reason=matched.reason,
                )
            )
        else:
            blocked.append(f)
    return blocked, suppressed


def canonical_report(
    zone_path: Path,
    journal_path: Path,
    freezes_path: Path,
    exceptions_path: Path,
) -> dict[str, Any]:
    zone = parse_zone_text(zone_path.read_text())
    changes = parse_journal_text(journal_path.read_text())
    freezes = parse_freezes(freezes_path.read_text())
    exceptions = parse_exceptions(exceptions_path.read_text())
    if not changes:
        zone_name = next((rr.owner for rr in zone if rr.type == "SOA"), zone[0].owner if zone else "")
    else:
        zones = {c.zone for c in changes}
        if len(zones) != 1:
            raise FatalInput("active journal spans multiple zones")
        zone_name = next(iter(zones))
    candidate, find_apply = apply_changes(zone, changes)
    findings = find_apply + evaluate_policies(zone_name, zone, candidate, changes, freezes)
    blocked, suppressed = partition_exceptions(findings, exceptions, changes)
    blocked = sorted(blocked, key=lambda f: (f.zone, f.owner, f.record_type, f.code))
    suppressed = sorted(
        suppressed, key=lambda f: (f.zone, f.owner, f.record_type, f.code, f.exception_id or "")
    )
    soa = next((rr for rr in candidate if rr.type == "SOA" and rr.owner == zone_name), None)
    soa_serial = int(soa.rdata.split()[2]) if soa else 0
    return {
        "format_version": 1,
        "inputs": {
            "zone_sha256": sha256_file(zone_path),
            "journal_sha256": sha256_file(journal_path),
            "freezes_sha256": sha256_file(freezes_path),
            "exceptions_sha256": sha256_file(exceptions_path),
        },
        "summary": {
            "publishable": len(blocked) == 0,
            "findings": len(blocked),
            "suppressed": len(suppressed),
            "active_changes": len(changes),
        },
        "findings": [
            {
                "zone": f.zone,
                "owner": f.owner,
                "record_type": f.record_type,
                "code": f.code,
                "severity": f.severity,
                "evidence": f.evidence,
            }
            for f in blocked
        ],
        "suppressed": [
            {
                "zone": f.zone,
                "owner": f.owner,
                "record_type": f.record_type,
                "code": f.code,
                "exception_id": f.exception_id,
                "reason": f.reason,
                "evidence": f.evidence,
            }
            for f in suppressed
        ],
        "candidate": {
            "zone": zone_name,
            "soa_serial": soa_serial,
            "record_count": len(candidate),
            "delegation_count": len(delegation_owners(zone_name, candidate)),
        },
    }


def dump_canonical(obj: dict[str, Any]) -> str:
    text = json.dumps(obj, indent=2, ensure_ascii=False)
    # JSON dumps already uses [] for empty arrays
    if not text.endswith("\n"):
        text += "\n"
    return text


def soa_rdata(serial: int, mname: str = "ns1.example.com.", rname: str = "hostmaster.example.com.") -> str:
    return f"{mname} {rname} {serial} 7200 3600 1209600 3600"


def base_zone(zone: str = "example.com.", serial: int = 2026010100) -> str:
    return "\n".join(
        [
            f"; zone {zone}",
            f"{zone} 3600 IN SOA {soa_rdata(serial)}",
            f"{zone} 3600 IN NS ns1.{zone}",
            f"ns1.{zone} 3600 IN A 192.0.2.53",
            f"www.{zone} 300 IN A 192.0.2.10",
            "",
        ]
    )


def change_obj(
    change_id: str,
    seq: int,
    action: str,
    zone: str,
    owner: str,
    ttl: int,
    record_type: str,
    rdata: str,
    effective_utc: str,
    correction_of: str = "",
    reason: str = "n/a",
) -> dict[str, Any]:
    return {
        "change_id": change_id,
        "seq": seq,
        "action": action,
        "zone": zone,
        "owner": owner,
        "ttl": ttl,
        "record_type": record_type,
        "rdata": rdata,
        "effective_utc": effective_utc,
        "correction_of": correction_of,
        "reason": reason,
    }


def write_inputs(
    tmp: Path,
    zone_text: str,
    journal_rows: list[dict[str, Any]],
    freeze_rows: list[list[str]] | None = None,
    exception_rows: list[list[str]] | None = None,
    shuffle_journal: bool = False,
    seed: int = 0,
) -> dict[str, Path]:
    tmp.mkdir(parents=True, exist_ok=True)
    zone_path = tmp / "zone.txt"
    journal_path = tmp / "journal.ndjson"
    freezes_path = tmp / "freezes.csv"
    exceptions_path = tmp / "exceptions.csv"
    report_path = tmp / "report.json"
    zone_path.write_text(zone_text)
    rows = list(journal_rows)
    if shuffle_journal:
        rng = random.Random(seed)
        rng.shuffle(rows)
    journal_path.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
    fh = StringIO()
    w = csv.writer(fh)
    w.writerow(FREEZE_HEADER)
    for row in freeze_rows or []:
        w.writerow(row)
    freezes_path.write_text(fh.getvalue())
    eh = StringIO()
    w = csv.writer(eh)
    w.writerow(EXCEPTION_HEADER)
    for row in exception_rows or []:
        w.writerow(row)
    exceptions_path.write_text(eh.getvalue())
    return {
        "zone": zone_path,
        "journal": journal_path,
        "freezes": freezes_path,
        "exceptions": exceptions_path,
        "report": report_path,
    }


def make_publishable_bundle(tmp: Path) -> dict[str, Path]:
    zone = "example.com."
    return write_inputs(
        tmp,
        base_zone(zone, 100),
        [
            change_obj(
                "c1", 1, "replace", zone, zone, 3600, "SOA", soa_rdata(101),
                "2026-03-01T12:00:00Z", reason="bump"
            )
        ],
    )


def make_blocked_freeze_bundle(tmp: Path) -> dict[str, Path]:
    zone = "example.com."
    return write_inputs(
        tmp,
        base_zone(zone, 100),
        [
            change_obj(
                "c1", 1, "replace", zone, zone, 3600, "SOA", soa_rdata(101),
                "2026-03-01T12:00:00Z"
            ),
            change_obj(
                "c2", 1, "add", zone, f"api.{zone}", 300, "A", "192.0.2.80",
                "2026-03-01T12:00:00Z"
            ),
        ],
        freeze_rows=[
            ["FZ1", zone, f"api.{zone}", "A", "2026-03-01T00:00:00Z", "2026-03-02T00:00:00Z", "freeze api"],
        ],
    )


def make_large_journal_bundle(tmp: Path, lines: int = 10000) -> dict[str, Path]:
    zone = "ops.example."
    zone_text = "\n".join(
        [
            f"{zone} 3600 IN SOA {soa_rdata(50, f'ns1.{zone}', f'hostmaster.{zone}')}",
            f"{zone} 3600 IN NS ns1.{zone}",
            f"ns1.{zone} 3600 IN A 198.51.100.1",
            f"alias.{zone} 300 IN A 198.51.100.2",
            "",
        ]
    )
    rows: list[dict[str, Any]] = []
    # SOA wrap-ish normal bump
    rows.append(
        change_obj(
            "soa", 1, "replace", zone, zone, 3600, "SOA",
            soa_rdata(51, f"ns1.{zone}", f"hostmaster.{zone}"),
            "2026-06-01T00:00:00Z",
        )
    )
    # CNAME exclusive + TXT canonical target via corrections
    rows.append(
        change_obj(
            "cn", 1, "add", zone, f"cdn.{zone}", 300, "CNAME", f"alias.{zone}",
            "2026-06-01T00:00:00Z",
        )
    )
    # Same change_id: lower-seq MX beside CNAME is superseded by higher-seq noop elsewhere,
    # so the CNAME owner stays exclusive.
    rows.append(
        change_obj(
            "cn-side", 1, "add", zone, f"cdn.{zone}", 300, "MX", f"10 mail.{zone}",
            "2026-06-01T00:00:00Z",
        )
    )
    rows.append(
        change_obj(
            "cn-side", 9, "add", zone, f"pad-side.{zone}", 300, "A", "198.51.100.9",
            "2026-06-01T00:00:00Z", reason="supersede conflicting mx",
        )
    )
    rows.append(
        change_obj(
            "cn-nsec", 1, "add", zone, f"cdn.{zone}", 300, "NSEC", f"alias.{zone} A",
            "2026-06-01T00:00:00Z",
        )
    )
    rows.append(
        change_obj(
            "txt1", 1, "add", zone, f"txt.{zone}", 300, "TXT", '"hello"   "world"',
            "2026-06-01T00:00:00Z",
        )
    )
    rows.append(
        change_obj(
            "txt1", 3, "replace", zone, f"txt.{zone}", 300, "TXT", '"hello" "world"',
            "2026-06-01T00:00:00Z", reason="canonical"
        )
    )
    # filler lines / changes to reach scale
    for i in range(lines):
        rows.append(
            change_obj(
                f"pad-{i}", 1, "add", zone, f"h{i}.{zone}", 300, "A", f"203.0.113.{i % 200}",
                "2026-06-01T00:00:00Z", reason="pad"
            )
        )
        if i % 7 == 0:
            # lower seq duplicate superseded
            rows.append(
                change_obj(
                    f"pad-{i}", 0, "add", zone, f"h{i}.{zone}", 300, "A", "203.0.113.250",
                    "2026-06-01T00:00:00Z", reason="old"
                )
            )
    return write_inputs(tmp, zone_text, rows, shuffle_journal=True, seed=42)


def make_composite_serial_freeze_exception(tmp: Path) -> dict[str, Path]:
    zone = "wrap.example."
    zone_text = "\n".join(
        [
            f"{zone} 3600 IN SOA {soa_rdata(4294967295, f'ns1.{zone}', f'hostmaster.{zone}')}",
            f"{zone} 3600 IN NS ns1.{zone}",
            f"ns1.{zone} 3600 IN A 192.0.2.1",
            "",
        ]
    )
    rows = [
        change_obj(
            "soa", 1, "replace", zone, zone, 3600, "SOA",
            soa_rdata(1, f"ns1.{zone}", f"hostmaster.{zone}"),
            "2026-07-01T12:00:00Z",
        ),
        change_obj(
            "a1", 1, "add", zone, f"svc.{zone}", 300, "A", "192.0.2.9",
            "2026-07-01T12:00:00Z",
        ),
        change_obj(
            "a2", 1, "add", zone, f"other.{zone}", 300, "A", "192.0.2.8",
            "2026-07-01T12:00:00Z",
        ),
    ]
    freezes = [
        ["FZ1", zone, f"svc.{zone}", "A", "2026-07-01T00:00:00Z", "2026-07-02T00:00:00Z", "svc freeze"],
        ["FZ2", zone, f"nope.{zone}", "A", "2026-07-01T00:00:00Z", "2026-07-02T00:00:00Z", "unrelated"],
    ]
    exceptions = [
        ["EX1", zone, f"svc.{zone}", "A", "FREEZE_WINDOW", "2026-07-01T00:00:00Z", "2026-07-02T00:00:00Z", "approved"],
    ]
    return write_inputs(tmp, zone_text, rows, freezes, exceptions, shuffle_journal=True, seed=7)


def make_composite_delegation_wildcard(tmp: Path) -> dict[str, Path]:
    zone = "cut.example."
    zone_text = "\n".join(
        [
            f"{zone} 3600 IN SOA {soa_rdata(10, f'ns1.{zone}', f'hostmaster.{zone}')}",
            f"{zone} 3600 IN NS ns1.{zone}",
            f"ns1.{zone} 3600 IN A 192.0.2.1",
            "",
        ]
    )
    rows = [
        change_obj(
            "soa", 1, "replace", zone, zone, 3600, "SOA",
            soa_rdata(11, f"ns1.{zone}", f"hostmaster.{zone}"),
            "2026-05-01T00:00:00Z",
        ),
        # in-zone NS without glue
        change_obj(
            "del1", 1, "add", zone, f"child.{zone}", 3600, "NS", f"ns.child.{zone}",
            "2026-05-01T00:00:00Z",
        ),
        # out-of-zone NS needs no glue
        change_obj(
            "del2", 1, "add", zone, f"ext.{zone}", 3600, "NS", "ns.external.net.",
            "2026-05-01T00:00:00Z",
        ),
        # wildcard below delegation
        change_obj(
            "w1", 1, "add", zone, f"*.child.{zone}", 300, "A", "192.0.2.77",
            "2026-05-01T00:00:00Z",
        ),
    ]
    return write_inputs(tmp, zone_text, rows, shuffle_journal=True, seed=3)
