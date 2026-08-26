"""Verifier for the Go package relocation consistency validator."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

REPORT = Path("/app/artifacts/relocation_consistency_report.json")
_ART_BASE = Path(
    os.environ.get("RELOC_VERIFIER_ARTIFACT_DIR", "/tmp/reloc-verifier-artifacts")
)
REPORT_FIRST = _ART_BASE / "report_first.json"
REPORT_SECOND = _ART_BASE / "report_second.json"
REPORT_SWAP = _ART_BASE / "report_swap.json"
REPORT_SWAP_SECOND = _ART_BASE / "report_swap_second.json"
REPORT_PROBE = _ART_BASE / "report_probe_b07.json"
BIN = Path("/app/bin/reloccheck")
MAIN_GO = Path("/app/relocbin/main.go")
EVAL_GO = Path("/app/reloclogic/evaluate.go")
SPEC = Path("/app/RELOCATION_SPEC.md")
LAYOUT = Path("/app/REPORT_LAYOUT.md")
CANON = Path("/app/reloc-canon/rules.yaml")
BATCH_DIR = Path("/app/reloc-batches")
STUB = "reloclogic.EvaluateBatch not implemented"

BUNDLED_DATA_CHECKSUMS: dict[str, str] = {
    "batch_01.json": "ea82d16d5318152c690d96b45058e71c05f86d807a1b1ddd1471fdf90a27cba4",
    "batch_02.json": "e94a4c907340f7ce583cd7d3bb29707908ffad4c96ce20bdeb4954d9aa5812d5",
    "batch_03.json": "a73705f68d135623d3ca6930b365c616bcb876682f11c85f38ddbdb6c02cad64",
    "batch_04.json": "d83c906189794bd8313fe8fa20b4a7007b72abcd9d664371c8790ecaf1a33b45",
    "batch_05.json": "b11c07b152642ba9983d716d321d8d3bff13dfeff3261083bfec392ad0450b07",
    "batch_06.json": "2c178b18624475aafbe91501a8c0331b08f77705fe92cff76a3cd74bd7bc329c",
    "batch_07.json": "20333b18e4a29f7279b54e5bf555b1ede520d2c797fda4b08cf1aa4b257a0708",
    "batch_08.json": "7a11d5a38f3243a63b1964b40f3893d80b723812ddd0b0c8d3781fd435b46e73",
    "batch_09.json": "4a37d370cd28ef03fcf3b22bfa432dc45b991d59f83f9c0f218f0346342c28dd",
    "batch_10.json": "1cdeeabbf9a1e8cd017d07673b30b3ac1df8580177232b09a6644c78f15347d0",
    "batch_11.json": "251d529754790f5615d9d6dba8305a39793b79be2338336117bd8ae94ba37c2f",
    "batch_12.json": "79abfc81a3862f7f569d836f17b7d73fe0af507d0bea8423010fbfa131b44975",
    "batch_13.json": "b2ff6888a0a6e2c7ba587fc10cc77474221883056b24a519039f46f493071959",
    "batch_14.json": "b9d7aff4474b81a03505e8c3af2e57c03a8ab859db23fdb966a9dc33223137aa",
    "batch_15.json": "8482eeb765d0a4f5f4b2f7725d8e0a456b46942ec3e1655368cd523a9b779d0d",
    "batch_16.json": "64bdf8e48a3524e93aeb675beac1ae8902106a4f1430b15f231ac08c6a81b5e1",
    "batch_17.json": "2984f5a8511522c147a6cc44f4a43e56c9ec9c7600c5481444afdc00144e2c7c",
    "batch_18.json": "ab4b4db3c89be814d6f3cc743302b926e7aec426a5ce23c28bc6a881f8962907",
    "batch_19.json": "8cf78b933efde0463cb67ad98b0e2ec3b4c52a10a34660234367cb0e0b535287",
    "batch_20.json": "98df0a8c0db3bc0d86e3b9556b07828f13028b6cc1d03f0cbe0a4ca56b9df17b",
}

EXPECTED_MAIN_GO_SHA256 = "383f641a00d3d56627a1d80fc927d7dfdf77e1d9d02c02988c4cdb35c063a720"
EXPECTED_SPEC_SHA256 = "cf0976cc406a97ee1b3308e04a0837be528933b593a455a12e7b441c12aaa48b"
EXPECTED_LAYOUT_SHA256 = "d38eb662434f8aa1b8b61f82eb3c2ceaab7e24a40b15f1e83d3b0dabedab8fa4"
EXPECTED_CANON_SHA256 = "fdad58d4c1829ff1e53f3abb115f98c68f18260ca234af3d195e182278120f2d"
EXPECTED_REPORT_FINGERPRINT_HEX = (
    "39beeace287dae7d19491e295273d5aa73a29487a26c2212b3f4861a38b53f65"
)


EXPECTED_RELOCATION_OK: dict[str, bool] = {
    "batch_01": False,
    "batch_02": True,
    "batch_03": False,
    "batch_04": True,
    "batch_05": False,
    "batch_06": True,
    "batch_07": False,
    "batch_08": False,
    "batch_09": False,
    "batch_10": False,
    "batch_11": False,
    "batch_12": True,
    "batch_13": False,
    "batch_14": False,
    "batch_15": False,
    "batch_16": False,
    "batch_17": False,
    "batch_18": False,
    "batch_19": False,
    "batch_20": False,
}

CLEAN_IDS = {"batch_02", "batch_04", "batch_06", "batch_12"}
SUMMARY_KEYS = [
    "batches_analyzed",
    "failed_batches",
    "clean_batches",
    "total_findings",
    "replay_runs",
    "replay_passed",
]

_ARTIFACTS_READY = False


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fingerprint(report: dict, batch_dir: Path) -> str:
    parts = []
    for name in sorted(BUNDLED_DATA_CHECKSUMS):
        parts.append(_sha256_file(batch_dir / name))
    data_digest = hashlib.sha256("".join(parts).encode()).hexdigest()
    flags = "".join("1" if m["relocation_ok"] else "0" for m in report["batches"])
    summary = report["summary"]
    lines = ["|".join(str(summary[k]) for k in SUMMARY_KEYS)]
    for m in report["batches"]:
        blob = []
        for f in m["findings"]:
            blob.append(
                f"{f['kind']}:{f['subject']}@{f['expected']}/{f['observed']}:{f['rule_id']}"
            )
        bits = (
            f"{int(m['mapping_ok'])}{int(m['rewrite_ok'])}{int(m['isolation_ok'])}"
            f"{int(m['identity_ok'])}{int(m['rollback_ok'])}"
        )
        cond = m["replay"]
        lines.append(
            f"{m['batch_id']}|{int(m['relocation_ok'])}|{len(m['findings'])}|{bits}|"
            f"{cond['schedules_run']}:{cond['schedules_passed']}:{int(cond['stable'])}|"
            + ";".join(blob)
        )
    struct = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    return hashlib.sha256((data_digest + flags + struct).encode()).hexdigest()


def _run_bin(env: dict[str, str] | None = None) -> None:
    base = os.environ.copy()
    if env:
        base.update(env)
    subprocess.run([str(BIN)], check=True, env=base)


def _walk_symbol_fqns(units: list) -> list[str]:
    out: list[str] = []

    def rec(us: list) -> None:
        for u in us:
            for s in u.get("symbols", []):
                out.append(s["fqn"])
            if u.get("nested"):
                rec(u["nested"])

    rec(units)
    return out


def _walk_resource_content_refs(units: list) -> list[str]:
    out: list[str] = []

    def rec(us: list) -> None:
        for u in us:
            for r in u.get("resources", []):
                out.append(r["content_ref"])
            if u.get("nested"):
                rec(u["nested"])

    rec(units)
    return out


def _collect_names(units: list) -> list[str]:
    out: list[str] = []

    def rec(us: list) -> None:
        for u in us:
            for s in u.get("symbols", []):
                out.append(s["fqn"])
            for r in u.get("refs", []):
                out.append(r["literal"])
            for res in u.get("resources", []):
                out.append(res["content_ref"])
            if u.get("nested"):
                rec(u["nested"])

    rec(units)
    return out


def _matches_prefix(name: str, pref: str) -> bool:
    return name == pref or name.startswith(pref + ".") or name.startswith(pref + "/")


def _effective_map_bind(units: list, mappings: list) -> str:
    """Seq-ascending effective bind excluding stale, shadowed, and cycle nodes."""
    names = _collect_names(units)
    stale = {
        m["from_prefix"]
        for m in mappings
        if not any(_matches_prefix(n, m["from_prefix"]) for n in names)
    }
    shadowed: set[str] = set()
    for m in mappings:
        shadowers = [
            n["from_prefix"]
            for n in mappings
            if n["from_prefix"] != m["from_prefix"]
            and n["from_prefix"].startswith(m["from_prefix"] + ".")
        ]
        if not shadowers:
            continue
        won = False
        for name in names:
            best = None
            best_len = -1
            for cand in mappings:
                fp = cand["from_prefix"]
                if not _matches_prefix(name, fp):
                    continue
                if len(fp) > best_len:
                    best_len = len(fp)
                    best = cand
            if best is not None and best["from_prefix"] == m["from_prefix"]:
                won = True
                break
        if not won:
            shadowed.add(m["from_prefix"])
    graph = {m["from_prefix"]: m["to_prefix"] for m in mappings}
    cycle: set[str] = set()
    nodes = set(graph) | set(graph.values())
    for start in sorted(nodes):
        seen: list[str] = []
        cur = start
        for _ in range(len(nodes) + 3):
            if cur not in graph:
                break
            if cur in seen:
                body = seen[seen.index(cur) :]
                cycle.update(body)
                break
            seen.append(cur)
            cur = graph[cur]
    prefs = [
        m["from_prefix"]
        for m in sorted(mappings, key=lambda x: x["seq"])
        if m["from_prefix"] not in stale
        and m["from_prefix"] not in shadowed
        and m["from_prefix"] not in cycle
    ]
    return ",".join(prefs)


def _simulate_digest(
    batch_id: str, units: list, steps: list, mappings: list | None = None
) -> str:
    fqns = sorted(_walk_symbol_fqns(units))
    res_refs = sorted(_walk_resource_content_refs(units))
    seed = batch_id + "|" + ",".join(fqns) + "|res|" + ",".join(res_refs)
    digest = hashlib.sha256(seed.encode()).hexdigest()
    map_bind = ""
    if mappings is not None:
        map_bind = _effective_map_bind(units, mappings)
    for st in sorted(steps, key=lambda x: x["seq"]):
        if st.get("op") != "apply":
            continue
        if not st.get("fail"):
            if mappings is not None:
                digest = hashlib.sha256(
                    (digest + "|ok|" + str(st["seq"]) + "|maps|" + map_bind).encode()
                ).hexdigest()
            else:
                digest = hashlib.sha256(
                    (digest + "|ok|" + str(st["seq"])).encode()
                ).hexdigest()
        elif st.get("rollback"):
            pass
        else:
            digest = hashlib.sha256(
                (digest + "|fail|" + str(st["seq"])).encode()
            ).hexdigest()
    return digest


def prepare_verifier_artifacts() -> None:
    global _ARTIFACTS_READY
    if _ARTIFACTS_READY:
        return
    _ART_BASE.mkdir(parents=True, exist_ok=True)
    if not BIN.is_file():
        raise AssertionError("reloccheck binary missing")
    _run_bin()
    shutil.copyfile(REPORT, REPORT_FIRST)
    _run_bin()
    shutil.copyfile(REPORT, REPORT_SECOND)

    swap = _ART_BASE / "swap_batches"
    if swap.exists():
        shutil.rmtree(swap)
    shutil.copytree(BATCH_DIR, swap)
    payload = json.loads((swap / "batch_02.json").read_text(encoding="utf-8"))
    payload["batch_id"] = "batch_01"
    payload["observed"]["digest"] = _simulate_digest(
        payload["batch_id"],
        payload["units"],
        payload.get("steps", []),
        payload.get("mappings", []),
    )
    (swap / "batch_01.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    _run_bin({"RELOC_BATCH_DIR": str(swap)})
    shutil.copyfile(REPORT, REPORT_SWAP)
    _run_bin({"RELOC_BATCH_DIR": str(swap)})
    shutil.copyfile(REPORT, REPORT_SWAP_SECOND)

    probe = _ART_BASE / "probe_batches"
    if probe.exists():
        shutil.rmtree(probe)
    shutil.copytree(BATCH_DIR, probe)
    src = json.loads((probe / "batch_02.json").read_text(encoding="utf-8"))
    src["batch_id"] = "batch_07"
    src["observed"]["digest"] = _simulate_digest(
        src["batch_id"],
        src["units"],
        src.get("steps", []),
        src.get("mappings", []),
    )
    (probe / "batch_07.json").write_text(
        json.dumps(src, indent=2) + "\n", encoding="utf-8"
    )
    _run_bin({"RELOC_BATCH_DIR": str(probe)})
    shutil.copyfile(REPORT, REPORT_PROBE)

    _run_bin()
    _ARTIFACTS_READY = True


def _report() -> dict:
    prepare_verifier_artifacts()
    return _load_json(REPORT_FIRST)


# --- Essential harness / anti-cheat ---


def test_pinned_inputs_untouched() -> None:
    """Bundled batches, specs, and canon must keep their shipped digests."""
    for name, digest in BUNDLED_DATA_CHECKSUMS.items():
        assert _sha256_file(BATCH_DIR / name) == digest, name
    assert _sha256_file(MAIN_GO) == EXPECTED_MAIN_GO_SHA256
    assert _sha256_file(SPEC) == EXPECTED_SPEC_SHA256
    assert _sha256_file(LAYOUT) == EXPECTED_LAYOUT_SHA256
    assert _sha256_file(CANON) == EXPECTED_CANON_SHA256


def test_stub_removed_and_binary_native() -> None:
    """Stub panic must be gone and reloccheck must be a native ELF >2048 bytes."""
    text = EVAL_GO.read_text(encoding="utf-8")
    assert STUB not in text
    assert BIN.is_file()
    assert BIN.stat().st_size > 2048
    magic = BIN.read_bytes()[:4]
    assert magic in {b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xce"}


def test_summary_and_clean_matrix() -> None:
    """Summary counters and clean-batch matrix must match hardened oracle totals."""
    report = _report()
    summary = report["summary"]
    rows = report["batches"]
    assert summary["batches_analyzed"] == 20
    assert summary["clean_batches"] == 4
    assert summary["failed_batches"] == 16
    assert summary["total_findings"] == sum(len(r["findings"]) for r in rows)
    assert summary["total_findings"] == 27
    assert summary["replay_runs"] == 6
    assert summary["replay_passed"] == 2
    clean = {r["batch_id"] for r in rows if r["relocation_ok"]}
    assert clean == CLEAN_IDS
    for row in rows:
        assert row["relocation_ok"] is EXPECTED_RELOCATION_OK[row["batch_id"]]


def test_structural_fingerprint() -> None:
    """Aggregate structural fingerprint must match the oracle digest."""
    report = _report()
    assert _fingerprint(report, BATCH_DIR) == EXPECTED_REPORT_FINGERPRINT_HEX


def test_deterministic_repeated_runs() -> None:
    """Two consecutive runs on identical inputs must be byte-identical."""
    prepare_verifier_artifacts()
    assert REPORT_FIRST.read_bytes() == REPORT_SECOND.read_bytes()
    assert REPORT_SWAP.read_bytes() == REPORT_SWAP_SECOND.read_bytes()


def test_swap_probe_uses_env_override() -> None:
    """RELOC_BATCH_DIR probes must recompute without baking path-specific goldens."""
    prepare_verifier_artifacts()
    swapped = _load_json(REPORT_SWAP)
    assert swapped["batches"][0]["batch_id"] == "batch_01"
    assert swapped["batches"][0]["relocation_ok"] is True
    assert swapped["batches"][0]["findings"] == []
    probed = _load_json(REPORT_PROBE)
    b07 = next(r for r in probed["batches"] if r["batch_id"] == "batch_07")
    assert b07["relocation_ok"] is True
    assert b07["findings"] == []


def test_canon_flags_required_for_hardness() -> None:
    """Canon must enable the harder policy flags used by EvaluateBatch."""
    text = CANON.read_text(encoding="utf-8")
    for flag in (
        "digest_bind_effective_maps: true",
        "digest_map_bind_order_seq: true",
        "relocator_epoch_must_equal: true",
        "orphan_requires_payload: true",
        "replay_skips_digest: true",
        "detect_dangling_observations: true",
        "collision_top_level_only: true",
        "digest_exclude_cycle_maps: true",
        "replay_ignore_unknown_seqs: true",
        "detect_dangling_nested: true",
    ):
        assert flag in text


# --- Ten harder semantic traps ---


def test_digest_map_bind_ordered_by_seq_not_lex() -> None:
    """Effective map_bind must join by ascending seq, not lexicographic from_prefix."""
    bf = _load_json(BATCH_DIR / "batch_01.json")
    eff = _effective_map_bind(bf["units"], bf["mappings"])
    lex = ",".join(sorted(m["from_prefix"] for m in bf["mappings"]))
    assert eff == "com.foo,com.bar"
    assert lex == "com.bar,com.foo"
    assert eff != lex
    assert bf["observed"]["digest"] == _simulate_digest(
        bf["batch_id"], bf["units"], bf.get("steps", []), bf.get("mappings", [])
    )
    row = next(r for r in _report()["batches"] if r["batch_id"] == "batch_01")
    assert not any(f["kind"] == "rollback_incomplete" for f in row["findings"])


def test_empty_effective_map_bind_still_appends_maps_marker() -> None:
    """Cycle-member exclusion can empty map_bind even when a cycle node is used."""
    bf = _load_json(BATCH_DIR / "batch_05.json")
    assert _effective_map_bind(bf["units"], bf["mappings"]) == ""
    # Without cycle exclusion, used com.a would remain in the bind.
    assert any(m["from_prefix"] == "com.a" for m in bf["mappings"])
    digest = _simulate_digest(
        bf["batch_id"], bf["units"], bf.get("steps", []), bf.get("mappings", [])
    )
    assert bf["observed"]["digest"] == digest
    row = next(r for r in _report()["batches"] if r["batch_id"] == "batch_05")
    assert any(f["kind"] == "relocation_loop" for f in row["findings"])
    stale = {f["subject"] for f in row["findings"] if f["kind"] == "stale_mapping"}
    assert stale == {"com.b"}
    assert "com.a" not in stale


def test_epoch_must_equal_rejects_higher_batch_17() -> None:
    """relocator_epoch_must_equal fails when observed epoch is greater than required."""
    report = _report()
    row = next(r for r in report["batches"] if r["batch_id"] == "batch_17")
    meta = [f for f in row["findings"] if f["kind"] == "metadata_inconsistency"]
    assert len(meta) == 1
    assert meta[0]["expected"] == "7"
    assert meta[0]["observed"] == "8"
    assert meta[0]["rule_id"] == "reloc.metadata_inconsistency"
    assert row["identity_ok"] is False
    assert row["relocation_ok"] is False


def test_orphan_requires_payload_ignores_empty_shell() -> None:
    """Empty shells never orphan; multiple payload entries still yield one orphan."""
    bf = _load_json(BATCH_DIR / "batch_11.json")
    cores = [n for n in bf["observed"]["nested"] if n["unit_path"] == "lib/core.jar"]
    assert len(cores) >= 3
    assert sum(1 for n in cores if n["symbols"] or n["refs"]) >= 2
    assert any(not n["symbols"] and not n["refs"] for n in cores)
    report = _report()
    row = next(r for r in report["batches"] if r["batch_id"] == "batch_11")
    orphans = [f for f in row["findings"] if f["kind"] == "orphan_nested_observation"]
    assert len(orphans) == 1
    assert orphans[0]["subject"] == "lib/core.jar"
    assert orphans[0]["observed"] == "present"


def test_dangling_symbol_and_ref_batch_20() -> None:
    """Unknown observed symbols and ref ids must both emit dangling_observation."""
    report = _report()
    row = next(r for r in report["batches"] if r["batch_id"] == "batch_20")
    dangles = [f for f in row["findings"] if f["kind"] == "dangling_observation"]
    by_subj = {f["subject"]: f for f in dangles}
    assert "com.ghost.Fake" in by_subj
    assert "ref:ghost-r" in by_subj
    assert by_subj["ref:ghost-r"]["observed"] == "com.ghost.Ref"
    assert by_subj["ref:ghost-r"]["rule_id"] == "reloc.dangling_observation"
    assert row["rewrite_ok"] is False


def test_multi_isolation_breach_sorted_subjects_batch_08() -> None:
    """Multiple cross-root merges must emit one isolation_breach per dotted package."""
    report = _report()
    row = next(r for r in report["batches"] if r["batch_id"] == "batch_08")
    hits = [f for f in row["findings"] if f["kind"] == "isolation_breach"]
    assert len(hits) == 2
    subjects = [f["subject"] for f in hits]
    assert subjects == sorted(subjects)
    assert set(subjects) == {"shaded.other", "shaded.shared"}
    assert all("/" not in f["subject"] for f in hits)
    assert all(f["rule_id"] == "reloc.isolation_breach" for f in hits)


def test_replay_empty_schedule_fails_batch_10() -> None:
    """Empty mapping_seq_order is an empty active map set and must fail when observed is relocated."""
    report = _report()
    row = next(r for r in report["batches"] if r["batch_id"] == "batch_10")
    assert row["replay"]["schedules_run"] == 3
    assert row["replay"]["schedules_passed"] == 1
    assert row["replay"]["stable"] is False


def test_replay_skips_digest_batch_13() -> None:
    """Full-batch digest failure must not prevent a clean replay subset from passing."""
    report = _report()
    row = next(r for r in report["batches"] if r["batch_id"] == "batch_13")
    assert any(f["kind"] == "rollback_incomplete" for f in row["findings"])
    assert row["replay"]["schedules_run"] == 1
    assert row["replay"]["schedules_passed"] == 1
    assert row["replay"]["stable"] is False


def test_nested_only_collision_suppressed_batch_04() -> None:
    """collision_top_level_only must keep batch_04 clean despite nested NestCollide twins."""
    bf = _load_json(BATCH_DIR / "batch_04.json")
    nested_fqns = [s["fqn"] for s in bf["units"][0]["nested"][0]["symbols"]]
    assert "com.foo.Twin" in nested_fqns and "com.bar.Twin" in nested_fqns
    report = _report()
    row = next(r for r in report["batches"] if r["batch_id"] == "batch_04")
    assert not any(f["kind"] == "symbol_collision" for f in row["findings"])
    assert row["relocation_ok"] is True
    assert row["findings"] == []


def test_rule_id_and_global_sort_invariants() -> None:
    """Every finding must use reloc.<kind> and global lex sort within each batch."""
    report = _report()
    for row in report["batches"]:
        serialized = [
            (f["kind"], f["subject"], f["expected"], f["observed"]) for f in row["findings"]
        ]
        assert serialized == sorted(serialized)
        for f in row["findings"]:
            assert f["rule_id"] == f"reloc.{f['kind']}"
            assert f["rule_id"] != f["kind"]


def test_digest_excludes_cycle_nodes_even_when_used_batch_05() -> None:
    """digest_exclude_cycle_maps drops cycle from_prefixes from map_bind even if used."""
    bf = _load_json(BATCH_DIR / "batch_05.json")
    names = _collect_names(bf["units"])
    assert any(n.startswith("com.a") for n in names)
    # Naive effective (stale/shadow only) would keep com.a.
    stale_only = [
        m["from_prefix"]
        for m in sorted(bf["mappings"], key=lambda x: x["seq"])
        if any(_matches_prefix(n, m["from_prefix"]) for n in names)
    ]
    assert "com.a" in stale_only
    assert _effective_map_bind(bf["units"], bf["mappings"]) == ""
    assert bf["observed"]["digest"] == _simulate_digest(
        bf["batch_id"], bf["units"], bf.get("steps", []), bf.get("mappings", [])
    )


def test_cascade_gap_empty_shell_parent_has_no_orphan() -> None:
    """Parent with cascade_gap but only empty nested shells must not emit orphan."""
    report = _report()
    row = next(r for r in report["batches"] if r["batch_id"] == "batch_11")
    gaps = {f["subject"] for f in row["findings"] if f["kind"] == "cascade_gap"}
    assert "lib/side.jar" in gaps
    assert "lib/core.jar" in gaps
    orphans = [f for f in row["findings"] if f["kind"] == "orphan_nested_observation"]
    assert [f["subject"] for f in orphans] == ["lib/core.jar"]


def test_duplicate_payload_entries_single_orphan_batch_11() -> None:
    """Two payload nested entries for the same parent still produce exactly one orphan."""
    bf = _load_json(BATCH_DIR / "batch_11.json")
    payloads = [
        n
        for n in bf["observed"]["nested"]
        if n["unit_path"] == "lib/core.jar" and (n["symbols"] or n["refs"])
    ]
    assert len(payloads) >= 2
    report = _report()
    row = next(r for r in report["batches"] if r["batch_id"] == "batch_11")
    orphans = [f for f in row["findings"] if f["kind"] == "orphan_nested_observation"]
    assert len(orphans) == 1


def test_dangling_nested_observation_batch_11() -> None:
    """Unknown nested observed originals use parent_path#original subjects."""
    report = _report()
    row = next(r for r in report["batches"] if r["batch_id"] == "batch_11")
    hits = [
        f
        for f in row["findings"]
        if f["kind"] == "dangling_observation" and "#" in f["subject"]
    ]
    assert len(hits) == 1
    assert hits[0]["subject"] == "lib/core.jar#com.ghost.Nested"
    assert hits[0]["expected"] == ""
    assert hits[0]["observed"] == "com.ghost.Nested"
    assert hits[0]["rule_id"] == "reloc.dangling_observation"


def test_replay_ignores_unknown_seq_batch_10() -> None:
    """Unknown mapping seq values must be ignored for subset selection and pass counts."""
    bf = _load_json(BATCH_DIR / "batch_10.json")
    assert any(99 in sch["mapping_seq_order"] for sch in bf["replay"]["schedules"])
    report = _report()
    row = next(r for r in report["batches"] if r["batch_id"] == "batch_10")
    assert row["replay"]["schedules_run"] == 3
    assert row["replay"]["schedules_passed"] == 1
    assert row["replay"]["stable"] is False
