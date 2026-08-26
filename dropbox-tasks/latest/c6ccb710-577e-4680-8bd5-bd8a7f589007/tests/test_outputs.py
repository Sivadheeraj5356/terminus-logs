"""Behavioral tests for Keelmark Haskell Cabal keel-block packaging gate."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
from pathlib import Path
from typing import Any


def app_root() -> Path:
    return Path(os.environ.get("HARBOR_APP_ROOT", "/app"))


def app_path(path: str) -> Path:
    root = app_root()
    if path.startswith("/app/"):
        return root / path[len("/app/") :]
    return Path(path)


SCRIPT = app_path("/app/keelmark.sh")
BIN = app_path("/app/bin/keelmark")
PROJECT = app_path("/app/cabal.project")
PROJECT_LOCAL = app_path("/app/cabal.project.local")
CABAL = app_path("/app/packages/keelmark-app/keelmark.cabal")
CORE_CABAL = app_path("/app/packages/keelmark-core/keelmark-core.cabal")
REPORT_CABAL = app_path("/app/packages/keelmark-report/keelmark-report.cabal")
CORE_SETUP = app_path("/app/packages/keelmark-core/Setup.hs")
REPORT_SETUP = app_path("/app/packages/keelmark-report/Setup.hs")
APP_SETUP = app_path("/app/packages/keelmark-app/Setup.hs")
MAIN_HS = app_path("/app/packages/keelmark-app/app/Main.hs")
SCAN_HS = app_path("/app/packages/keelmark-core/src/Keelmark/Scan.hs")
CLASSIFY_HS = app_path("/app/packages/keelmark-core/src/Keelmark/Classify.hs")
EMIT_HS = app_path("/app/packages/keelmark-report/src/Keelmark/Emit.hs")
COMPAT_CLASSIFY = app_path(
    "/app/packages/keelmark-core/compat/Keelmark/Classify.hs"
)
COMPAT_SCAN = app_path("/app/packages/keelmark-core/compat/Keelmark/Scan.hs")
COMPAT_EMIT = app_path("/app/packages/keelmark-report/compat/Keelmark/Emit.hs")
LEDGER = app_path("/app/keelmark-ledger/normative-keelmark-pack-v1.json")
OUT = app_path("/app/output")
INV = OUT / "pack_inventory.json"
ALERTS = OUT / "tension_alerts.json"
DEFERRED = OUT / "deferred.json"
SUMMARY = OUT / "summary.json"
GATE_SEAL = OUT / "gate_seal.txt"
POLICY = app_path("/app/keelmark-policy")
SHARDS = app_path("/app/keelmark-shards")

INV_TOP = [
    "audit_token",
    "pack_revision",
    "contract_revision",
    "package_version",
    "blocks",
    "critical",
    "warn",
    "stable",
    "deferred",
]
BLOCK_KEYS = [
    "name",
    "zone",
    "cell_class",
    "steward",
    "sample_count",
    "max_kN",
    "eff_max_kN",
    "dominant_peer",
    "load_index",
    "classification",
    "last_tension_at",
    "package_rev",
    "contract_revision",
]
ALERT_KEYS = [
    "block",
    "severity",
    "max_kN",
    "eff_max_kN",
    "load_index",
    "sample_count",
    "zone",
    "steward",
    "cell_class",
    "audit_stamp",
    "contract_revision",
]
SUMMARY_KEYS = [
    "audit_token",
    "pack_revision",
    "contract_revision",
    "package_version",
    "candidate_count",
    "measured_count",
    "deferred_count",
    "event_lines_total",
    "usable_events_total",
    "window_dropped_total",
    "dedup_dropped_total",
    "retracted_total",
    "alert_count",
    "alerts_muted",
    "coverage_pct",
    "inventory_sig",
]


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _run() -> None:
    assert SCRIPT.is_file(), "missing /app/keelmark.sh"
    subprocess.run(["bash", str(SCRIPT)], check=True, cwd=str(app_root()))


def pad_tension_ts(raw: str) -> str:
    """Pad hour and second; leave minute unpadded."""
    if "T" not in raw:
        return raw
    date, rest = raw.split("T", 1)
    body = rest[:-1] if rest.endswith("Z") else rest
    suffix = "Z" if rest.endswith("Z") else ""
    parts = body.split(":")
    if len(parts) != 3:
        return raw
    h, m, s = parts
    if len(h) == 1:
        h = "0" + h
    if len(s) == 1:
        s = "0" + s
    return f"{date}T{h}:{m}:{s}{suffix}"


def parse_events(raw: str) -> tuple[list[dict[str, Any]], int]:
    """Retraction-aware single pass; returns (surviving events, retracted count)."""
    out: list[dict[str, Any]] = []
    retracted = 0
    for line in raw.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue
        try:
            obj = json.loads(trimmed)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if not all(k in obj for k in ("ts", "peer", "kind")):
            continue
        if not all(isinstance(obj[k], str) for k in ("ts", "peer", "kind")):
            continue
        kind = obj["kind"]
        if kind == "retract":
            keep = [e for e in out if not (e["ts"] == obj["ts"] and e["peer"] == obj["peer"])]
            retracted += len(out) - len(keep)
            out = keep
            continue
        if kind not in ("sample", "escalate"):
            continue
        # Type-strict: kN must be a JSON number.
        if "kN" not in obj:
            continue
        if isinstance(obj["kN"], bool) or not isinstance(obj["kN"], (int, float)):
            continue
        out.append(obj)
    return out, retracted


def read_shard_stream(name: str) -> str:
    base = SHARDS / name / "tension_events.jsonl"
    overlay = SHARDS / name / "tension_events.overlay.jsonl"
    raw = base.read_text(encoding="utf-8") if base.is_file() else ""
    if overlay.is_file():
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += overlay.read_text(encoding="utf-8")
    return raw


def fnv64_hex(data: bytes) -> str:
    h = 14695981039346656037
    for b in data:
        h = ((h ^ b) * 1099511628211) % (1 << 64)
    return f"{h:016x}"


def window_filter(events: list[dict[str, Any]], start: str, end: str) -> list[dict[str, Any]]:
    return [e for e in events if start <= e["ts"][:10] <= end]


def dedup_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[tuple, float] = {}
    for e in events:
        key = (e["ts"], e["peer"], e["kind"])
        best[key] = max(best.get(key, float("-inf")), float(e["kN"]))
    seen: set[tuple] = set()
    out = []
    for e in events:
        key = (e["ts"], e["peer"], e["kind"])
        if key in seen:
            continue
        seen.add(key)
        row = dict(e)
        row["kN"] = best[key]
        out.append(row)
    return out


def count_nonblank(raw: str) -> int:
    return sum(1 for ln in raw.splitlines() if ln.strip())


def dominant_peer(events: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for e in events:
        counts[e["peer"]] = counts.get(e["peer"], 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    return ranked[0][0]


def eff_tenths(max_kn: float, gain: float) -> int:
    """round_half_up_1dp(max_kN * gain) held as integer tenths."""
    return math.floor(max_kn * gain * 10 + 0.5)


def classify(eff_t: int, has_esc: bool, warn_kn: float, crit_kn: float) -> str:
    eff = eff_t / 10
    if eff >= crit_kn or has_esc:
        return "CRITICAL"
    if eff >= warn_kn:
        return "WARN"
    return "STABLE"


def load_index(eff_t: int, sample_count: int, rated: int) -> int:
    return (eff_t * 100 + sample_count * 7) // max(1, rated)


def coverage_cents(measured: int, candidates: int) -> int:
    if candidates == 0:
        return 0
    return math.floor(10000 * measured / candidates + 0.5)


def apply_amendments(contract: dict[str, Any], alert_mute: set[str]) -> None:
    """Ratified-only, supersession-voided, ascending-seq amendment application."""
    path = POLICY / "amendments.jsonl"
    rows = [
        json.loads(ln)
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    ratified = [r for r in rows if r["status"] == "ratified"]
    voided = {s for a in ratified for s in a.get("supersedes", []) if a["seq"] > s}
    for a in sorted(ratified, key=lambda r: r["seq"]):
        if a["seq"] in voided:
            continue
        target = a["target"]
        if target == "warn_kN":
            contract["warn_kN"] = a["value"]
        elif target == "critical_kN":
            contract["critical_kN"] = a["value"]
        elif target == "alert_mute_add":
            alert_mute.add(a["value"])
        elif target.startswith("class_gains."):
            contract["class_gains"][target.split(".", 1)[1]] = a["value"]


def expected_outputs() -> dict[str, Any]:
    contract = _load(POLICY / "pack-contract.json")
    edition = _load(POLICY / "edition-policy.json")
    roster = {b["name"]: b for b in _load(POLICY / "block-roster.json")["blocks"]}
    suppress_doc = _load(POLICY / "suppress-blocks.json")
    suppress = set(suppress_doc["names"])
    alert_mute = set(suppress_doc["alert_mute"])
    apply_amendments(contract, alert_mute)
    monitored = set(contract["monitored_blocks"])
    pins = edition["block_pins"]
    gains = contract["class_gains"]
    win_start = contract["audit_window"]["start"]
    win_end = contract["audit_window"]["end"]
    candidates = sorted(n for n in roster if n in monitored and n in pins)
    abi_ok = edition["edition_abi"] == contract["required_edition_abi"]

    deferred: list[dict[str, str]] = []
    premeasured: list[dict[str, Any]] = []
    event_lines_total = 0

    for name in candidates:
        rb = roster[name]
        pin = pins[name]
        raw = read_shard_stream(name)
        event_lines_total += count_nonblank(raw)
        parsed, retracted = parse_events(raw)
        windowed = window_filter(parsed, win_start, win_end)
        deduped = dedup_events(windowed)

        if name in suppress:
            deferred.append({"name": name, "reason": "suppress_hit"})
            continue
        if not abi_ok:
            deferred.append({"name": name, "reason": "abi_miss"})
            continue
        if pin != rb["package_rev"]:
            deferred.append({"name": name, "reason": "pin_mismatch"})
            continue
        if not deduped:
            deferred.append({"name": name, "reason": "empty_shard"})
            continue

        max_kn = max(float(e["kN"]) for e in deduped)
        last = max(deduped, key=lambda e: e["ts"])
        premeasured.append(
            {
                "name": name,
                "rb": rb,
                "samples": len(deduped),
                "max_kN": max_kn,
                "base_t": eff_tenths(max_kn, gains[rb["cell_class"]]),
                "peer": dominant_peer(deduped),
                "raw_ts": last["ts"],
                "escalates": any(e["kind"] == "escalate" for e in deduped),
                "win_drop": len(parsed) - len(windowed),
                "dup_drop": len(windowed) - len(deduped),
                "retracted": retracted,
            }
        )

    # Brace-cycle quarantine on the graph restricted to surviving vertices.
    vertices = {pm["name"] for pm in premeasured}
    edges = {
        pm["name"]: [p for p in pm["rb"].get("braces", []) if p in vertices]
        for pm in premeasured
    }

    def on_cycle(start: str) -> bool:
        frontier = list(edges[start])
        seen: set[str] = set()
        while frontier:
            node = frontier.pop()
            if node == start:
                return True
            if node in seen:
                continue
            seen.add(node)
            frontier.extend(edges.get(node, []))
        return False

    cycle_names = {n for n in vertices if on_cycle(n)}
    deferred.extend({"name": n, "reason": "brace_cycle"} for n in sorted(cycle_names))
    survivors = [pm for pm in premeasured if pm["name"] not in cycle_names]
    usable_events_total = sum(pm["samples"] for pm in survivors)
    window_dropped_total = sum(pm["win_drop"] for pm in survivors)
    dedup_dropped_total = sum(pm["dup_drop"] for pm in survivors)
    retracted_total = sum(pm["retracted"] for pm in survivors)

    zone_overrides = contract.get("zone_overrides", {})

    # Single-pass directional brace uplift on pre-uplift base tenths.
    base_map = {pm["name"]: pm["base_t"] for pm in survivors}
    blocks: list[dict[str, Any]] = []
    for pm in survivors:
        rb = pm["rb"]
        uplift = sum(base_map[p] // 50 for p in rb.get("braces", []) if p in base_map)
        final_t = pm["base_t"] + uplift
        eff_warn = float(
            zone_overrides.get(rb["zone"], {}).get("warn_kN", contract["warn_kN"])
        )
        klass = classify(
            final_t, pm["escalates"], eff_warn, float(contract["critical_kN"])
        )
        idx = load_index(final_t, pm["samples"], int(rb["rated_tonnage"]))
        blocks.append(
            {
                "name": pm["name"],
                "zone": rb["zone"],
                "cell_class": rb["cell_class"],
                "steward": rb["steward"],
                "sample_count": pm["samples"],
                "max_kN": pm["max_kN"],
                "eff_max_kN": final_t / 10,
                "dominant_peer": pm["peer"],
                "load_index": idx,
                "classification": klass,
                "last_tension_at": pad_tension_ts(pm["raw_ts"]),
                "_raw_ts": pm["raw_ts"],
                "package_rev": rb["package_rev"],
                "contract_revision": contract["contract_revision"],
            }
        )

    deferred.sort(key=lambda r: r["name"])

    def class_rank(c: str) -> int:
        return {"CRITICAL": 0, "WARN": 1, "STABLE": 2}[c]

    blocks.sort(
        key=lambda b: (
            class_rank(b["classification"]),
            b["_raw_ts"],
            b["load_index"],
            [-ord(c) for c in b["name"]],
        )
    )

    qualifying = [
        b
        for b in blocks
        if b["classification"] in ("CRITICAL", "WARN")
        and b["load_index"] >= int(contract["min_alert_index"])
    ]
    alerts_muted = sum(1 for b in qualifying if b["name"] in alert_mute)
    alerts = [
        {
            "block": b["name"],
            "severity": b["classification"],
            "max_kN": b["max_kN"],
            "eff_max_kN": b["eff_max_kN"],
            "load_index": b["load_index"],
            "sample_count": b["sample_count"],
            "zone": b["zone"],
            "steward": b["steward"],
            "cell_class": b["cell_class"],
            "audit_stamp": contract["audit_stamp"],
            "contract_revision": contract["contract_revision"],
        }
        for b in qualifying
        if b["name"] not in alert_mute
    ]
    alerts.sort(key=lambda a: (0 if a["severity"] == "CRITICAL" else 1, a["block"]))

    critical = sorted(b["name"] for b in blocks if b["classification"] == "CRITICAL")
    warn = sorted(b["name"] for b in blocks if b["classification"] == "WARN")
    stable = sorted(b["name"] for b in blocks if b["classification"] == "STABLE")

    inventory = {
        "audit_token": edition["audit_token"],
        "pack_revision": edition["version"],
        "contract_revision": contract["contract_revision"],
        "package_version": edition["package_version"],
        "blocks": [{k: b[k] for k in BLOCK_KEYS} for b in blocks],
        "critical": critical,
        "warn": warn,
        "stable": stable,
        "deferred": [d["name"] for d in deferred],
    }
    summary = {
        "audit_token": edition["audit_token"],
        "pack_revision": edition["version"],
        "contract_revision": contract["contract_revision"],
        "package_version": edition["package_version"],
        "candidate_count": len(blocks) + len(deferred),
        "measured_count": len(blocks),
        "deferred_count": len(deferred),
        "event_lines_total": event_lines_total,
        "usable_events_total": usable_events_total,
        "window_dropped_total": window_dropped_total,
        "dedup_dropped_total": dedup_dropped_total,
        "retracted_total": retracted_total,
        "alert_count": len(alerts),
        "alerts_muted": alerts_muted,
        "coverage_pct": coverage_cents(len(blocks), len(blocks) + len(deferred)) / 100,
        "inventory_sig": fnv64_hex(INV.read_bytes()),
    }
    return {
        "inventory": inventory,
        "alerts": {"alerts": alerts},
        "deferred": {"deferred": deferred},
        "summary": summary,
    }


def _object_key_order(path: Path, expected_keys: list[str]) -> None:
    raw = path.read_text(encoding="utf-8")
    keys = re.findall(r'^\s{2}"([^"]+)":', raw, flags=re.M)
    assert keys[: len(expected_keys)] == expected_keys


def test_keelmark_script_rebuilds_cabal_console_binary():
    """keelmark.sh must rebuild /app/bin/keelmark from the Cabal package sources."""
    if BIN.exists():
        BIN.unlink()
    _run()
    assert BIN.is_file(), "expected packaged console binary at /app/bin/keelmark"
    assert os.access(BIN, os.X_OK)


def test_cabal_package_metadata_matches_edition_pin():
    """The executable package must be named keelmark, versioned to the edition pin, and layer on the internal libraries."""
    _run()
    edition = _load(POLICY / "edition-policy.json")
    text = CABAL.read_text(encoding="utf-8")
    assert re.search(r"(?m)^name:\s+keelmark\s*$", text)
    assert re.search(
        rf"(?m)^version:\s+{re.escape(edition['package_version'])}\s*$", text
    )
    assert re.search(r"(?m)^executable\s+keelmark\s*$", text)
    assert "keelmark-core" in text
    assert "keelmark-report" in text
    assert "aeson" in text


def test_core_library_exposes_all_shipped_modules():
    """keelmark-core must expose Types, Scan and Classify so dependent packages can import them."""
    _run()
    text = CORE_CABAL.read_text(encoding="utf-8")
    assert re.search(r"(?mi)^\s*library\s*$", text)
    for module in ("Keelmark.Types", "Keelmark.Scan", "Keelmark.Classify"):
        assert module in text, f"{module} missing from keelmark-core exposed-modules"


def test_report_library_depends_on_core():
    """keelmark-report emits reports over core types, so it must build-depend on keelmark-core."""
    _run()
    text = REPORT_CABAL.read_text(encoding="utf-8")
    assert "Keelmark.Emit" in text
    assert "keelmark-core" in text


def test_no_core_to_report_dependency_cycle():
    """keelmark-core must not depend on keelmark-report; that inverts the layering into a build cycle."""
    _run()
    text = CORE_CABAL.read_text(encoding="utf-8")
    assert "keelmark-report" not in text, "keelmark-core must not depend on keelmark-report"


def test_core_declares_containers_and_offline_satisfiable_aeson_bound():
    """core parses with Data.Map (containers) and must admit the offline-installed aeson 2.0 line."""
    _run()
    text = CORE_CABAL.read_text(encoding="utf-8")
    assert "containers" in text, "keelmark-core must declare containers"
    m = re.search(r"aeson([^,\n]*)", text)
    assert m, "aeson dependency missing from keelmark-core"
    assert not re.search(r">=?\s*2\.[1-9]", m.group(1)), "aeson lower bound excludes the installed 2.0 line"


def test_executable_build_type_configures_offline():
    """A Custom build-type without a Setup.hs cannot configure offline; require Simple or a shipped Setup.hs."""
    _run()
    text = CABAL.read_text(encoding="utf-8")
    bt = re.search(r"(?mi)^build-type:\s*(\S+)", text)
    assert bt, "executable package must declare a build-type"
    if bt.group(1).lower() == "custom":
        assert APP_SETUP.is_file(), "Custom build-type requires a Setup.hs"
    else:
        assert bt.group(1).lower() == "simple"


def test_cabal_project_lists_three_packages_without_unsatisfiable_pin():
    """The workspace project must include all three packages and carry no offline-unsatisfiable constraint."""
    _run()
    text = PROJECT.read_text(encoding="utf-8")
    for pkg in ("keelmark-core", "keelmark-report", "keelmark-app"):
        assert pkg in text, f"cabal.project must list {pkg}"
    assert not re.search(r"text\s*==\s*1\.3", text), "cabal.project pins text to an offline-unavailable version"


def test_internal_package_versions_align_with_edition_pin():
    """keelmark-core and keelmark-report versions must equal edition-policy.package_version."""
    _run()
    edition = _load(POLICY / "edition-policy.json")
    pin = edition["package_version"]
    for path in (CORE_CABAL, REPORT_CABAL, CABAL):
        text = path.read_text(encoding="utf-8")
        assert re.search(rf"(?m)^version:\s+{re.escape(pin)}\s*$", text), (
            f"{path.name} version must equal edition package_version {pin}"
        )


def test_gate_v2_stream_profile_compiled_into_both_libraries():
    """Both internal libraries must declare cpp-options -DKEELMARK_GATE_V2 per packaging_build."""
    _run()
    ledger = _load(LEDGER)
    define = ledger["packaging_build"]["stream_profile_cpp_define"]
    for path in (CORE_CABAL, REPORT_CABAL):
        text = path.read_text(encoding="utf-8")
        assert re.search(rf"cpp-options:.*-D{re.escape(define)}", text), (
            f"{path.name} must compile with -D{define}"
        )


def test_compat_trees_excluded_from_hs_source_dirs():
    """Shipped libraries must not list compat in hs-source-dirs."""
    _run()
    for path in (CORE_CABAL, REPORT_CABAL):
        text = path.read_text(encoding="utf-8")
        m = re.search(r"(?mi)^\s*hs-source-dirs:\s*(.+)$", text)
        assert m, f"{path.name} missing hs-source-dirs"
        dirs = m.group(1).strip()
        assert "compat" not in dirs.split(), (
            f"{path.name} hs-source-dirs must not include compat (got {dirs!r})"
        )


def test_project_local_does_not_undefine_gate_profile():
    """cabal.project.local must not strip KEELMARK_GATE_V2 via -U."""
    _run()
    ledger = _load(LEDGER)
    define = ledger["packaging_build"]["stream_profile_cpp_define"]
    blobs = [PROJECT.read_text(encoding="utf-8")]
    if PROJECT_LOCAL.is_file():
        blobs.append(PROJECT_LOCAL.read_text(encoding="utf-8"))
    joined = "\n".join(blobs)
    assert not re.search(rf"-U{re.escape(define)}", joined), (
        f"workspace must not pass -U{define} (project-local tide pin must be cleared)"
    )


def test_classify_and_emit_restored_under_src_not_compat_copy():
    """Maintained Scan, Classify, and Emit must live under src and diverge from tide-era compat."""
    _run()
    assert SCAN_HS.is_file(), "missing packages/keelmark-core/src/Keelmark/Scan.hs"
    assert CLASSIFY_HS.is_file(), "missing packages/keelmark-core/src/Keelmark/Classify.hs"
    assert EMIT_HS.is_file(), "missing packages/keelmark-report/src/Keelmark/Emit.hs"
    scan = SCAN_HS.read_text(encoding="utf-8")
    classify = CLASSIFY_HS.read_text(encoding="utf-8")
    emit = EMIT_HS.read_text(encoding="utf-8")
    # Half-up tenths, not Haskell banker's round.
    assert "floor" in classify and "0.5" in classify
    assert re.search(r">=\s*critKn|>=\s*warnKn", classify), "thresholds must be inclusive >="
    # Must not be a byte-identical copy of the retired compat modules.
    assert scan != COMPAT_SCAN.read_text(encoding="utf-8")
    assert classify != COMPAT_CLASSIFY.read_text(encoding="utf-8")
    assert emit != COMPAT_EMIT.read_text(encoding="utf-8")


def test_main_invokes_scan_symbols_directly():
    """Main.hs must call parseTensionEvents and peerEscalates from the scan module."""
    _run()
    main_txt = MAIN_HS.read_text(encoding="utf-8")
    scan_txt = SCAN_HS.read_text(encoding="utf-8")
    assert "parseTensionEvents" in scan_txt
    assert "peerEscalates" in scan_txt
    assert "parseTensionEvents" in main_txt
    assert "peerEscalates" in main_txt


def test_edition_abi_aligned_with_pack_contract():
    """edition_abi must be repaired to required_edition_abi with no abi_miss deferrals."""
    _run()
    edition = _load(POLICY / "edition-policy.json")
    contract = _load(POLICY / "pack-contract.json")
    assert edition["edition_abi"] == contract["required_edition_abi"]
    deferred = {d["name"]: d["reason"] for d in _load(DEFERRED)["deferred"]}
    assert "abi_miss" not in deferred.values()


def test_pack_revision_uses_edition_version_not_decoy():
    """pack_revision must come from edition-policy version, never the decoy pack_revision field."""
    _run()
    edition = _load(POLICY / "edition-policy.json")
    inv = _load(INV)
    summary = _load(SUMMARY)
    assert inv["pack_revision"] == edition["version"]
    assert summary["pack_revision"] == edition["version"]
    assert inv["pack_revision"] != edition["pack_revision"]


def test_candidate_intersection_ignores_orphan_and_roster_only():
    """Names outside monitored∩roster∩pins must not appear in inventory or deferred."""
    _run()
    inv = _load(INV)
    deferred = {d["name"] for d in _load(DEFERRED)["deferred"]}
    names = {b["name"] for b in inv["blocks"]} | deferred
    assert "orphan-only" not in names
    assert "uniform-roster-only" not in names
    assert "tango-unmonitored" not in names


def test_suppress_hit_and_pin_mismatch_and_empty_shard_reasons():
    """Skip precedence records suppress_hit, pin_mismatch, and empty_shard with exact codes."""
    _run()
    deferred = {d["name"]: d["reason"] for d in _load(DEFERRED)["deferred"]}
    assert deferred["echo-suppress"] == "suppress_hit"
    assert deferred["sierra-abi-bait"] == "suppress_hit"
    assert deferred["golf-mismatch"] == "pin_mismatch"
    assert deferred["hotel-empty"] == "empty_shard"
    assert deferred["lima-noise"] == "empty_shard"
    assert deferred["romeo-ghost"] == "empty_shard"


def test_inventory_matches_reference_measurement_math():
    """Measured rows must match reference pipeline, calibration, and padding exactly."""
    _run()
    exp = expected_outputs()["inventory"]
    got = _load(INV)
    assert got["audit_token"] == exp["audit_token"]
    assert got["contract_revision"] == exp["contract_revision"]
    assert got["package_version"] == exp["package_version"]
    assert [b["name"] for b in got["blocks"]] == [b["name"] for b in exp["blocks"]]
    for g, e in zip(got["blocks"], exp["blocks"]):
        assert g == e
    assert got["critical"] == exp["critical"]
    assert got["warn"] == exp["warn"]
    assert got["stable"] == exp["stable"]
    assert got["deferred"] == exp["deferred"]


def test_alpha_gain_uplift_crosses_critical_threshold():
    """Primary-class gain lifts alpha-keel's raw 580.0 to 614.8, forcing CRITICAL."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    row = by_name["alpha-keel"]
    assert row["max_kN"] == 580.0
    assert row["eff_max_kN"] == 614.8
    assert row["classification"] == "CRITICAL"


