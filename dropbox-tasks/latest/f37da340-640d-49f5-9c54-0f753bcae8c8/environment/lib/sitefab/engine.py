#!/usr/bin/env python3
"""Sitefab controller. Applies /etc/sitefab policy against topology + scripts."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import uuid
from pathlib import Path

from law_digest import law_digest_lines

TOPOLOGY = Path("/app/environment/topology")
SCENARIOS = Path("/app/environment/scenarios")
ETC = Path("/etc/sitefab")
REPORT = Path("/app/output/sitefab_report.json")
DEFAULT_JOURNAL = Path("/var/lib/sitefab/journal.json")
DEFER_REMOTE = 10000
DEFER_LINK = 5000
DEFER_PROP = 2500


def _read_ini(path: Path) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if path.exists():
        cfg.read(path)
    return cfg


def _parse_unit(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    section = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        data[f"{section}.{key.strip()}"] = val.strip()
    return data


def _load_template(name: str) -> dict[str, str]:
    if not name:
        return {}
    return _parse_unit(ETC / "templates" / f"{name}.mount")


def _load_arm_unit(arm: str, profile: str | None = None) -> dict[str, str]:
    candidates: list[Path] = []
    if profile:
        candidates.append(ETC / "units" / profile / f"{arm}.mount")
    candidates.append(ETC / "units" / f"{arm}.mount")
    merged: dict[str, str] = {}
    base_path = next((p for p in candidates if p.exists()), None)
    if base_path is None:
        drop_dir = ETC / "units" / f"{arm}.mount.d"
        if drop_dir.is_dir():
            for drop in sorted(drop_dir.glob("*.conf")):
                merged.update(_parse_unit(drop))
        return merged

    inherit = _parse_unit(base_path).get("Unit.X-Sitefab-Inherit", "").strip()
    if inherit:
        merged.update(_load_template(inherit))
    merged.update(_parse_unit(base_path))
    drop_dir = base_path.parent / f"{arm}.mount.d"
    if drop_dir.is_dir():
        for drop in sorted(drop_dir.glob("*.conf")):
            merged.update(_parse_unit(drop))
    return merged


def _split_options(opts: str) -> list[str]:
    return [p.strip() for p in opts.split(",") if p.strip()]


def _has_token(opts: str, token: str) -> bool:
    return token in _split_options(opts)


def _has_nf(opts: str) -> bool:
    parts = _split_options(opts)
    return "_nf" in parts or "nofail" in parts


def _reconcile(gen_opts: str, hand_opts: str, mode: str) -> str:
    if mode != "gen-hand-bs":
        return hand_opts or gen_opts
    bs = ",bs="
    gen_has = bs in gen_opts
    hand_has = bs in hand_opts
    if gen_has and not hand_has:
        suffix = gen_opts.split(bs, 1)[1]
        return f"{hand_opts}{bs}{suffix}"
    if hand_has and not gen_has:
        return hand_opts
    if gen_has and hand_has and gen_opts != hand_opts:
        suffix = gen_opts.split(bs, 1)[1]
        base = hand_opts.split(bs, 1)[0]
        return f"{base}{bs}{suffix}"
    return hand_opts or gen_opts


def _policy() -> configparser.ConfigParser:
    cfg = _read_ini(ETC / "sitefab.conf")
    drop = ETC / "policy.d"
    if drop.is_dir():
        for path in sorted(drop.glob("*.conf")):
            part = _read_ini(path)
            for section in part.sections():
                if not cfg.has_section(section):
                    cfg.add_section(section)
                for key, val in part.items(section):
                    cfg.set(section, key, val)
    return cfg


def _carry_keys(cfg: configparser.ConfigParser) -> set[str]:
    raw = cfg.get("Journal", "Carry", fallback="")
    return {p.strip() for p in raw.split(",") if p.strip()}


def _journal_path(cfg: configparser.ConfigParser) -> Path:
    return Path(cfg.get("Journal", "Path", fallback=str(DEFAULT_JOURNAL)))


def _load_journal(path: Path) -> dict:
    if not path.exists():
        return {
            "seq": 0,
            "epochs": {},
            "last_ro": {},
            "stale_ref": {},
            "pending_arms": {},
            "refresh_count": 0,
            "barrier_rev": 0,
            "violation": False,
            "latch": {},
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _save_journal(path: Path, doc: dict, carry: set[str]) -> None:
    out = {
        "seq": int(doc.get("seq", 0)),
        "refresh_count": int(doc.get("refresh_count", 0)),
        "barrier_rev": int(doc.get("barrier_rev", 0)),
        "violation": bool(doc.get("violation", False)),
        "epochs": {},
        "last_ro": {},
        "stale_ref": {},
        "pending_arms": {},
        "latch": {},
    }
    for key in ("epochs", "last_ro", "stale_ref", "pending_arms", "latch"):
        if key in carry:
            out[key] = doc.get(key, {})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_topology(name: str) -> dict:
    return json.loads((TOPOLOGY / f"{name}.json").read_text(encoding="utf-8"))


def _arm_where(arm: dict, profile: str) -> str:
    return arm.get("where") or f"/srv/arms/{profile}/{arm['name']}"


def _arm_what(arm: dict, profile: str) -> str:
    return arm.get("what") or f"/srv/backing/{profile}/{arm['name']}"


def _compile_entries(profile: dict, cfg: configparser.ConfigParser) -> list[dict]:
    pname = profile["name"]
    strict = cfg.get("Compile", "PreferUnit", fallback="") == "strict"
    seal_paths = cfg.get("Compile", "SealPaths", fallback="") == "yes"
    entries = []
    for arm in profile["arms"]:
        unit = _load_arm_unit(arm["name"], pname)
        if strict and not unit:
            continue
        if not unit:
            opts = arm["opts"]
            remote = bool(arm.get("remote"))
            hint = int(arm["order_hint"])
            link_after = ""
            prop = ""
        else:
            opts = unit.get("Mount.Options", arm["opts"])
            remote_raw = unit.get(
                "Mount.X-Sitefab-Remote",
                unit.get("Unit.X-Sitefab-Remote", "yes" if arm.get("remote") else "no"),
            )
            remote = str(remote_raw).lower() in {"1", "yes", "true", "on"}
            hint = int(
                unit.get(
                    "Mount.X-Sitefab-OrderHint",
                    unit.get("Unit.X-Sitefab-OrderHint", arm["order_hint"]),
                )
            )
            link_after = unit.get("Unit.X-Sitefab-LinkAfter", "").strip()
            prop = unit.get("Mount.X-Sitefab-Propagate", "").strip()

        order_key = hint
        if remote:
            order_key = hint if _has_nf(opts) else hint + DEFER_REMOTE
        if link_after:
            peer = _load_arm_unit(link_after, pname)
            peer_hint = int(
                peer.get(
                    "Mount.X-Sitefab-OrderHint",
                    next(
                        (
                            a["order_hint"]
                            for a in profile["arms"]
                            if a["name"] == link_after
                        ),
                        hint,
                    ),
                )
            )
            if hint <= peer_hint:
                order_key += DEFER_LINK
        if prop and prop not in {"shared", "slave", "private", "rshared", "rslave"}:
            order_key += DEFER_PROP

        if seal_paths and unit:
            want_what = _arm_what(arm, pname)
            want_where = _arm_where(arm, pname)
            if unit.get("Mount.What") != want_what or unit.get("Mount.Where") != want_where:
                order_key += DEFER_REMOTE

        entries.append({"arm": arm["name"], "opts": opts, "order_key": order_key})
    entries.sort(key=lambda e: (e["order_key"], e["arm"]))
    return entries


def re_split_deps(dep: str) -> list[str]:
    return [d.strip() for d in dep.replace(",", " ").split() if d.strip()]


def _unit_depends(arm_name: str, profile: dict) -> list[str]:
    pname = profile["name"]
    scoped = ETC / "units" / pname / f"{arm_name}.mount"
    shared = ETC / "units" / f"{arm_name}.mount"
    if scoped.exists() or shared.exists():
        unit = _load_arm_unit(arm_name, pname)
        return re_split_deps(unit.get("Unit.X-Sitefab-Depends", ""))
    for arm in profile["arms"]:
        if arm["name"] == arm_name:
            return list(arm.get("depends_on", []))
    return []


def _drop_pair(profile_name: str) -> tuple[str, str] | None:
    """Reconcile pending ONLY from live drop-ins. Topology pairs are inventory only."""
    for base in (
        ETC / "units" / profile_name / "data.mount.d",
        ETC / "units" / "data.mount.d",
    ):
        gen_drop = base / "10-generator.conf"
        hand_drop = base / "20-hand.conf"
        if gen_drop.exists() and hand_drop.exists():
            gen = _parse_unit(gen_drop).get("Mount.Options", "")
            hand = _parse_unit(hand_drop).get("Mount.Options", "")
            return gen, hand
    return None


def _stage_pending(profile: dict, cfg: configparser.ConfigParser) -> dict[str, str]:
    mode = cfg.get("Reconcile", "Mode", fallback="")
    require = cfg.get("Reconcile", "RequireDropIns", fallback="") == "yes"
    pending: dict[str, str] = {}
    pair = _drop_pair(profile["name"])
    if pair is None:
        if require:
            return pending
        for legacy in profile.get("units", []):
            rec = _reconcile(legacy.get("gen_opts", ""), legacy.get("hand_opts", ""), mode)
            pending["unit"] = rec
            for arm in profile["arms"]:
                if arm["name"] == "data":
                    pending[arm["name"]] = rec
            return pending
        return pending

    gen, hand = pair
    rec = _reconcile(gen, hand, mode)
    pending["unit"] = rec
    for arm in profile["arms"]:
        if arm["name"] == "data":
            pending[arm["name"]] = rec
    return pending


def _parse_script(path: Path) -> tuple[str, list[dict]]:
    profile = "alpha"
    steps: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "profile":
            profile = parts[1]
            continue
        if parts[0] != "step":
            continue
        phase = parts[1]
        fields: dict[str, str] = {"phase": phase}
        for token in parts[2:]:
            if "=" in token:
                k, v = token.split("=", 1)
                fields[k] = v
        steps.append(fields)
    return profile, steps


def _digest_lines(report: dict, store_arms: dict[str, str], refresh_count: int) -> list[str]:
    lines: list[str] = []
    for entry in report["entries"]:
        arm = entry["arm"]
        opts = store_arms.get(arm, entry["opts"])
        lines.append(f"entry:{arm}:{entry['order_key']}:{opts}")
    for cref in report["consumer_refs"]:
        lines.append(f"cref:{cref['arm']}:{cref['epoch']}")
    lines.append(f"refresh:{refresh_count}")
    lines.append(f"barrier:{report['barrier_rev']}")
    lines.append(f"run:{report['run_id']}")
    lines.append(f"seq:{report['journal_seq']}")
    lines.append(f"steps:{len(report['steps'])}")
    return sorted(lines)


def _store_digest(lines: list[str]) -> str:
    return law_digest_lines(lines)


def _health_digest(report: dict) -> str:
    parts = sorted(f"{e['arm']}:{e['order_key']}" for e in report["entries"])
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _depend_token_ok(arm_name: str, profile: dict, cfg: configparser.ConfigParser) -> bool:
    need = cfg.get("Visibility", "DependToken", fallback="").strip()
    if not need:
        return True
    unit = _load_arm_unit(arm_name, profile["name"])
    opts = unit.get("Mount.Options", "")
    return _has_token(opts, need)


def run(
    script_name: str,
    *,
    continue_run: bool = False,
    purge: bool = False,
) -> dict:
    cfg = _policy()
    jpath = _journal_path(cfg)
    carry = _carry_keys(cfg)

    if purge and jpath.exists():
        jpath.unlink()

    journal = _load_journal(jpath)
    if continue_run:
        journal_seq = int(journal.get("seq", 0)) + 1
    else:
        journal_seq = 0

    script_path = Path(script_name)
    if not script_path.is_absolute():
        script_path = SCENARIOS / script_name
    profile_name, events = _parse_script(script_path)
    profile = _load_topology(profile_name)

    entries = _compile_entries(profile, cfg)
    store_arms: dict[str, str] = {}
    pending = _stage_pending(profile, cfg)

    epochs: dict[str, int] = {}
    last_ro: dict[str, bool] = {}
    stale_ref: dict[str, bool] = {}
    latch: dict[str, str] = {}
    refresh_count = 0
    barrier_rev = int(journal.get("barrier_rev", 0))
    violation = bool(journal.get("violation", False))

    if continue_run:
        if "epochs" in carry:
            epochs = {k: int(v) for k, v in journal.get("epochs", {}).items()}
        if "last_ro" in carry:
            last_ro = {k: bool(v) for k, v in journal.get("last_ro", {}).items()}
        if "stale_ref" in carry:
            stale_ref = {k: bool(v) for k, v in journal.get("stale_ref", {}).items()}
        if "pending_arms" in carry:
            pending = dict(journal.get("pending_arms", {})) or pending
        if "latch" in carry:
            latch = {k: str(v) for k, v in journal.get("latch", {}).items()}
        refresh_count = int(journal.get("refresh_count", 0))

    step_recs: list[dict] = []
    refreshes: list[dict] = []
    tick = refresh_count
    hold_deps = cfg.get("Visibility", "DependentHold", fallback="") == "until-propagate"
    omit_stale = cfg.get("Visibility", "OmitStaleRefs", fallback="") == "yes"
    epoch_latch = cfg.get("Visibility", "EpochOnRwAfterRo", fallback="") == "yes"
    maint = cfg.get("Visibility", "MaintLatch", fallback="") == "yes"

    for evt in events:
        phase = evt["phase"]
        step_recs.append({"phase": phase, "target": evt.get("target", evt.get("to", ""))})
        if phase == "ro":
            target = evt["target"]
            last_ro[target] = True
            epochs.setdefault(target, 0)
        elif phase == "rw":
            target = evt["target"]
            was = last_ro.get(target, False)
            epochs.setdefault(target, 0)
            if epoch_latch and was:
                epochs[target] += 1
            last_ro[target] = False
            if hold_deps and was:
                for arm in profile["arms"]:
                    deps = _unit_depends(arm["name"], profile)
                    if target in deps and _depend_token_ok(arm["name"], profile, cfg):
                        stale_ref[arm["name"]] = True
        elif phase == "bmv":
            src = evt["from"]
            dst = evt["to"]
            epochs[src] = epochs.get(src, 0) + 1
            epochs[dst] = epochs.get(dst, 0) + 1
            if maint:
                latch[src] = "moved"
                latch[dst] = "landed"
        elif phase == "prp":
            target = evt["target"]
            tick += 1
            refresh_count = tick
            epochs[target] = epochs.get(target, 0) + 1
            stale_ref.pop(target, None)
            refreshes.append({"phase": "prp", "target": target, "tick": tick})
        elif phase == "pur":
            if jpath.exists():
                jpath.unlink()
            journal = _load_journal(jpath)
            epochs.clear()
            last_ro.clear()
            stale_ref.clear()
            latch.clear()
            pending = _stage_pending(profile, cfg)
            refresh_count = 0
            tick = 0
            barrier_rev = 0
            violation = False
            journal_seq = 0
        elif phase == "bar":
            if cfg.get("Barrier", "BumpRev", fallback="") == "yes":
                barrier_rev += 1
            if cfg.get("Barrier", "ClearStale", fallback="") == "yes":
                stale_ref.clear()
            if cfg.get("Barrier", "CommitPending", fallback="") == "yes":
                store_arms.update(pending)
                pending = {}
            if cfg.get("Barrier", "ClearLatch", fallback="") == "yes":
                latch.clear()
            violation = False
        elif phase == "rst":
            epochs.clear()
            last_ro.clear()
            if not maint:
                latch.clear()

    refs = []
    for arm, epoch in epochs.items():
        if omit_stale and stale_ref.get(arm, False):
            continue
        refs.append({"arm": arm, "epoch": epoch})
    refs.sort(key=lambda r: r["arm"])

    report = {
        "run_id": str(uuid.uuid4()),
        "steps": step_recs,
        "entries": entries,
        "refreshes": refreshes,
        "consumer_refs": refs,
        "journal_seq": journal_seq,
        "barrier_rev": barrier_rev,
        "violation": violation,
        "maintenance_latch": sorted(latch.keys()),
    }

    digest_source = cfg.get("Digest", "Source", fallback="health-cache")
    if digest_source == "durable-store":
        report["durable_digest"] = _store_digest(
            _digest_lines(report, store_arms, refresh_count)
        )
    else:
        report["durable_digest"] = _health_digest(report)

    persist_seq = journal_seq if continue_run else 1
    if any(e["phase"] == "pur" for e in events) and not continue_run:
        persist_seq = 1
    persist_doc = {
        "seq": persist_seq,
        "epochs": epochs,
        "last_ro": last_ro,
        "stale_ref": stale_ref,
        "pending_arms": pending,
        "latch": latch,
        "refresh_count": refresh_count,
        "barrier_rev": barrier_rev,
        "violation": violation,
    }
    _save_journal(jpath, persist_doc, carry)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(prog="sitefab")
    parser.add_argument("--script", required=True)
    parser.add_argument("--continue", dest="continue_run", action="store_true")
    parser.add_argument("--purge", action="store_true")
    args = parser.parse_args()
    run(args.script, continue_run=args.continue_run, purge=args.purge)


if __name__ == "__main__":
    main()
