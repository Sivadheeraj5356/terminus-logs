"""Verifier for the cross-compiler artifact equivalence checker task."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import yaml

SCHEMA = Path("/app/contracts/OUTPUT_SCHEMA.md")
REPORT = Path("/app/output/equivalence_report.json")
_ART_BASE = Path(os.environ.get("EQUIV_VERIFIER_ARTIFACT_DIR", "/tmp/equiv-verifier-artifacts"))
REPORT_FIRST = _ART_BASE / "report_first.json"
REPORT_SECOND = _ART_BASE / "report_second.json"
REPORT_SWAP = _ART_BASE / "report_swap.json"
REPORT_SWAP_SECOND = _ART_BASE / "report_swap_second.json"
REPORT_PROBE = _ART_BASE / "report_probe.json"
REPORT_MIXED = _ART_BASE / "report_mixed_stress.json"
REPORT_HARD_WORKER_STRESS = _ART_BASE / "report_hard_worker_stress.json"
REPORT_HARD_DUAL_REF = _ART_BASE / "report_hard_dual_ref.json"
REPORT_HARD_ROLLBACK_STRESS = _ART_BASE / "report_hard_rollback_stress.json"
REPORT_HARD_NONDET_CHECKPOINT = _ART_BASE / "report_hard_nondet_checkpoint.json"
REPORT_HARD_FULL_STRESS_INVALID = _ART_BASE / "report_hard_full_stress_invalid.json"
BIN = Path("/app/bin/artifact-equivalence-checker")
MAIN_GO = Path("/app/toolchain-cli/main.go")
EVALUATE_GO = Path("/app/equivalence-engine/evaluate.go")
SESSION_DIR = Path("/app/build-sessions")
RULES = Path("/app/policy/equivalence_rules.yaml")
STUB_NOT_IMPLEMENTED = "engine.EvaluateSession not implemented"

BUNDLED_DATA_CHECKSUMS: dict[str, str] = {
    "build_01.json": "5dc89bc34727d75c939798af526803ad3f8517cce747407f87c1c06db5a9b300",
    "build_02.json": "a400f8722b9e004647292e46eee405214561ae829a2f0a37d14acbe0412bbe9b",
    "build_03.json": "d5d48f1f98fc653a65442b97bdec213fd544557b09b6dc7d3f32c7824d1e0ef0",
    "build_04.json": "871c755c311064e6c831b00226216859c8046567cd030e4a38c77e54e2a2e874",
    "build_05.json": "feafc4761852b947402cd834551c9cf5f390183ddf58bd791e244b9f376e3f0b",
    "build_06.json": "da7f657ae8a6a8d0480dc187434cb6b3ea4c5afe274199a679c89512b921a704",
    "build_07.json": "364980583d45590ef0187b23e2c3af2431dcda004797927cf1ccdf86687ad517",
    "build_08.json": "236fc7e29599f93c34e90e160f3ba39d6a5681d1afb03c6f2f5097f9464cca11",
    "build_09.json": "026b9226e16de505f168b1d1fc4d192af7b78b7649466d6150d7d7fd99f8ede5",
    "build_10.json": "9e45df279a665b8370321e3f5cd556f6e7d95c210eb7218bf12eae00aacb5fe2",
    "build_11.json": "7c267735ddb30d88738b108d925327fdf354adc9d49a541f92391abdea354dd0",
    "build_12.json": "d9820528fceaf23e7be346d77d0debd3f9798d892b7b90fdb6946b80d7869c1b",
    "build_13.json": "db043648c4abd9be74a0c8c28337f602eb0b6a20065f0751d2e5fcd1af07f0e9",
    "build_14.json": "71194fd7fa004710e24d9d35e95609bdbd39414648e3710aab9b7f17a8cef1ca",
    "build_15.json": "70cbcada783c407567b66975bd2b81b4f7fa3319e848174043f009ab6f80f141",
    "build_16.json": "4a7ad1f30a0caadadb03056f700e5cc628270e2565fe6228b811209689684c30",
    "build_17.json": "f7af48787d6f7d0840b8981c63013fd5ca82a18283686d9cce8a4ee0abefc1d5",
    "build_18.json": "89a69e5a6d90a86eeffb13d48b513d3973a16cecebbb4ed40d366969059dd1bd",
    "build_19.json": "13b733c58c05f6f4353cd97231f562d612044701da4dfb7d23877bfe20a19930",
    "build_20.json": "68a0d852df4f6d91e7c347a95394126f4141ac87d6a26ed3cd0cc096b6e9bfcb",
}

EXPECTED_MAIN_GO_SHA256 = "379525ce6c1b1dc1bf7454a1f7f3ea285044c7b4f4bcf3ec2d6fe99519cab9b3"
EXPECTED_SCHEMA_SHA256 = "d3693cabaf38cad36bf96c821cf6705990d1e19c1eb182c4bc70da981960623c"
EXPECTED_SESSION_FMT_SHA256 = "c06ad62a46ce92bc2b887d309e4704b57fcbc0c97a6b460d7961ec28f2ea347f"
EXPECTED_RULES_SHA256 = "0a19e1c7492986ca4d04e184c356ab7d33948c90da40aaf736fab4e762af6cd5"

SUMMARY_KEYS = [
    "sessions_analyzed",
    "equivalent_sessions",
    "divergent_sessions",
    "total_divergences_found",
    "stress_schedules_run",
    "stress_schedules_passed",
]

SESSION_KEYS = [
    "session_id",
    "equivalent",
    "divergences",
    "checkpoint_valid",
    "deterministic",
    "rollback_valid",
    "distributed_consistent",
    "compression_valid",
    "symbol_consistent",
    "optimization_divergent",
    "toolchain_fix_order",
    "stress",
]

STRESS_KEYS = ["schedules_run", "schedules_passed", "validated"]
DIVERGENCE_KEYS = ["kind", "toolchain", "seq", "detail"]
EXPECTED_SESSION_IDS = [f"build_{i:02d}" for i in range(1, 21)]

_ARTIFACTS_READY = False


def _hash_concat(parts: list[str]) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode())
        h.update(b"\0")
    return h.hexdigest()


def _sort_events(events: list[dict]) -> list[dict]:
    return sorted(events, key=lambda e: (e["seq"], e["toolchain"]))


def _div(
    kind: str, toolchain: str, seq: int, detail: str
) -> dict[str, object]:
    return {"kind": kind, "toolchain": toolchain, "seq": seq, "detail": detail}


def _check_determinism(events: list[dict]) -> tuple[bool, list[dict]]:
    seen: dict[tuple[int, str], str] = {}
    ok = True
    divs: list[dict] = []
    for e in events:
        key = (e["seq"], e["toolchain"])
        if key in seen and seen[key] != e["new_hash"]:
            ok = False
            divs.append(
                _div(
                    "nondeterministic_emit",
                    e["toolchain"],
                    e["seq"],
                    f"conflicting hashes {seen[key]} vs {e['new_hash']}",
                )
            )
        else:
            seen[key] = e["new_hash"]
    return ok, divs


def _check_hash_chains(events: list[dict]) -> tuple[bool, list[dict]]:
    chains: dict[tuple[str, str], list[dict]] = {}
    for e in events:
        chains.setdefault((e["toolchain"], e["artifact_ref"]), []).append(e)
    ok = True
    divs: list[dict] = []
    for (tc, ref), evs in chains.items():
        evs = sorted(evs, key=lambda x: x["seq"])
        for i, e in enumerate(evs):
            want = "" if i == 0 else evs[i - 1]["new_hash"]
            if e["prev_hash"] != want:
                ok = False
                divs.append(
                    _div(
                        "hash_chain_break",
                        tc,
                        e["seq"],
                        f"prev {e['prev_hash']} expected {want} on {ref}",
                    )
                )
    return ok, divs


def _find_event(events: list[dict], seq: int, toolchain: str, stage: str) -> dict | None:
    for e in events:
        if e["seq"] == seq and e["toolchain"] == toolchain and e["stage"] == stage:
            return e
    return None


def _check_checkpoints(cps: list[dict], events: list[dict]) -> tuple[bool, list[dict]]:
    ok = True
    divs: list[dict] = []
    for c in cps:
        e = _find_event(events, c["seq"], c["toolchain"], c["stage"])
        if e is None:
            ok = False
            divs.append(
                _div(
                    "missing_checkpoint_event",
                    c["toolchain"],
                    c["seq"],
                    f"no event for stage {c['stage']}",
                )
            )
            continue
        if e["new_hash"] != c["artifact_hash"]:
            ok = False
            divs.append(
                _div(
                    "checkpoint_hash_mismatch",
                    c["toolchain"],
                    c["seq"],
                    f"checkpoint {c['artifact_hash']} event {e['new_hash']}",
                )
            )
        if e["symbol_digest"] != c["symbol_digest"]:
            ok = False
            divs.append(
                _div(
                    "checkpoint_symbol_mismatch",
                    c["toolchain"],
                    c["seq"],
                    f"symbol {c['symbol_digest']} vs {e['symbol_digest']}",
                )
            )
    return ok, divs


def _check_compression(cps: list[dict]) -> tuple[bool, list[dict]]:
    ok = True
    divs: list[dict] = []
    for c in cps:
        if c["raw_size"] <= 0:
            ok = False
            divs.append(
                _div("compression_invalid", c["toolchain"], c["seq"], "raw_size must be positive")
            )
            continue
        expected = c["raw_size"] // 2
        if c["compressed_size"] != expected:
            ok = False
            divs.append(
                _div(
                    "compression_ratio_mismatch",
                    c["toolchain"],
                    c["seq"],
                    f"compressed {c['compressed_size']} expected {expected}",
                )
            )
    return ok, divs


def _check_symbols(events: list[dict], cps: list[dict]) -> tuple[bool, list[dict]]:
    cp_map = {f"{c['seq']}|{c['toolchain']}": c["symbol_digest"] for c in cps}
    ok = True
    divs: list[dict] = []
    seen: set[tuple[str, str, int]] = set()
    for e in events:
        key = f"{e['seq']}|{e['toolchain']}"
        if key in cp_map and e["symbol_digest"] != cp_map[key]:
            row = (
                "symbol_state_drift",
                e["toolchain"],
                e["seq"],
            )
            if row in seen:
                continue
            seen.add(row)
            ok = False
            divs.append(
                _div(
                    "symbol_state_drift",
                    e["toolchain"],
                    e["seq"],
                    f"event {e['symbol_digest']} checkpoint {cp_map[key]}",
                )
            )
    return ok, divs


def _final_hashes(events: list[dict]) -> dict[str, str]:
    max_seq: dict[str, int] = {}
    for e in events:
        max_seq[e["toolchain"]] = max(max_seq.get(e["toolchain"], -1), e["seq"])
    out: dict[str, str] = {}
    for e in events:
        if e["seq"] == max_seq[e["toolchain"]]:
            out[e["toolchain"]] = e["new_hash"]
    return out


def _check_cross(cross: bool, events: list[dict]) -> tuple[bool, list[dict]]:
    if not cross:
        return True, []
    fh = _final_hashes(events)
    if len(fh) < 2:
        return True, []
    ref_tc = sorted(fh.keys())[0]
    ref = fh[ref_tc]
    ok = True
    divs: list[dict] = []
    for tc in sorted(fh.keys())[1:]:
        if fh[tc] != ref:
            ok = False
            divs.append(
                _div(
                    "artifact_mismatch",
                    tc,
                    0,
                    f"final hash {fh[tc]} vs reference {ref}",
                )
            )
    return ok, divs


def _check_rollbacks(cps: list[dict], rollbacks: list[dict]) -> tuple[bool, list[dict]]:
    by_seq = {c["seq"]: c for c in cps}
    ok = True
    divs: list[dict] = []
    for r in rollbacks:
        cp = by_seq.get(r["restored_checkpoint"])
        if cp is None:
            ok = False
            divs.append(
                _div(
                    "rollback_checkpoint_missing",
                    "",
                    r["restored_checkpoint"],
                    f"attempt {r['attempt']}",
                )
            )
            continue
        if r["expected_symbol_digest"] != cp["symbol_digest"]:
            ok = False
            divs.append(
                _div(
                    "rollback_expected_mismatch",
                    cp["toolchain"],
                    r["restored_checkpoint"],
                    f"expected {r['expected_symbol_digest']} checkpoint {cp['symbol_digest']}",
                )
            )
        if r["actual_symbol_digest"] != cp["symbol_digest"]:
            ok = False
            divs.append(
                _div(
                    "rollback_restore_failed",
                    cp["toolchain"],
                    r["restored_checkpoint"],
                    f"actual {r['actual_symbol_digest']} checkpoint {cp['symbol_digest']}",
                )
            )
    return ok, divs


def _shard_hash(events: list[dict], seqs: list[int]) -> str:
    seq_set = set(seqs)
    parts = [
        e["new_hash"]
        for e in _sort_events(events)
        if e["seq"] in seq_set
    ]
    return _hash_concat(parts)


def _check_shards(events: list[dict], shards: list[dict]) -> tuple[bool, list[dict]]:
    if not shards:
        return True, []
    unique = {e["seq"] for e in events}
    covered: dict[int, int] = {}
    ok = True
    divs: list[dict] = []
    for sh in shards:
        want = _shard_hash(events, sh["event_seqs"])
        if want != sh["contribution_hash"]:
            ok = False
            divs.append(
                _div(
                    "shard_hash_mismatch",
                    sh["worker"],
                    0,
                    f"shard {sh['shard_id']}",
                )
            )
        for s in sh["event_seqs"]:
            covered[s] = covered.get(s, 0) + 1
    for seq in unique:
        if covered.get(seq, 0) != 1:
            ok = False
            divs.append(
                _div(
                    "shard_coverage_gap",
                    "",
                    seq,
                    f"covered {covered.get(seq, 0)} need 1",
                )
            )
    return ok, divs


def _check_opt(passes: list[dict]) -> bool:
    by_pass: dict[str, dict[str, str]] = {}
    for p in passes:
        by_pass.setdefault(p["pass_id"], {})[p["toolchain"]] = p["behavior_fingerprint"]
    for tc_map in by_pass.values():
        if len(set(tc_map.values())) > 1:
            return True
    return False


def _merge_divs(*parts: list[dict]) -> list[dict]:
    all_divs: list[dict] = []
    seen: set[str] = set()
    for part in parts:
        for d in part:
            key = f"{d['kind']}|{d['toolchain']}|{d['seq']}|{d['detail']}"
            if key in seen:
                continue
            seen.add(key)
            all_divs.append(d)
    return sorted(all_divs, key=lambda d: (d["kind"], d["toolchain"], d["seq"]))


def _fix_order(divs: list[dict], cross: bool, events: list[dict]) -> list[str]:
    tcs = {d["toolchain"] for d in divs if d["toolchain"]}
    if cross:
        fh = _final_hashes(events)
        if fh:
            ref_tc = sorted(fh.keys())[0]
            ref = fh[ref_tc]
            for tc, h in fh.items():
                if h != ref:
                    tcs.add(tc)
    return sorted(tcs)


def _replay_stress(
    events: list[dict],
    schedules: list[dict],
    fix_order: list[str],
    cross: bool,
) -> dict[str, object]:
    if not schedules:
        return {"schedules_run": 0, "schedules_passed": 0, "validated": True}
    enforce = bool(fix_order)
    passed = 0
    for sch in schedules:
        seq_set = set(sch["event_seq_order"])
        subset = []
        for e in events:
            if e["seq"] not in seq_set:
                continue
            if enforce and e["toolchain"] in fix_order:
                continue
            subset.append(e)
        subset = _sort_events(subset)
        _, det_divs = _check_determinism(subset)
        _, chain_divs = _check_hash_chains(subset)
        if len(det_divs) == 0 and len(chain_divs) == 0:
            passed += 1
    run = len(schedules)
    validated = passed == run
    if cross and events:
        unique = len({e["seq"] for e in events})
        all_full = all(len(s["event_seq_order"]) >= unique for s in schedules)
        all_prefix = all(len(s["event_seq_order"]) < unique for s in schedules)
        if all_prefix and not all_full:
            validated = True
        if all_full and not all_prefix:
            validated = False
    return {"schedules_run": run, "schedules_passed": passed, "validated": validated}


def evaluate_session(sf: dict) -> dict:
    """Independent reference implementation of OUTPUT_SCHEMA.md rules."""
    events = _sort_events(list(sf.get("events") or []))
    cps = list(sf.get("checkpoints") or [])
    rollbacks = list(sf.get("rollbacks") or [])
    shards = list(sf.get("shards") or [])
    opts = list(sf.get("optimization_passes") or [])
    stress_obj = sf.get("stress") or {}
    schedules = list(stress_obj.get("schedules") or [])
    cross = bool(sf.get("cross_compile"))

    det_ok, det_divs = _check_determinism(events)
    chain_ok, chain_divs = _check_hash_chains(events)
    cp_ok, cp_divs = _check_checkpoints(cps, events)
    comp_ok, comp_divs = _check_compression(cps)
    sym_ok, sym_divs = _check_symbols(events, cps)
    cross_ok, cross_divs = _check_cross(cross, events)
    rb_ok, rb_divs = _check_rollbacks(cps, rollbacks)
    sh_ok, sh_divs = _check_shards(events, shards)
    opt_div = _check_opt(opts)

    divs = _merge_divs(
        det_divs, chain_divs, cp_divs, comp_divs, sym_divs, cross_divs, rb_divs, sh_divs
    )
    fix = _fix_order(divs, cross, events)
    equivalent = (
        det_ok
        and chain_ok
        and cp_ok
        and comp_ok
        and sym_ok
        and cross_ok
        and rb_ok
        and sh_ok
        and not opt_div
        and len(divs) == 0
    )
    stress = _replay_stress(events, schedules, fix, cross)
    return {
        "session_id": sf["session_id"],
        "equivalent": equivalent,
        "divergences": divs,
        "checkpoint_valid": cp_ok,
        "deterministic": det_ok,
        "rollback_valid": rb_ok,
        "distributed_consistent": sh_ok,
        "compression_valid": comp_ok,
        "symbol_consistent": sym_ok,
        "optimization_divergent": opt_div,
        "toolchain_fix_order": fix,
        "stress": stress,
    }


def reference_report(session_dir: Path = SESSION_DIR) -> dict:
    sessions = []
    for i in range(1, 21):
        path = session_dir / f"build_{i:02d}.json"
        sf = json.loads(path.read_text(encoding="utf-8"))
        sessions.append(evaluate_session(sf))
    sessions.sort(key=lambda s: s["session_id"])
    summary = {
        "sessions_analyzed": 20,
        "equivalent_sessions": sum(1 for s in sessions if s["equivalent"]),
        "divergent_sessions": sum(1 for s in sessions if not s["equivalent"]),
        "total_divergences_found": sum(len(s["divergences"]) for s in sessions),
        "stress_schedules_run": sum(s["stress"]["schedules_run"] for s in sessions),
        "stress_schedules_passed": sum(s["stress"]["schedules_passed"] for s in sessions),
    }
    return {"summary": summary, "sessions": sessions}


def _mutate_hard_worker_stress(data: dict) -> None:
    """build_06 + worker-2 chain-break event; stress must omit worker toolchain rows."""
    data["events"].append(
        {
            "seq": 3,
            "toolchain": "worker-2",
            "stage": "shard_merge",
            "op": "emit",
            "artifact_ref": "obj",
            "prev_hash": "broken_prev",
            "new_hash": "worker_bad_hash",
            "symbol_digest": "worker_sym",
        }
    )
    data["stress"] = {
        "schedules": [
            {"schedule_id": "full", "event_seq_order": [1, 2, 3]},
            {"schedule_id": "prefix", "event_seq_order": [1]},
        ]
    }


def _mutate_hard_dual_ref(data: dict) -> None:
    """build_10 + independent lib artifact_ref chain break at higher seq."""
    data["events"].extend(
        [
            {
                "seq": 4,
                "toolchain": "gcc-13",
                "stage": "preprocess",
                "op": "emit",
                "artifact_ref": "lib",
                "prev_hash": "",
                "new_hash": "lib_h1",
                "symbol_digest": "s1",
            },
            {
                "seq": 5,
                "toolchain": "gcc-13",
                "stage": "compile",
                "op": "emit",
                "artifact_ref": "lib",
                "prev_hash": "broken_lib",
                "new_hash": "lib_h2",
                "symbol_digest": "s2",
            },
        ]
    )


def _mutate_hard_rollback_stress(data: dict) -> None:
    """build_05 + stress schedules; gcc-13 omission required for both to pass."""
    data["stress"] = {
        "schedules": [
            {"schedule_id": "s1", "event_seq_order": [1, 2]},
            {"schedule_id": "s2", "event_seq_order": [1]},
        ]
    }


def prepare_verifier_artifacts() -> None:
    """Build checker and capture default/swap/probe/mixed/hard reports."""
    global _ARTIFACTS_READY
    if _ARTIFACTS_READY:
        return
    _ART_BASE.mkdir(parents=True, exist_ok=True)

    subprocess.run(["make", "build"], cwd="/app", check=False, timeout=180)

    def _run_checker(env: dict[str, str] | None = None) -> bool:
        if not BIN.exists():
            return False
        env_map = {**os.environ, **(env or {})}
        result = subprocess.run(
            [str(BIN)],
            cwd="/app",
            env=env_map,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        return result.returncode == 0

    def _copy_report(dest: Path) -> None:
        if REPORT.exists():
            shutil.copy2(REPORT, dest)

    def _capture_equiv_fixture(
        root_name: str,
        report_dest: Path,
        src_name: str,
        mutate: Callable[[dict], None] | None = None,
    ) -> None:
        root = Path(f"/tmp/equiv-{root_name}")
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        shutil.copytree(SESSION_DIR, root, dirs_exist_ok=True)
        payload = json.loads((SESSION_DIR / src_name).read_text(encoding="utf-8"))
        payload["session_id"] = "build_20"
        if mutate is not None:
            mutate(payload)
        (root / "build_20.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        env = {"EQUIV_SESSION_DIR": str(root)}
        if REPORT.exists():
            REPORT.unlink()
        if _run_checker(env):
            _copy_report(report_dest)

    if _run_checker():
        _copy_report(REPORT_FIRST)
    if _run_checker():
        _copy_report(REPORT_SECOND)

    swap_root = Path("/tmp/equiv-verify-sessions")
    if swap_root.exists():
        shutil.rmtree(swap_root)
    swap_root.mkdir(parents=True)
    shutil.copytree(SESSION_DIR, swap_root, dirs_exist_ok=True)
    src = SESSION_DIR / "build_02.json"
    dst = swap_root / "build_01.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    data["session_id"] = "build_01"
    dst.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    decoy = {
        "session_id": "build_99",
        "cross_compile": False,
        "toolchains": [],
        "checkpoints": [],
        "events": [],
        "rollbacks": [],
        "shards": [],
        "optimization_passes": [],
    }
    (swap_root / "build_99.json").write_text(json.dumps(decoy, indent=2) + "\n", encoding="utf-8")
    swap_env = {"EQUIV_SESSION_DIR": str(swap_root)}
    if REPORT.exists():
        REPORT.unlink()
    if _run_checker(swap_env):
        _copy_report(REPORT_SWAP)
    if REPORT.exists():
        REPORT.unlink()
    if _run_checker(swap_env):
        _copy_report(REPORT_SWAP_SECOND)

    probe_root = Path("/tmp/equiv-probe-build07")
    if probe_root.exists():
        shutil.rmtree(probe_root)
    probe_root.mkdir(parents=True)
    shutil.copytree(SESSION_DIR, probe_root, dirs_exist_ok=True)
    probe_data = json.loads((SESSION_DIR / "build_04.json").read_text(encoding="utf-8"))
    probe_data["session_id"] = "build_07"
    (probe_root / "build_07.json").write_text(
        json.dumps(probe_data, indent=2) + "\n", encoding="utf-8"
    )
    probe_env = {"EQUIV_SESSION_DIR": str(probe_root)}
    if REPORT.exists():
        REPORT.unlink()
    if _run_checker(probe_env):
        _copy_report(REPORT_PROBE)

    # Mixed stress + opt + chain break on swapped build_20 → exposes enforce_fix_order
    # when fix_order contains compiler ids vs worker ids.
    mixed_root = Path("/tmp/equiv-mixed-stress")
    if mixed_root.exists():
        shutil.rmtree(mixed_root)
    mixed_root.mkdir(parents=True)
    shutil.copytree(SESSION_DIR, mixed_root, dirs_exist_ok=True)
    b10 = json.loads((SESSION_DIR / "build_10.json").read_text(encoding="utf-8"))
    b10["session_id"] = "build_20"
    b10["stress"] = {
        "schedules": [
            {"schedule_id": "s1", "event_seq_order": [1, 2, 3]},
            {"schedule_id": "s2", "event_seq_order": [1]},
        ]
    }
    (mixed_root / "build_20.json").write_text(json.dumps(b10, indent=2) + "\n", encoding="utf-8")
    mixed_env = {"EQUIV_SESSION_DIR": str(mixed_root)}
    if REPORT.exists():
        REPORT.unlink()
    if _run_checker(mixed_env):
        _copy_report(REPORT_MIXED)

    _capture_equiv_fixture(
        "hard-worker-stress",
        REPORT_HARD_WORKER_STRESS,
        "build_06.json",
        _mutate_hard_worker_stress,
    )
    _capture_equiv_fixture(
        "hard-dual-ref",
        REPORT_HARD_DUAL_REF,
        "build_10.json",
        _mutate_hard_dual_ref,
    )
    _capture_equiv_fixture(
        "hard-rollback-stress",
        REPORT_HARD_ROLLBACK_STRESS,
        "build_05.json",
        _mutate_hard_rollback_stress,
    )
    _capture_equiv_fixture(
        "hard-nondet-checkpoint",
        REPORT_HARD_NONDET_CHECKPOINT,
        "build_04.json",
    )
    _capture_equiv_fixture(
        "hard-full-stress-invalid",
        REPORT_HARD_FULL_STRESS_INVALID,
        "build_14.json",
    )

    if REPORT.exists():
        REPORT.unlink()
    _run_checker()
    _ARTIFACTS_READY = True


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_report(path: Path = REPORT) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _by_id(report: dict) -> dict[str, dict]:
    return {s["session_id"]: s for s in report["sessions"]}


def _assert_key_order(obj: dict, expected: list[str], label: str) -> None:
    assert list(obj.keys()) == expected, f"{label} key order mismatch"


def _assert_session_match(actual: dict, expected: dict, sid: str) -> None:
    for key in (
        "equivalent",
        "checkpoint_valid",
        "deterministic",
        "rollback_valid",
        "distributed_consistent",
        "compression_valid",
        "symbol_consistent",
        "optimization_divergent",
        "toolchain_fix_order",
        "stress",
    ):
        assert actual[key] == expected[key], f"{sid}.{key}: {actual[key]!r} != {expected[key]!r}"
    assert [d["kind"] for d in actual["divergences"]] == [
        d["kind"] for d in expected["divergences"]
    ], sid
    assert [d["toolchain"] for d in actual["divergences"]] == [
        d["toolchain"] for d in expected["divergences"]
    ], sid
    assert [d["seq"] for d in actual["divergences"]] == [
        d["seq"] for d in expected["divergences"]
    ], sid
    assert [d["detail"] for d in actual["divergences"]] == [
        d["detail"] for d in expected["divergences"]
    ], sid


def test_verifier_harness_prepared_artifacts():
    """tests/test.sh must run prepare_verifier_artifacts before pytest."""
    assert _ARTIFACTS_READY or REPORT_FIRST.exists()


def test_bundled_session_checksums_unchanged():
    """Anti-tamper: bundled build session files must match embedded SHA256 manifest."""
    for name, expected in BUNDLED_DATA_CHECKSUMS.items():
        path = SESSION_DIR / name
        assert path.exists(), f"missing {name}"
        assert _sha256_file(path) == expected, f"tampered {name}"


def test_immutable_environment_files_unchanged():
    """Agent must not edit main.go, schema, session format, or policy files."""
    assert _sha256_file(MAIN_GO) == EXPECTED_MAIN_GO_SHA256
    assert _sha256_file(SCHEMA) == EXPECTED_SCHEMA_SHA256
    assert _sha256_file(Path("/app/references/session_format.md")) == EXPECTED_SESSION_FMT_SHA256
    assert _sha256_file(RULES) == EXPECTED_RULES_SHA256


def test_binary_built_and_stub_removed():
    """make build must produce executable checker exceeding 2048 bytes without stub panic."""
    assert BIN.exists() and os.access(BIN, os.X_OK)
    assert BIN.stat().st_size > 2048
    src = EVALUATE_GO.read_text(encoding="utf-8")
    assert STUB_NOT_IMPLEMENTED not in src


def test_report_schema_and_key_order():
    """Report must follow OUTPUT_SCHEMA.md top-level and nested key order."""
    report = _load_report()
    _assert_key_order(report, ["summary", "sessions"], "top level")
    _assert_key_order(report["summary"], SUMMARY_KEYS, "summary")
    assert len(report["sessions"]) == 20
    for sess in report["sessions"]:
        _assert_key_order(sess, SESSION_KEYS, sess["session_id"])
        _assert_key_order(sess["stress"], STRESS_KEYS, f"{sess['session_id']}.stress")
        for div in sess["divergences"]:
            _assert_key_order(div, DIVERGENCE_KEYS, "divergence")


def test_sessions_sorted_by_session_id():
    """Report sessions array must be sorted by session_id ascending."""
    report = _load_report()
    ids = [s["session_id"] for s in report["sessions"]]
    assert ids == EXPECTED_SESSION_IDS


def test_full_report_matches_independent_reference_evaluator():
    """Agent output must match independent Python recompute of OUTPUT_SCHEMA rules."""
    actual = _load_report()
    expected = reference_report()
    assert actual["summary"] == expected["summary"]
    a_by = _by_id(actual)
    e_by = _by_id(expected)
    for sid in EXPECTED_SESSION_IDS:
        _assert_session_match(a_by[sid], e_by[sid], sid)


def test_equivalent_derivation_from_boolean_checks():
    """equivalent must equal (all validity true AND not opt AND empty divergences)."""
    by = _by_id(_load_report())
    for sid, s in by.items():
        all_valid = all(
            s[k]
            for k in (
                "checkpoint_valid",
                "deterministic",
                "rollback_valid",
                "distributed_consistent",
                "compression_valid",
                "symbol_consistent",
            )
        )
        derived = all_valid and not s["optimization_divergent"] and s["divergences"] == []
        assert s["equivalent"] is derived, sid


def test_summary_totals_against_reference():
    """Summary counters must equal reference evaluator totals on bundled sessions."""
    actual = _load_report()["summary"]
    expected = reference_report()["summary"]
    assert actual == expected
    assert actual["equivalent_sessions"] == 5
    assert actual["divergent_sessions"] == 15
    assert actual["total_divergences_found"] == 19
    assert actual["stress_schedules_run"] == 4
    assert actual["stress_schedules_passed"] == 4


def test_deterministic_report_bytes():
    """Consecutive checker runs on bundled data must write byte-identical reports."""
    assert REPORT_FIRST.exists() and REPORT_SECOND.exists()
    assert REPORT_FIRST.read_bytes() == REPORT_SECOND.read_bytes()
    raw = REPORT.read_bytes()
    assert raw.endswith(b"\n")
    json.loads(raw.decode("utf-8"))


def test_clean_sessions_use_empty_arrays_not_null():
    """Equivalent sessions must use empty JSON arrays for divergences and fix order."""
    by = _by_id(_load_report())
    ref = _by_id(reference_report())
    for sid, s in by.items():
        if ref[sid]["equivalent"]:
            assert s["divergences"] == []
            assert s["toolchain_fix_order"] == []


def test_divergences_sorted_lexicographically():
    """Divergence rows must be sorted by kind, toolchain, then seq ascending."""
    report = _load_report()
    for sess in report["sessions"]:
        divs = sess["divergences"]
        assert divs == sorted(divs, key=lambda d: (d["kind"], d["toolchain"], d["seq"]))


def test_stress_prefix_vs_full_schedule_validation():
    """build_13 prefix stress validated true; build_14 full stress validated false."""
    by = _by_id(_load_report())
    assert by["build_13"]["stress"]["validated"] is True
    assert by["build_13"]["stress"]["schedules_run"] == 2
    assert by["build_14"]["stress"]["validated"] is False
    assert by["build_14"]["stress"]["schedules_run"] == 2
    assert by["build_14"]["stress"]["schedules_passed"] == by["build_14"]["stress"]["schedules_run"]
    assert by["build_13"]["stress"] == reference_report()["sessions"][12]["stress"]
    assert by["build_14"]["stress"] == reference_report()["sessions"][13]["stress"]


def test_build_01_artifact_mismatch_detail_and_reference_hash():
    """build_01 artifact_mismatch detail must use reference-final template."""
    divs = _by_id(_load_report())["build_01"]["divergences"]
    ref_divs = _by_id(reference_report())["build_01"]["divergences"]
    assert any(d["kind"] == "artifact_mismatch" for d in divs)
    assert divs == ref_divs


def test_build_04_cascaded_kind_seq_and_details():
    """build_04 must match reference cascade; checkpoint_valid true despite nondeterministic_emit."""
    actual = _by_id(_load_report())["build_04"]
    expected = _by_id(reference_report())["build_04"]
    _assert_session_match(actual, expected, "build_04")
    assert actual["checkpoint_valid"] is True
    assert actual["deterministic"] is False
    assert [d["kind"] for d in actual["divergences"]].count("hash_chain_break") == 2


def test_build_06_worker_fix_order_not_compiler_id():
    """build_06 shard_hash_mismatch uses seq 0 and worker-2 toolchain/fix order."""
    s = _by_id(_load_report())["build_06"]
    assert s["toolchain_fix_order"] == ["worker-2"]
    assert s["divergences"][0]["kind"] == "shard_hash_mismatch"
    assert s["divergences"][0]["seq"] == 0
    assert s["divergences"][0]["toolchain"] == "worker-2"
    assert s["divergences"][0]["detail"] == "shard shard-b"
    assert s["distributed_consistent"] is False


def test_build_09_optimization_only_empty_fix_order():
    """build_09 optimization divergence leaves divergences and fix order empty."""
    s = _by_id(_load_report())["build_09"]
    assert s["optimization_divergent"] is True
    assert s["divergences"] == []
    assert s["toolchain_fix_order"] == []
    assert s["equivalent"] is False


def test_build_10_hash_chain_break_keeps_deterministic_true():
    """build_10 hash_chain_break must not flip deterministic."""
    s = _by_id(_load_report())["build_10"]
    assert {d["kind"] for d in s["divergences"]} == {"hash_chain_break"}
    assert s["deterministic"] is True
    assert s["equivalent"] is False
    assert s["divergences"][0]["detail"].startswith("prev broken_prev_hash0 expected ")


def test_build_05_rollback_detail_and_checkpoint_toolchain():
    """build_05 rollback_restore_failed uses gcc-13 last-wins checkpoint at seq 2."""
    s = _by_id(_load_report())["build_05"]
    expected = _by_id(reference_report())["build_05"]
    _assert_session_match(s, expected, "build_05")
    assert s["toolchain_fix_order"] == ["gcc-13"]
    rollback = next(d for d in s["divergences"] if d["kind"] == "rollback_restore_failed")
    assert rollback["toolchain"] == "gcc-13"


def test_build_08_dual_symbol_and_checkpoint_flags():
    """build_08 emits both checkpoint_symbol_mismatch and symbol_state_drift."""
    s = _by_id(_load_report())["build_08"]
    expected = _by_id(reference_report())["build_08"]
    _assert_session_match(s, expected, "build_08")
    assert s["checkpoint_valid"] is False
    assert s["symbol_consistent"] is False


def test_build_19_coverage_gap_seq_and_empty_fix():
    """build_19 shard_coverage_gap reports uncovered seq with empty toolchain/fix order."""
    s = _by_id(_load_report())["build_19"]
    expected = _by_id(reference_report())["build_19"]
    _assert_session_match(s, expected, "build_19")


def test_build_11_combined_artifact_and_chain_break():
    """build_11 must emit both artifact_mismatch and hash_chain_break with fix gcc-13."""
    s = _by_id(_load_report())["build_11"]
    expected = _by_id(reference_report())["build_11"]
    _assert_session_match(s, expected, "build_11")


def test_equiv_session_dir_swap_fixture():
    """EQUIV_SESSION_DIR swap makes build_01 equivalent; swap runs are byte-identical."""
    assert REPORT_SWAP.exists() and REPORT_SWAP_SECOND.exists()
    assert REPORT_SWAP.read_bytes() == REPORT_SWAP_SECOND.read_bytes()
    swap = _load_report(REPORT_SWAP)
    assert _by_id(swap)["build_01"]["equivalent"] is True
    assert (
        swap["summary"]["equivalent_sessions"]
        >= _load_report()["summary"]["equivalent_sessions"]
    )


def test_equiv_session_dir_probe_fixture():
    """Probe replacing build_07 with build_04 events yields nondeterministic divergence."""
    assert REPORT_PROBE.exists()
    probe = _load_report(REPORT_PROBE)
    s = _by_id(probe)["build_07"]
    assert s["equivalent"] is False
    assert "nondeterministic_emit" in {d["kind"] for d in s["divergences"]}
    assert s["deterministic"] is False


def test_mixed_stress_fixture_enforce_compiler_fix_order():
    """Mixed EQUIV_SESSION_DIR fixture: build_20=build_10+stress must match reference recompute."""
    assert REPORT_MIXED.exists()
    mixed = _load_report(REPORT_MIXED)
    b10 = json.loads((SESSION_DIR / "build_10.json").read_text(encoding="utf-8"))
    b10["session_id"] = "build_20"
    b10["stress"] = {
        "schedules": [
            {"schedule_id": "s1", "event_seq_order": [1, 2, 3]},
            {"schedule_id": "s2", "event_seq_order": [1]},
        ]
    }
    expected = evaluate_session(b10)
    actual = _by_id(mixed)["build_20"]
    _assert_session_match(actual, expected, "build_20-mixed")
    # Mixed prefix+full does not force validated false; enforce_toolchain_fix_order
    # omits gcc-13 events so schedules can still pass while fix order lists gcc-13.
    assert actual["stress"]["schedules_run"] == 2
    assert actual["toolchain_fix_order"] == ["gcc-13"]
    assert actual["stress"]["validated"] is expected["stress"]["validated"]
    assert actual["stress"]["schedules_passed"] == expected["stress"]["schedules_passed"]


def test_hard_stress_worker_event_omission_fixture():
    """EQUIV fixture: omit worker-2 toolchain events during stress replay."""
    assert REPORT_HARD_WORKER_STRESS.exists()
    payload = json.loads((SESSION_DIR / "build_06.json").read_text(encoding="utf-8"))
    payload["session_id"] = "build_20"
    _mutate_hard_worker_stress(payload)
    expected = evaluate_session(payload)
    actual = _by_id(_load_report(REPORT_HARD_WORKER_STRESS))["build_20"]
    _assert_session_match(actual, expected, "build_20-worker-stress")
    assert actual["toolchain_fix_order"] == ["worker-2"]
    assert actual["stress"]["schedules_passed"] == 2
    assert actual["stress"]["validated"] is True


def test_hard_dual_artifact_ref_independent_chains_fixture():
    """EQUIV fixture: hash chains are per (toolchain, artifact_ref); lib break is separate."""
    assert REPORT_HARD_DUAL_REF.exists()
    payload = json.loads((SESSION_DIR / "build_10.json").read_text(encoding="utf-8"))
    payload["session_id"] = "build_20"
    _mutate_hard_dual_ref(payload)
    expected = evaluate_session(payload)
    actual = _by_id(_load_report(REPORT_HARD_DUAL_REF))["build_20"]
    _assert_session_match(actual, expected, "build_20-dual-ref")
    assert actual["deterministic"] is True
    chain_divs = [d for d in actual["divergences"] if d["kind"] == "hash_chain_break"]
    assert len(chain_divs) == 2
    details = {d["detail"] for d in chain_divs}
    assert any(" on obj" in d for d in details)
    assert any(" on lib" in d for d in details)
    assert actual["divergences"][0]["kind"] == "artifact_mismatch"
    assert actual["divergences"][0]["toolchain"] == "gcc-13"
    assert "lib_h2" in actual["divergences"][0]["detail"]


def test_hard_rollback_stress_compiler_omit_fixture():
    """EQUIV fixture: build_05 stress must omit gcc-13 events when fix order is non-empty."""
    assert REPORT_HARD_ROLLBACK_STRESS.exists()
    payload = json.loads((SESSION_DIR / "build_05.json").read_text(encoding="utf-8"))
    payload["session_id"] = "build_20"
    _mutate_hard_rollback_stress(payload)
    expected = evaluate_session(payload)
    actual = _by_id(_load_report(REPORT_HARD_ROLLBACK_STRESS))["build_20"]
    _assert_session_match(actual, expected, "build_20-rollback-stress")
    assert actual["toolchain_fix_order"] == ["gcc-13"]
    assert actual["stress"]["schedules_passed"] == 2
    assert actual["stress"]["validated"] is True


def test_hard_nondeterministic_checkpoint_valid_fixture():
    """EQUIV fixture: checkpoint_valid stays true when first matching-stage event agrees."""
    assert REPORT_HARD_NONDET_CHECKPOINT.exists()
    payload = json.loads((SESSION_DIR / "build_04.json").read_text(encoding="utf-8"))
    payload["session_id"] = "build_20"
    expected = evaluate_session(payload)
    actual = _by_id(_load_report(REPORT_HARD_NONDET_CHECKPOINT))["build_20"]
    _assert_session_match(actual, expected, "build_20-nondet-checkpoint")
    assert actual["checkpoint_valid"] is True
    assert actual["deterministic"] is False
    drift = next(d for d in actual["divergences"] if d["kind"] == "symbol_state_drift")
    assert drift["detail"] == "event nondeterministic01 checkpoint eda387559a39efab"


def test_hard_all_full_cross_stress_invalidated_fixture():
    """EQUIV fixture: all-full cross-compile stress forces validated false even when all pass."""
    assert REPORT_HARD_FULL_STRESS_INVALID.exists()
    payload = json.loads((SESSION_DIR / "build_14.json").read_text(encoding="utf-8"))
    payload["session_id"] = "build_20"
    expected = evaluate_session(payload)
    actual = _by_id(_load_report(REPORT_HARD_FULL_STRESS_INVALID))["build_20"]
    _assert_session_match(actual, expected, "build_20-full-stress-invalid")
    assert actual["stress"]["schedules_passed"] == actual["stress"]["schedules_run"]
    assert actual["stress"]["validated"] is False
    assert actual["toolchain_fix_order"] == ["gcc-13"]


def test_policy_yaml_required_keys():
    """equivalence_rules.yaml must ship required ordering and validation keys."""
    rules = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    assert rules["ordering"]["primary_key"] == "seq"
    assert rules["ordering"]["secondary_key"] == "toolchain"
    assert rules["compression"]["ratio_denominator"] == 2
    assert rules["cross_toolchain"]["require_final_hash_match"] is True
    assert rules["stress"]["enforce_toolchain_fix_order"] is True