def test_foxtrot_half_up_tenths_not_bankers_round():
    """foxtrot-half raw 61.25 at gain 1.0 must half-up to 61.3 (banker's round yields 61.2)."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    row = by_name["foxtrot-half"]
    assert row["max_kN"] == 61.25
    assert row["eff_max_kN"] == 61.3
    assert row["classification"] == "STABLE"


def test_charlie_calibration_derates_then_brace_uplift_holds_warn():
    """charlie-crit derates from raw 625.5 to base 588.0, then delta-esc's brace adds 3.3 for 591.3 WARN."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    row = by_name["charlie-crit"]
    assert row["max_kN"] == 625.5
    assert row["eff_max_kN"] == 591.3
    assert row["classification"] == "WARN"


def test_papa_edge_gain_and_bravo_brace_lift_into_warn():
    """papa-edge calibrates 385.0 to 408.1 and gains 9.6 from bravo's brace (romeo contributes nothing)."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    row = by_name["papa-edge"]
    assert row["max_kN"] == 385.0
    assert row["eff_max_kN"] == 417.7
    assert row["classification"] == "WARN"


def test_victor_brace_uplift_flips_stable_into_warn():
    """victor-thresh base 395.0 is STABLE alone; alpha-keel's brace pushes it to 407.2 WARN."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    row = by_name["victor-thresh"]
    assert row["max_kN"] == 395.0
    assert row["eff_max_kN"] == 407.2
    assert row["classification"] == "WARN"


