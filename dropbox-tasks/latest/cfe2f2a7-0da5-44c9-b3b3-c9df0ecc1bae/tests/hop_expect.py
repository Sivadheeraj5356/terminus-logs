"""Independent v3 contract reference for hopledger (tests-only)."""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


KIND_RANK = {
    "checkpoint": 0,
    "policy_update": 1,
    "quarantine": 2,
    "clear_quarantine": 3,
    "link_close": 4,
    "hop": 5,
    "link_open": 6,
    "note": 7,
}


def canonical(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: canonical(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [canonical(x) for x in obj]
    return obj


def canonical_json(obj: Any) -> str:
    return json.dumps(canonical(obj), separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def kind_rank(kind: str) -> int:
    return KIND_RANK.get(kind, 99)


def bucket_index(ms: int) -> int:
    return min(ms // 50, 5)


def pattern_tier(pattern: str) -> int:
    if pattern == "*>*":
        return 4
    if pattern.startswith("*>"):
        return 3
    if pattern.endswith(">*"):
        return 2
    return 1


def match_pattern(pattern: str, link_id: str) -> bool:
    if ">" not in link_id:
        return False
    src, dst = link_id.split(">", 1)
    if pattern == "*>*":
        return True
    if pattern.endswith(">*"):
        return src == pattern[:-2]
    if pattern.startswith("*>"):
        return dst == pattern[2:]
    return link_id == pattern


def sla_for(doc: dict | None, link_id: str) -> int:
    if doc is None:
        return 0
    best_tier = 999
    best_idx = 999
    best: int | None = None
    for idx, rule in enumerate(doc.get("rules", [])):
        if not match_pattern(rule["pattern"], link_id):
            continue
        tier = pattern_tier(rule["pattern"])
        if tier < best_tier or (tier == best_tier and idx < best_idx):
            best_tier = tier
            best_idx = idx
            best = int(rule["sla_ms"])
    if best is not None:
        return best
    return int(doc.get("default_sla_ms", 0))


@dataclass
class RawLine:
    lane: str
    priority: int
    line_num: int
    raw: str
    raw_hash: str


@dataclass
class Record:
    raw: RawLine
    epoch: int
    seq: int
    kind: str
    source: str
    rev: int
    cancel: bool
    op_id: str
    link: str = ""
    ms: int = 0
    tag: str = ""
    policy: dict | None = None
    merge_index: int = 0


@dataclass
class LinkState:
    open: bool = False
    quarantined: bool = False
    hop_count: int = 0
    sum_ms: int = 0
    max_ms: int = 0
    alarm_breaches: int = 0
    sla_ms: int = 0
    buckets: list[int] = field(default_factory=lambda: [0, 0, 0, 0, 0, 0])
    last_epoch: int = 0
    last_seq: int = 0
    referenced: bool = False


@dataclass
class AuditEntry:
    decision: str
    epoch: int
    seq: int
    lane: str
    source: str
    op_id: str
    rev: int
    kind: str
    reason: str
    link: str

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "epoch": self.epoch,
            "seq": self.seq,
            "lane": self.lane,
            "source": self.source,
            "op_id": self.op_id,
            "rev": self.rev,
            "kind": self.kind,
            "reason": self.reason,
            "link": self.link,
        }


def identity_key(rec: Record) -> tuple[int, int, str, str]:
    return (rec.epoch, rec.seq, rec.source, rec.op_id)


def parse_event(raw: RawLine, default_source: str) -> Record:
    obj = json.loads(raw.raw)
    for req in ("seq", "epoch", "kind"):
        if req not in obj:
            raise ValueError(f"missing field {req}")
    epoch = int(obj["epoch"])
    seq = int(obj["seq"])
    kind = str(obj["kind"])
    if epoch < 0 or seq < 0:
        raise ValueError("negative epoch or seq")
    source = str(obj.get("source", default_source))
    rev = int(obj.get("rev", 0))
    cancel = bool(obj.get("cancel", False))
    op_id = str(obj.get("op_id", f"{epoch}:{seq}:{source}:{raw.lane}"))
    rec = Record(
        raw=raw,
        epoch=epoch,
        seq=seq,
        kind=kind,
        source=source,
        rev=rev,
        cancel=cancel,
        op_id=op_id,
    )
    if kind in {
        "link_open",
        "link_close",
        "hop",
        "quarantine",
        "clear_quarantine",
    }:
        if "link" not in obj:
            raise ValueError("missing link")
        rec.link = str(obj["link"])
    if kind == "hop":
        rec.ms = int(obj["ms"])
        if rec.ms < 0:
            raise ValueError("negative latency")
    if kind == "checkpoint":
        rec.tag = str(obj.get("tag", ""))
        if not rec.tag:
            raise ValueError("empty checkpoint tag")
    if kind == "policy_update":
        if "policy" not in obj or not isinstance(obj["policy"], dict):
            raise ValueError("invalid policy update")
        rec.policy = obj["policy"]
    if kind not in KIND_RANK:
        raise ValueError(f"unknown kind {kind}")
    return rec


def load_raw_lines(manifest: dict, base: Path) -> list[RawLine]:
    lines: list[RawLine] = []
    if manifest.get("lanes"):
        for lane in manifest["lanes"]:
            path = base / lane["path"]
            text = path.read_text()
            for i, line in enumerate(text.splitlines()):
                if not line.strip():
                    continue
                lines.append(
                    RawLine(
                        lane=lane["name"],
                        priority=int(lane["priority"]),
                        line_num=i,
                        raw=line,
                        raw_hash=sha256_hex(line),
                    )
                )
    else:
        path = base / manifest["journal"]
        text = path.read_text()
        for i, line in enumerate(text.splitlines()):
            if not line.strip():
                continue
            lines.append(
                RawLine(
                    lane="",
                    priority=0,
                    line_num=i,
                    raw=line,
                    raw_hash=sha256_hex(line),
                )
            )
    return lines


def merge_key(rec: Record) -> tuple:
    return (
        rec.epoch,
        rec.seq,
        kind_rank(rec.kind),
        rec.raw.priority,
        rec.raw.lane,
        rec.raw.line_num,
        rec.raw.raw_hash,
    )


def compute_raw_input_digest(raw_lines: list[RawLine]) -> str:
    payload = [
        {
            "lane": rl.lane,
            "priority": rl.priority,
            "line": rl.line_num,
            "raw": rl.raw,
        }
        for rl in raw_lines
    ]
    return sha256_hex(canonical_json(payload))


def select_winners(records: list[Record]) -> dict[tuple[int, int, str, str], Record]:
    winners: dict[tuple[int, int, str, str], Record] = {}
    for rec in records:
        key = identity_key(rec)
        cur = winners.get(key)
        if cur is None or rec.rev > cur.rev or (
            rec.rev == cur.rev and rec.merge_index > cur.merge_index
        ):
            winners[key] = rec
    return winners


def policy_lineage_digest(initial: dict | None, updates: list[dict]) -> str:
    items: list[Any] = []
    if initial is not None:
        items.append(initial)
    items.extend(updates)
    if not items:
        return ""
    return sha256_hex(canonical_json(items))


def load_manifest(path: Path) -> tuple[dict, Path]:
    manifest = json.loads(path.read_text())
    return manifest, path.parent


def replay(
    manifest: dict,
    base: Path,
) -> dict[str, Any]:
    raw_lines = load_raw_lines(manifest, base)
    raw_input_digest = compute_raw_input_digest(raw_lines)

    records: list[Record] = []
    for rl in raw_lines:
        default_source = rl.lane if rl.lane else "main"
        records.append(parse_event(rl, default_source))
    records.sort(key=merge_key)
    for idx, rec in enumerate(records):
        rec.merge_index = idx

    winners = select_winners(records)

    policy_path = None
    initial_policy: dict | None = None
    if manifest.get("policy"):
        policy_path = base / manifest["policy"]
        initial_policy = json.loads(policy_path.read_text())

    active_policy = initial_policy
    policy_updates: list[dict] = []
    policy_digest = sha256_hex(policy_path.read_bytes()) if policy_path else ""

    links: dict[str, LinkState] = {}
    audit: list[AuditEntry] = []
    counts = {
        "applied_events": 0,
        "cancelled_events": 0,
        "superseded_events": 0,
        "duplicate_raw_events": 0,
        "suppressed_hops": 0,
    }
    max_epoch = -1
    processed_keys: set[tuple[int, int, str, str]] = set()
    line_cursors: dict[str, int] = {}

    checkpoint_dir = base / manifest.get("checkpoint_dir", "checkpoints")

    def link_row(link_id: str) -> LinkState:
        if link_id not in links:
            links[link_id] = LinkState(sla_ms=sla_for(active_policy, link_id))
        return links[link_id]

    def touch(rec: Record, link_id: str) -> None:
        st = link_row(link_id)
        st.referenced = True
        st.last_epoch = rec.epoch
        st.last_seq = rec.seq
        st.sla_ms = sla_for(active_policy, link_id)

    def audit_add(rec: Record, decision: str, reason: str, link: str = "") -> None:
        audit.append(
            AuditEntry(
                decision=decision,
                epoch=rec.epoch,
                seq=rec.seq,
                lane=rec.raw.lane,
                source=rec.source,
                op_id=rec.op_id,
                rev=rec.rev,
                kind=rec.kind,
                reason=reason,
                link=link or rec.link,
            )
        )

    for rec in records:
        key = identity_key(rec)
        winner = winners[key]

        if rec is not winner:
            if rec.rev < winner.rev:
                audit_add(rec, "superseded", "lower_rev")
                counts["superseded_events"] += 1
            elif rec.raw.raw_hash == winner.raw.raw_hash:
                audit_add(rec, "duplicate_raw", "exact_raw_duplicate")
                counts["duplicate_raw_events"] += 1
            else:
                audit_add(rec, "superseded", "tie_break")
                counts["superseded_events"] += 1
            continue

        if rec.cancel:
            audit_add(rec, "cancelled", "tombstone")
            counts["cancelled_events"] += 1
            processed_keys.add(key)
            if rec.link:
                touch(rec, rec.link)
            max_epoch = max(max_epoch, rec.epoch)
            continue

        if rec.kind == "note":
            audit_add(rec, "note", "ignored")
            processed_keys.add(key)
            max_epoch = max(max_epoch, rec.epoch)
            continue

        if rec.kind == "policy_update":
            assert rec.policy is not None
            active_policy = rec.policy
            policy_updates.append(rec.policy)
            audit_add(rec, "policy_update", "applied")
            counts["applied_events"] += 1
            processed_keys.add(key)
            max_epoch = max(max_epoch, rec.epoch)
            continue

        if rec.kind == "checkpoint":
            audit_add(rec, "checkpoint", rec.tag)
            counts["applied_events"] += 1
            processed_keys.add(key)
            for r in records:
                if r.merge_index <= rec.merge_index:
                    prev = line_cursors.get(r.raw.lane, -1)
                    if r.raw.line_num > prev:
                        line_cursors[r.raw.lane] = r.raw.line_num
            snap = {
                "schema_version": 3,
                "epoch": rec.epoch,
                "next_seq": rec.seq + 1,
                "applied_events": counts["applied_events"],
                "audit_counts": {
                    "cancelled_events": counts["cancelled_events"],
                    "superseded_events": counts["superseded_events"],
                    "duplicate_raw_events": counts["duplicate_raw_events"],
                    "suppressed_hops": counts["suppressed_hops"],
                },
                "policy_state": active_policy,
                "policy_updates": list(policy_updates),
                "policy_lineage_digest": policy_lineage_digest(initial_policy, policy_updates),
                "links": {
                    lid: {
                        "open": st.open,
                        "quarantined": st.quarantined,
                        "hop_count": st.hop_count,
                        "sum_ms": st.sum_ms,
                        "max_ms": st.max_ms,
                        "alarm_breaches": st.alarm_breaches,
                        "sla_ms": st.sla_ms,
                        "buckets": st.buckets,
                        "last_epoch": st.last_epoch,
                        "last_seq": st.last_seq,
                    }
                    for lid, st in links.items()
                    if st.referenced
                },
                "winner_keys": [list(k) for k in processed_keys],
                "line_cursors": dict(line_cursors),
                "raw_input_digest": raw_input_digest,
            }
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            (checkpoint_dir / f"{rec.tag}.snap").write_text(
                json.dumps(snap, separators=(",", ":"), sort_keys=True) + "\n"
            )
            max_epoch = max(max_epoch, rec.epoch)
            continue

        if rec.link:
            touch(rec, rec.link)

        if rec.kind == "link_open":
            st = link_row(rec.link)
            st.open = True
            audit_add(rec, "applied", "open")
            counts["applied_events"] += 1
        elif rec.kind == "link_close":
            st = link_row(rec.link)
            if st.open:
                st.open = False
                audit_add(rec, "applied", "close")
                counts["applied_events"] += 1
            else:
                audit_add(rec, "noop", "noop_close")
        elif rec.kind == "quarantine":
            st = link_row(rec.link)
            st.quarantined = True
            audit_add(rec, "applied", "quarantine")
            counts["applied_events"] += 1
        elif rec.kind == "clear_quarantine":
            st = link_row(rec.link)
            if st.quarantined:
                st.quarantined = False
                audit_add(rec, "applied", "clear")
                counts["applied_events"] += 1
            else:
                audit_add(rec, "noop", "noop_clear_quarantine")
        elif rec.kind == "hop":
            st = link_row(rec.link)
            if not st.open:
                audit_add(rec, "suppressed", "closed")
                counts["suppressed_hops"] += 1
            elif st.quarantined:
                audit_add(rec, "suppressed", "quarantined")
                counts["suppressed_hops"] += 1
            else:
                ms = rec.ms
                st.hop_count += 1
                st.sum_ms += ms
                st.max_ms = max(st.max_ms, ms)
                if st.sla_ms > 0 and ms > st.sla_ms:
                    st.alarm_breaches += 1
                st.buckets[bucket_index(ms)] += 1
                audit_add(rec, "applied", "hop")
                counts["applied_events"] += 1

        processed_keys.add(key)
        max_epoch = max(max_epoch, rec.epoch)

    rows = []
    for link_id in sorted(links):
        st = links[link_id]
        if not st.referenced:
            continue
        rows.append(
            {
                "link_id": link_id,
                "open": st.open,
                "quarantined": st.quarantined,
                "hop_count": st.hop_count,
                "sum_ms": st.sum_ms,
                "max_ms": st.max_ms,
                "alarm_breaches": st.alarm_breaches,
                "sla_ms": st.sla_ms,
                "buckets": st.buckets,
                "last_epoch": st.last_epoch,
                "last_seq": st.last_seq,
            }
        )

    lineage = policy_lineage_digest(initial_policy, policy_updates)
    report = {
        "schema_version": 3,
        "epochs_seen": max(max_epoch + 1, 0),
        "applied_events": counts["applied_events"],
        "cancelled_events": counts["cancelled_events"],
        "superseded_events": counts["superseded_events"],
        "duplicate_raw_events": counts["duplicate_raw_events"],
        "suppressed_hops": counts["suppressed_hops"],
        "open_link_count": sum(1 for st in links.values() if st.referenced and st.open),
        "quarantined_count": sum(
            1 for st in links.values() if st.referenced and st.quarantined
        ),
        "alarm_breach_total": sum(st.alarm_breaches for st in links.values()),
        "policy_digest": policy_digest,
        "policy_lineage_digest": lineage,
        "raw_input_digest": raw_input_digest,
        "links": rows,
    }

    audit_objs = [a.to_dict() for a in audit]
    digest_payload = {
        "report": report,
        "raw_input_digest": raw_input_digest,
        "policy_lineage_digest": lineage,
        "audit": audit_objs,
    }
    digest = sha256_hex(canonical_json(digest_payload)) + "\n"
    audit_text = "".join(json.dumps(a, separators=(",", ":"), sort_keys=True) + "\n" for a in audit_objs)
    if audit_objs:
        audit_text += ""

    return {
        "report_obj": report,
        "digest": digest,
        "audit": audit_text,
    }


def load_checkpoint(base: Path, manifest: dict, tag: str) -> dict:
    path = base / manifest["checkpoint_dir"] / f"{tag}.snap"
    return json.loads(path.read_text())


def expect_run(manifest_path: str, resume_tag: str | None = None) -> dict[str, Any]:
    manifest, base = load_manifest(Path(manifest_path))
    if resume_tag:
        resume = load_checkpoint(base, manifest, resume_tag)
        raw_lines = load_raw_lines(manifest, base)
        if resume.get("raw_input_digest") and resume["raw_input_digest"] != compute_raw_input_digest(raw_lines):
            raise ValueError("raw input digest mismatch")
    return replay(manifest, base)


def generate_manifest(seed: int, tmp: Path) -> Path:
    import random

    rng = random.Random(seed)
    lanes_spec = [
        {"name": "alpha", "path": "lanes/alpha.ndjson", "priority": 1},
        {"name": "beta", "path": "lanes/beta.ndjson", "priority": 2},
    ]
    if seed % 2:
        lanes_spec.append({"name": "gamma", "path": "lanes/gamma.ndjson", "priority": 3})

    links = [f"n{i}>s{j}" for i in range(3) for j in range(2)]
    rng.shuffle(links)
    links = links[: rng.randint(3, 5)]

    policy = {
        "default_sla_ms": 120,
        "rules": [
            {"pattern": f"{links[0].split('>')[0]}>*", "sla_ms": 80},
            {"pattern": "*>omega", "sla_ms": 70},
        ],
    }
    (tmp / "policy.json").write_text(json.dumps(policy) + "\n")

    lane_lines: dict[str, list[str]] = {lane["name"]: [] for lane in lanes_spec}
    epoch = 0
    seq = 1
    ckpt_tag = f"ckpt-{seed}"

    def emit(lane: str, obj: dict) -> None:
        nonlocal seq
        obj.setdefault("epoch", epoch)
        obj.setdefault("seq", seq)
        obj.setdefault("source", lane)
        lane_lines[lane].append(json.dumps(obj, separators=(",", ":")))
        seq += 1

    primary = links[0]
    emit(lanes_spec[0]["name"], {"kind": "link_open", "link": primary})
    emit(lanes_spec[0]["name"], {"kind": "hop", "link": primary, "ms": 45})
    emit(
        lanes_spec[1]["name"],
        {
            "kind": "hop",
            "link": primary,
            "ms": 90,
            "rev": 0,
            "op_id": f"{epoch}:{2}:{lanes_spec[1]['name']}:dup",
        },
    )
    emit(
        lanes_spec[1]["name"],
        {
            "kind": "hop",
            "link": primary,
            "ms": 55,
            "rev": 1,
            "op_id": f"{epoch}:{2}:{lanes_spec[1]['name']}:dup",
        },
    )
    raw_dup = json.dumps(
        {"seq": seq, "epoch": epoch, "kind": "note", "source": lanes_spec[0]["name"]},
        separators=(",", ":"),
    )
    lane_lines[lanes_spec[0]["name"]].append(raw_dup)
    seq += 1
    lane_lines[lanes_spec[0]["name"]].append(raw_dup)

    emit(lanes_spec[0]["name"], {"kind": "quarantine", "link": primary})
    emit(lanes_spec[0]["name"], {"kind": "hop", "link": primary, "ms": 30})

    secondary = links[1]
    emit(lanes_spec[1]["name"], {"kind": "link_open", "link": secondary})
    emit(lanes_spec[1]["name"], {"kind": "link_close", "link": secondary})
    emit(lanes_spec[1]["name"], {"kind": "link_close", "link": secondary})

    emit(lanes_spec[0]["name"], {"kind": "checkpoint", "tag": ckpt_tag})

    epoch = 100 if seed % 3 == 0 else 20
    seq = 1
    emit(lanes_spec[0]["name"], {"kind": "policy_update", "policy": {"default_sla_ms": 40, "rules": []}})
    emit(lanes_spec[0]["name"], {"kind": "hop", "link": primary, "ms": 60})
    emit(
        lanes_spec[1]["name"],
        {"kind": "hop", "link": primary, "ms": 10, "cancel": True, "op_id": "cancel-me"},
    )

    omega = f"{links[0].split('>')[0]}>omega"
    emit(lanes_spec[-1]["name"] if len(lanes_spec) > 2 else lanes_spec[1]["name"], {"kind": "link_open", "link": omega})
    emit(
        (lanes_spec[-1]["name"] if len(lanes_spec) > 2 else lanes_spec[1]["name"]),
        {"kind": "hop", "link": omega, "ms": 75},
    )

    for lane in lanes_spec:
        path = tmp / lane["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lane_lines[lane["name"]]) + "\n")

    (tmp / "checkpoints").mkdir(exist_ok=True)
    manifest = {
        "schema_version": 3,
        "checkpoint_dir": "checkpoints",
        "policy": "policy.json",
        "lanes": [
            {"name": lane["name"], "path": lane["path"], "priority": lane["priority"]}
            for lane in lanes_spec
        ],
    }
    manifest_path = tmp / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest_path


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "--generate":
        seed = int(sys.argv[2])
        tmp = Path(sys.argv[3])
        tmp.mkdir(parents=True, exist_ok=True)
        path = generate_manifest(seed, tmp)
        print(json.dumps(expect_run(str(path))))
        return
    manifest = sys.argv[1]
    resume_tag = sys.argv[2] if len(sys.argv) > 2 else None
    print(json.dumps(expect_run(manifest, resume_tag)))


if __name__ == "__main__":
    main()
