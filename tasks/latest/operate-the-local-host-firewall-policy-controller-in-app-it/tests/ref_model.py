"""Independent reference model for policy reconciliation."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

FAILPOINTS = [
    "after-stage-sets",
    "after-stage-chains",
    "after-publish-references",
    "after-manifest-publish",
    "during-cleanup",
]


def parse_toml(text: str) -> dict:
    cfg: dict = {"priority": 0, "tenant": "", "sets": {}, "rules": {}}
    sec = None
    rule_name = None
    set_name = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            sec = line[1:-1]
            rule_name = None
            set_name = None
            if sec.startswith("rules."):
                rule_name = sec.split(".", 1)[1]
                cfg["rules"].setdefault(rule_name, {})
            elif sec.startswith("sets."):
                set_name = sec.split(".", 1)[1]
                cfg["sets"].setdefault(set_name, {})
            continue
        if "=" not in line:
            continue
        k, _, v = [x.strip() for x in line.partition("=")]
        if rule_name is not None:
            if v.startswith("["):
                cfg["rules"][rule_name][k] = re.findall(r'"([^"]*)"', v)
            elif v.startswith('"'):
                cfg["rules"][rule_name][k] = v.strip('"')
            elif v.isdigit():
                cfg["rules"][rule_name][k] = int(v)
            else:
                cfg["rules"][rule_name][k] = v
        elif set_name is not None:
            if v.startswith("["):
                cfg["sets"][set_name][k] = re.findall(r'"([^"]*)"', v)
            elif v.startswith('"'):
                cfg["sets"][set_name][k] = v.strip('"')
            else:
                cfg["sets"][set_name][k] = v
        elif sec is None:
            if v.startswith('"'):
                cfg[k] = v.strip('"')
            elif v.lstrip("-").isdigit():
                cfg[k] = int(v)
            else:
                cfg[k] = v
    return cfg


def blend_dropins(base: dict, dropin_dir: Path) -> tuple[dict, list[dict]]:
    intent = json.loads(json.dumps(base))
    sources = []
    files = []
    for path in dropin_dir.glob("*.toml"):
        doc = parse_toml(path.read_text())
        files.append((doc.get("priority", 0), str(path.resolve()), doc))
    files.sort(key=lambda x: (x[0], x[1]))
    for priority, normalized, doc in files:
        sources.append({"path": normalized, "priority": priority})
        for rule_id, rule in doc.get("rules", {}).items():
            intent.setdefault("rules", {})[rule_id] = rule
        for set_id, s in doc.get("sets", {}).items():
            intent.setdefault("sets", {})[set_id] = s
    return intent, sources


def apply_overrides(intent: dict, overrides: dict) -> dict:
    out = json.loads(json.dumps(intent))
    for rule_id, ov in overrides.get("rules", {}).items():
        if ov.get("tenant") or ov.get("ownership_scope"):
            raise ValueError("protected override")
        if "action" in ov and ov["action"]:
            out.setdefault("rules", {}).setdefault(rule_id, {})["action"] = ov["action"]
    return out


def canonical_digest(intent: dict) -> str:
    set_ids = sorted(intent.get("sets", {}).keys())
    parts = []
    for sid in set_ids:
        blob = json.dumps(intent["sets"][sid], sort_keys=True)
        parts.append(f"set:{sid}:{hashlib.new('sha256', blob.encode()).hexdigest()}")
    for rid in sorted(intent.get("rules", {}).keys()):
        blob = json.dumps(intent["rules"][rid], sort_keys=True)
        parts.append(f"rule:{rid}:{hashlib.new('sha256', blob.encode()).hexdigest()}")
    parts.sort()
    return hashlib.new("sha256", "|".join(parts).encode()).hexdigest()


def effective_winner(dropin_dir: Path) -> str:
    """Return winning allow-web action: lower priority numbers win."""
    action = (
        parse_toml((dropin_dir.parent / "base.toml").read_text())
        .get("rules", {})
        .get("allow-web", {})
        .get("action", "drop")
    )
    files = []
    for path in dropin_dir.glob("*.toml"):
        doc = parse_toml(path.read_text())
        files.append((doc.get("priority", 0), str(path.resolve()), doc))
    files.sort(key=lambda x: (-x[0], x[1]))
    for _, _, doc in files:
        if "allow-web" in doc.get("rules", {}):
            action = doc["rules"]["allow-web"]["action"]
    return action


def simulate_packet(intent: dict, packet: dict) -> str:
    rules = intent.get("rules", {})
    ordered = sorted(rules.items(), key=lambda kv: kv[1].get("ordered_index", 0))
    for _, rule in ordered:
        if rule.get("dst_port") and rule["dst_port"] != packet["dst_port"]:
            continue
        src_set = rule.get("src_set")
        if src_set:
            members = intent.get("sets", {}).get(src_set, {}).get("members", [])
            if packet["src"] not in members:
                continue
        return rule.get("action", "drop")
    return "drop"


def state_digest(path: Path) -> str:
    if not path.exists():
        return hashlib.sha256(b"").hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()