def test_bravo_out_of_window_event_excluded():
    """bravo-warn's 700 kN event predates the audit window and must not drive classification."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    row = by_name["bravo-warn"]
    assert row["max_kN"] == 455.0
    assert row["sample_count"] == 3
    assert row["classification"] == "WARN"


def test_quebec_window_boundaries_inclusive():
    """quebec-bound keeps its start-date and end-date events but drops the 900 kN post-window event."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    row = by_name["quebec-bound"]
    assert row["sample_count"] == 2
    assert row["max_kN"] == 210.0
    assert row["classification"] == "STABLE"
    assert _load(SUMMARY)["window_dropped_total"] == 2


def test_tango_string_kn_line_is_malformed_but_extra_fields_pass():
    """A string-typed kN line is malformed and skipped while unknown extra fields stay usable."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    row = by_name["tango-strict"]
    assert row["sample_count"] == 1
    assert row["max_kN"] == 401.5


def test_ratified_warn_amendment_holds_tango_stable():
    """Ascending-seq application lands warn_kN at 402.0, so tango's 401.5 stays STABLE with no alert."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    row = by_name["tango-strict"]
    assert row["eff_max_kN"] == 401.5
    assert row["classification"] == "STABLE"
    alert_blocks = {a["block"] for a in _load(ALERTS)["alerts"]}
    assert "tango-strict" not in alert_blocks


def test_draft_revoked_and_superseded_amendments_apply_nothing():
    """Draft warn, revoked critical, superseded spare/trial rows must all be ignored."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    # revoked critical_kN 550 would flip charlie (591.3) to CRITICAL
    assert by_name["charlie-crit"]["classification"] == "WARN"
    # superseded spare gain 1.2 loses to seq 11's 1.15
    assert by_name["quebec-bound"]["eff_max_kN"] == 241.5
    assert by_name["india-pad"]["eff_max_kN"] == 356.5
    # superseded trial gain 1.05 never applies
    assert by_name["victor-thresh"]["eff_max_kN"] == 407.2


def test_amendment_extends_alert_mute_to_victor():
    """The ratified alert_mute_add row silences victor-thresh while keeping it measured WARN."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    assert by_name["victor-thresh"]["classification"] == "WARN"
    alert_blocks = {a["block"] for a in _load(ALERTS)["alerts"]}
    assert "victor-thresh" not in alert_blocks
    assert _load(SUMMARY)["alerts_muted"] == 2


def test_oscar_zone_override_outranks_amended_global_warn():
    """basin-g's 415.0 warn override derates oscar-alert (413.6) to STABLE despite the amended global 402."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    row = by_name["oscar-alert"]
    assert row["eff_max_kN"] == 413.6
    assert row["classification"] == "STABLE"
    alert_blocks = {a["block"] for a in _load(ALERTS)["alerts"]}
    assert "oscar-alert" not in alert_blocks
    # papa-edge shares basin-g and clears the override
    assert by_name["papa-edge"]["classification"] == "WARN"


def test_brace_cycle_members_defer_including_self_brace():
    """whiskey/xray's two-cycle and yankee's self-brace quarantine all three with reason brace_cycle."""
    _run()
    deferred = {d["name"]: d["reason"] for d in _load(DEFERRED)["deferred"]}
    assert deferred["whiskey-loop"] == "brace_cycle"
    assert deferred["xray-loop"] == "brace_cycle"
    assert deferred["yankee-self"] == "brace_cycle"
    measured = {b["name"] for b in _load(INV)["blocks"]}
    assert not {"whiskey-loop", "xray-loop", "yankee-self"} & measured


def test_zulu_chain_uplift_skips_quarantined_partner():
    """zulu-chain's uplift takes quebec's brace only; cycle-deferred whiskey contributes nothing."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    row = by_name["zulu-chain"]
    assert row["eff_max_kN"] == 407.3
    assert row["classification"] == "WARN"
    alert_blocks = {a["block"] for a in _load(ALERTS)["alerts"]}
    assert "zulu-chain" in alert_blocks


def test_quarantined_blocks_excluded_from_pipeline_counters():
    """whiskey-loop's out-of-window event must not count once the block is brace_cycle deferred."""
    _run()
    summary = _load(SUMMARY)
    assert summary["window_dropped_total"] == 2
    # 29 prior usable events plus foxtrot-half's single in-window sample.
    assert summary["usable_events_total"] == 30


def test_november_overlay_retract_strikes_critical_event():
    """The overlay retract removes november's 650 kN event, leaving 380.0 STABLE from one sample."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    row = by_name["november-retract"]
    assert row["sample_count"] == 1
    assert row["max_kN"] == 380.0
    assert row["classification"] == "STABLE"
    alert_blocks = {a["block"] for a in _load(ALERTS)["alerts"]}
    assert "november-retract" not in alert_blocks


def test_romeo_overlay_appends_event_and_unmatched_retract_noops():
    """Overlay sample events join the stream while a retract matching nothing changes nothing."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    row = by_name["romeo-overlay"]
    assert row["sample_count"] == 2
    assert row["max_kN"] == 240.0
    assert row["eff_max_kN"] == 276.0
    assert row["classification"] == "STABLE"


def test_uniform_retract_precedes_window_filter_and_dedup_spans_files():
    """uniform's retracted 05-15 event never hits window_dropped_total; the post-retract duplicate still dedups."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    row = by_name["uniform-overlay"]
    assert row["sample_count"] == 1
    assert row["max_kN"] == 460.0
    assert row["eff_max_kN"] == 432.4
    assert row["classification"] == "WARN"
    alert_blocks = {a["block"] for a in _load(ALERTS)["alerts"]}
    assert "uniform-overlay" in alert_blocks
    assert _load(SUMMARY)["window_dropped_total"] == 2


def test_retracted_total_counts_removed_events_only():
    """retracted_total sums struck events (november 1 + uniform 1); no-op retracts add nothing."""
    _run()
    assert _load(SUMMARY)["retracted_total"] == 2


def test_oscar_duplicate_telemetry_deduped_keeping_max():
    """oscar-alert's identical (ts, peer, kind) rows collapse to one keeping kN 440."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    row = by_name["oscar-alert"]
    assert row["sample_count"] == 2
    assert row["max_kN"] == 440.0
    assert _load(SUMMARY)["dedup_dropped_total"] == 2


def test_bravo_alert_muted_but_still_measured():
    """alert_mute drops bravo-warn from tension_alerts yet keeps its inventory row."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    assert "bravo-warn" in by_name
    alert_blocks = {a["block"] for a in _load(ALERTS)["alerts"]}
    assert "bravo-warn" not in alert_blocks
    assert _load(SUMMARY)["alerts_muted"] == 2


def test_delta_escalate_forces_critical_below_critical_kn():
    """An escalate event forces CRITICAL even when calibrated tension is far below critical_kN."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    row = by_name["delta-esc"]
    assert row["classification"] == "CRITICAL"
    assert row["eff_max_kN"] < 600.0


def test_india_pad_timestamp_pads_hour_and_second_only():
    """Unpadded minute must remain unpadded while hour and second gain leading zeros."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    assert by_name["india-pad"]["last_tension_at"] == "2025-06-01T09:5:03Z"


def test_mike_peer_tie_breaks_lexicographically_greatest():
    """Equal peer counts select the Z-A greatest peer name."""
    _run()
    by_name = {b["name"]: b for b in _load(INV)["blocks"]}
    assert by_name["mike-peers"]["dominant_peer"] == "zeta-peer"


def test_juliet_kilo_sort_tie_breaks_name_descending():
    """Identical class/ts/load_index rows sort by name Z-A (kilo before juliet)."""
    _run()
    names = [b["name"] for b in _load(INV)["blocks"]]
    assert names.index("kilo-sort") < names.index("juliet-sort")


def test_tension_alerts_match_reference_and_audit_stamp_source():
    """Alerts cover unmuted WARN/CRITICAL rows meeting min_alert_index with contract audit_stamp."""
    _run()
    exp = expected_outputs()["alerts"]
    got = _load(ALERTS)
    assert got == exp
    contract = _load(POLICY / "pack-contract.json")
    for row in got["alerts"]:
        assert row["audit_stamp"] == contract["audit_stamp"]


def test_summary_counters_match_reference_totals():
    """Summary counters must equal reference pipeline totals including window/dedup/mute."""
    _run()
    assert _load(SUMMARY) == expected_outputs()["summary"]


def test_coverage_pct_bare_number_two_decimal_half_up_emission():
    """coverage_pct emits as a bare JSON number (never a quoted string) with round-half-up hundredths."""
    _run()
    raw = SUMMARY.read_text(encoding="utf-8")
    m = re.search(r'"coverage_pct": (\d+\.\d+)', raw)
    assert m, "coverage_pct must be an unquoted JSON number with two decimals"
    assert re.fullmatch(r"\d+\.\d{2}", m.group(1)), "coverage_pct must carry exactly two decimals"
    summary = _load(SUMMARY)
    assert isinstance(summary["coverage_pct"], float), "coverage_pct must be a JSON number, not a string"
    expected = coverage_cents(summary["measured_count"], summary["candidate_count"]) / 100
    assert summary["coverage_pct"] == expected


def test_inventory_sig_is_fnv1a64_of_inventory_bytes():
    """summary.inventory_sig is the FNV-1a 64-bit hex of the exact pack_inventory.json bytes."""
    _run()
    summary = _load(SUMMARY)
    sig = summary["inventory_sig"]
    assert re.fullmatch(r"[0-9a-f]{16}", sig), "inventory_sig must be 16 lowercase hex chars"
    assert sig == fnv64_hex(INV.read_bytes())


def test_gate_seal_chains_bundle_sig_with_double_newline():
    """gate_seal.txt chains the four-deliverable bundle hash into the seal line ending in exactly two newlines."""
    _run()
    raw = GATE_SEAL.read_bytes()
    assert raw.endswith(b"\n\n") and not raw.endswith(b"\n\n\n")
    line = raw.decode("utf-8").rstrip("\n")
    summary = _load(SUMMARY)
    bundle_sig = fnv64_hex(
        INV.read_bytes() + ALERTS.read_bytes() + DEFERRED.read_bytes() + SUMMARY.read_bytes()
    )
    expected = "|".join(
        [
            "KEELMARK-GATE",
            summary["pack_revision"],
            summary["inventory_sig"],
            bundle_sig,
            str(summary["alert_count"]),
            str(summary["alerts_muted"]),
        ]
    )
    assert line == expected


def test_trailing_newline_polarity_per_deliverable():
    """Inventory and deferred omit trailing newline; alerts and summary include exactly one."""
    _run()
    assert not INV.read_bytes().endswith(b"\n")
    assert not DEFERRED.read_bytes().endswith(b"\n")
    assert ALERTS.read_bytes().endswith(b"\n") and not ALERTS.read_bytes().endswith(b"\n\n")
    assert SUMMARY.read_bytes().endswith(b"\n") and not SUMMARY.read_bytes().endswith(b"\n\n")


def test_top_level_key_orders_match_normative_ledger():
    """Deliverable top-level key appearance order must match the normative pack ledger."""
    _run()
    _object_key_order(INV, INV_TOP)
    _object_key_order(ALERTS, ["alerts"])
    _object_key_order(DEFERRED, ["deferred"])
    _object_key_order(SUMMARY, SUMMARY_KEYS)


def test_block_and_alert_row_key_orders():
    """Each block and alert object must emit keys in the normative row order."""
    _run()
    inv_raw = INV.read_text(encoding="utf-8")
    block_match = re.search(r'"blocks":\s*\[\s*\{(.*?)\n    \}', inv_raw, flags=re.S)
    assert block_match
    block_keys = re.findall(
        r'"(name|zone|cell_class|steward|sample_count|max_kN|eff_max_kN|dominant_peer|load_index|classification|last_tension_at|package_rev|contract_revision)":',
        block_match.group(1),
    )
    assert block_keys == BLOCK_KEYS

    alerts_raw = ALERTS.read_text(encoding="utf-8")
    alert_match = re.search(r'"alerts":\s*\[\s*\{(.*?)\n    \}', alerts_raw, flags=re.S)
    assert alert_match
    alert_keys = re.findall(
        r'"(block|severity|max_kN|eff_max_kN|load_index|sample_count|zone|steward|cell_class|audit_stamp|contract_revision)":',
        alert_match.group(1),
    )
    assert alert_keys == ALERT_KEYS


def test_second_run_is_idempotent_after_rebuild():
    """Re-running keelmark.sh rebuilds and reproduces identical packaging deliverables."""
    _run()
    first = {
        "inv": INV.read_bytes(),
        "alerts": ALERTS.read_bytes(),
        "deferred": DEFERRED.read_bytes(),
        "summary": SUMMARY.read_bytes(),
        "seal": GATE_SEAL.read_bytes(),
    }
    _run()
    assert INV.read_bytes() == first["inv"]
    assert ALERTS.read_bytes() == first["alerts"]
    assert DEFERRED.read_bytes() == first["deferred"]
    assert SUMMARY.read_bytes() == first["summary"]
    assert GATE_SEAL.read_bytes() == first["seal"]
