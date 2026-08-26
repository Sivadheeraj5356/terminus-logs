"""Verifier for the encrypted backup trustworthiness assessor."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml

REPORT = Path("/app/verdicts/backup_trust_report.json")
_ART = Path(os.environ.get("EBTA_VERIFIER_ARTIFACT_DIR", "/tmp/ebta-verifier-artifacts"))
REPORT_FIRST = _ART / "report_first.json"
REPORT_SECOND = _ART / "report_second.json"
REPORT_SWAP = _ART / "report_swap.json"
REPORT_PROBE_COLD = _ART / "report_probe_cold.json"
REPORT_PROBE_QUORUM = _ART / "report_probe_quorum.json"
BIN = Path("/app/bin/ebta")
MAIN_GO = Path("/app/bootstrap/ebta/main.go")
TRUST_GO = Path("/app/audit/trust.go")
ARCHIVE_GO = Path("/app/vault/archive.go")
CONTRACT = Path("/app/contracts/TRUST_REPORT.md")
FORMAT = Path("/app/contracts/ARCHIVE_FORMAT.md")
RULES = Path("/app/rules/escrow_matrix.yaml")
ARCHIVES = Path("/app/archives")

STUB_ASSESS = "audit.AssessArchive not implemented"
STUB_RESOLVE = "vault.ResolveArchivesDir not implemented"
STUB_LOAD = "vault.LoadArchive not implemented"

EXPECTED_MAIN_SHA256 = "97919dd4a732e3708ddb6a9c62b69da800b3dc714ce311f50e99a260862d8a68"
EXPECTED_CONTRACT_SHA256 = "29f8fb4390576b5f498b121eeb35e1cc9cb103d415cfe45c86b8edeaee259c93"
EXPECTED_FORMAT_SHA256 = "f2cd906e8110da3d26c6ad07bf5a31c0d1eb8d4f6f935ce52df1aea3f4a8b641"
EXPECTED_RULES_SHA256 = "c9c6882834578b97e462c58a459de28e161c1794a550a92acd8a53fb3150a662"
EXPECTED_REPORT_FINGERPRINT = (
    "d4c46cc0fa65370fabc82da93977f6d25a6146d140f45a6e2d4d32ea778b6035"
)

BUNDLED_ARCHIVE_CHECKSUMS: dict[str, str] = {
    "archive_01.json": "7946dc9bfe093c2c7dd7cd5cdfb787b22e33f9cc2c57e4b1e7934149ecca7923",
    "archive_02.json": "6357b0d70432e7e2ea1938b59629d12576fde4f35af16470ec8532c74ebfbb5d",
    "archive_03.json": "94144efcc297b3f4da5f6e8390422d3ed62cd4a23883d02549a581d6bdf84b58",
    "archive_04.json": "5f407cd6dde0be2c630e650306e17976454df8bfde28b5a823d36bf9e8dd101c",
    "archive_05.json": "70e7fdfd8e833404b1b1bae17e615cadea260f1eb787233ca477866bb915c0f1",
    "archive_06.json": "bcb5a98c221a98c8c164a1e591a0ad898550363199908e1b38e6407a39e6aa9e",
    "archive_07.json": "ebf97b98ffe0cd944d3a322eedf84ee87274a148c25b1694f70c194e6d470a89",
    "archive_08.json": "d9e1c62994d800789bbb153c637bdd445b9f3d059ffe07076d8ad951c154c232",
    "archive_09.json": "707354c2eddf5a9bc6b8581f9e9456baf511a2773ab3138e48df65c64fa710cc",
    "archive_10.json": "e7abbb7814ce3535659788fa653658400523bae591f647ab0845dabb6d35fc72",
    "archive_11.json": "03653f35c3ec52941e28292a9ce2686b9da4d4ed166f137ffc8bccd8f534e649",
    "archive_12.json": "d28743acd943f261b42376a22799beb7e91bffca5bd63dd8b9509e84936fa557",
    "archive_13.json": "3288e5679e17bb08b48e73629532a67532233ba254b4ed692e4366afa10b02d2",
    "archive_14.json": "ddd5252ea7538bb8cbb14921009d888992fb460fdb48ebb149ede2fa50b91de4",
    "archive_15.json": "c240ef18c80fa7e266db9d220ab9c30100f83c3f68f2c3a825af1bbb73364d55",
    "archive_16.json": "31fcfff71171de78891f911b2b714968f9361afad9f3715f083a8c2b0bbd6636",
    "archive_17.json": "b40fae207856e6db2b9b74bf5906777b6d1b98428d7ae970db89e636e0dcf021",
    "archive_18.json": "9ccffcccf84448a6586c17cb1fda26d36546e6d7e56f222f666f1fb4f5e33054",
    "archive_19.json": "bb503b9209ed03c636e799c5df768e93f2ad0e61111eaa1a19040983e5551370",
    "archive_20.json": "dc37f65bb35dadb39e601d41cee363d9cfe8cf08038c698c90038d198a3bf8d3",
}

EXPECTED_SCORES: dict[str, int] = {
    "archive_01": 0,
    "archive_02": 15,
    "archive_03": 12,
    "archive_04": 18,
    "archive_05": 10,
    "archive_06": 14,
    "archive_07": 16,
    "archive_08": 23,
    "archive_09": 13,
    "archive_10": 20,
    "archive_11": 0,
    "archive_12": 9,
    "archive_13": 0,
    "archive_14": 0,
    "archive_15": 15,
    "archive_16": 16,
    "archive_17": 38,
    "archive_18": 74,
    "archive_19": 0,
    "archive_20": 0,
}

EXPECTED_TIERS: dict[str, str] = {
    "archive_01": "low",
    "archive_02": "low",
    "archive_03": "low",
    "archive_04": "low",
    "archive_05": "low",
    "archive_06": "low",
    "archive_07": "low",
    "archive_08": "medium",
    "archive_09": "low",
    "archive_10": "medium",
    "archive_11": "low",
    "archive_12": "low",
    "archive_13": "low",
    "archive_14": "low",
    "archive_15": "low",
    "archive_16": "low",
    "archive_17": "medium",
    "archive_18": "high",
    "archive_19": "low",
    "archive_20": "low",
}

SUMMARY_KEYS = [
    "archives_analyzed",
    "archives_at_risk",
    "clean_archives",
    "total_findings",
    "critical_archives",
    "trustworthiness_mean",
    "archives_abs_path",
]
ARCHIVE_KEYS = [
    "archive_id",
    "trust_tier",
    "risk_score",
    "trustworthiness",
    "findings",
    "coverage_gaps",
    "unauthorized_mutations",
    "escrow_breaks",
    "recovery_weaknesses",
    "retention_tampers",
    "recovery_guarantee_fails",
    "stale_dependencies",
    "restore_forgeries",
    "silent_corruptions",
    "resilience_fails",
    "evidence",
]
FINDING_KEYS = ["kind", "subject", "detail"]
EXPECTED_IDS = [f"archive_{i:02d}" for i in range(1, 21)]

_ARTIFACTS_READY = False


def pytest_configure(_config):
    """Prepare captured reports before collection finishes running tests."""
    prepare_verifier_artifacts()


def prepare_verifier_artifacts() -> None:
    """Build ebta and capture default/swap/probe reports before pytest."""
    global _ARTIFACTS_READY
    if _ARTIFACTS_READY:
        return
    _ART.mkdir(parents=True, exist_ok=True)

    subprocess.run(["make", "build"], cwd="/app", check=False, timeout=180)

    def _run(env: dict[str, str] | None = None) -> bool:
        if not BIN.exists():
            return False
        result = subprocess.run(
            [str(BIN)],
            cwd="/app",
            env={**os.environ, **(env or {})},
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        return result.returncode == 0

    def _copy(dest: Path) -> None:
        if REPORT.exists():
            shutil.copy2(REPORT, dest)

    if _run():
        _copy(REPORT_FIRST)
    if _run():
        _copy(REPORT_SECOND)

    swap_root = Path("/tmp/ebta-verify-archives")
    if swap_root.exists():
        shutil.rmtree(swap_root)
    shutil.copytree(ARCHIVES, swap_root)
    src = json.loads((ARCHIVES / "archive_11.json").read_text(encoding="utf-8"))
    src["archive_id"] = "archive_02"
    (swap_root / "archive_02.json").write_text(
        json.dumps(src, indent=2) + "\n", encoding="utf-8"
    )
    decoy = {
        "archive_id": "archive_99",
        "objects": [
            {
                "id": "OZ",
                "key_id": "KZ",
                "cipher": "AES-256-GCM",
                "content_digest": "z",
                "declared_digest": "z",
            }
        ],
        "keys": [
            {
                "id": "KZ",
                "role": "data",
                "algorithm": "AES-256-GCM",
                "state": "active",
                "rewrap_needed": False,
                "rewrap_token": "",
                "threshold": 2,
                "shares": [],
            }
        ],
        "escrow": {"registered_fingerprints": {}},
        "manifest": {"signed_digests": ["z"]},
        "recovery": {
            "path_count": 2,
            "requires_online_hsm": False,
            "offline_cold_share": False,
            "geographic_split": False,
        },
        "retention": {
            "declared_days": 90,
            "enforced_days": 90,
            "immutable": True,
            "legal_hold": False,
        },
        "restore": {"chain_ok": True, "signer": "vault-root-a", "nonce_reuse": False},
        "shards": [{"id": "P1", "declared_crc": "c1", "payload_crc": "c1"}],
        "expected_shards": 1,
        "adversary_tests": [],
    }
    (swap_root / "archive_99.json").write_text(
        json.dumps(decoy, indent=2) + "\n", encoding="utf-8"
    )
    if REPORT.exists():
        REPORT.unlink()
    if _run({"EBTA_ARCHIVES_DIR": str(swap_root)}):
        _copy(REPORT_SWAP)

    cold_root = Path("/tmp/ebta-probe-cold")
    if cold_root.exists():
        shutil.rmtree(cold_root)
    shutil.copytree(ARCHIVES, cold_root)
    probe = json.loads((ARCHIVES / "archive_05.json").read_text(encoding="utf-8"))
    probe["recovery"]["offline_cold_share"] = True
    (cold_root / "archive_05.json").write_text(
        json.dumps(probe, indent=2) + "\n", encoding="utf-8"
    )
    if REPORT.exists():
        REPORT.unlink()
    if _run({"EBTA_ARCHIVES_DIR": str(cold_root)}):
        _copy(REPORT_PROBE_COLD)

    quorum_root = Path("/tmp/ebta-probe-quorum")
    if quorum_root.exists():
        shutil.rmtree(quorum_root)
    shutil.copytree(ARCHIVES, quorum_root)
    qb = json.loads((ARCHIVES / "archive_04.json").read_text(encoding="utf-8"))
    for share in qb["keys"][0]["shares"]:
        share["revoked"] = False
    (quorum_root / "archive_04.json").write_text(
        json.dumps(qb, indent=2) + "\n", encoding="utf-8"
    )
    if REPORT.exists():
        REPORT.unlink()
    if _run({"EBTA_ARCHIVES_DIR": str(quorum_root)}):
        _copy(REPORT_PROBE_QUORUM)

    if REPORT.exists():
        REPORT.unlink()
    _run()
    _ARTIFACTS_READY = True


def _ensure_artifacts() -> None:
    if not _ARTIFACTS_READY and not REPORT_FIRST.exists():
        prepare_verifier_artifacts()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _by_id(report: dict) -> dict[str, dict]:
    return {a["archive_id"]: a for a in report["archives"]}


def _fingerprint(report: dict) -> str:
    parts: list[str] = []
    s = report["summary"]
    parts.append(
        "|".join(
            str(s[k])
            for k in [
                "archives_analyzed",
                "archives_at_risk",
                "clean_archives",
                "total_findings",
                "critical_archives",
                "trustworthiness_mean",
            ]
        )
    )
    for t in report["archives"]:
        kinds = ",".join(f["kind"] for f in t["findings"])
        parts.append(
            f"{t['archive_id']}|{t['risk_score']}|{t['trust_tier']}|{len(t['findings'])}|{kinds}"
        )
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def test_verifier_artifacts_prepared():
    """Captured default reports must exist after verifier harness preparation."""
    _ensure_artifacts()
    assert REPORT_FIRST.exists() and REPORT.exists()


def test_bundled_archive_layout_and_checksums():
    """Exactly archive_01..archive_20 under /app/archives with matching ids and SHA256."""
    paths = sorted(ARCHIVES.glob("archive_*.json"), key=lambda p: p.name)
    assert [p.stem for p in paths] == EXPECTED_IDS
    assert sorted(ARCHIVES.glob("*.json"), key=lambda p: p.name) == paths
    for name, want in BUNDLED_ARCHIVE_CHECKSUMS.items():
        digest = hashlib.sha256((ARCHIVES / name).read_bytes()).hexdigest()
        assert digest == want, name


def test_contracts_and_rules_unchanged():
    """Contracts and rules files must remain the shipped contracts."""
    assert hashlib.sha256(CONTRACT.read_bytes()).hexdigest() == EXPECTED_CONTRACT_SHA256
    assert hashlib.sha256(FORMAT.read_bytes()).hexdigest() == EXPECTED_FORMAT_SHA256
    assert hashlib.sha256(RULES.read_bytes()).hexdigest() == EXPECTED_RULES_SHA256


def test_main_entrypoint_unchanged():
    """Leave bootstrap package alone; main.go SHA256 must match shipped digest."""
    assert hashlib.sha256(MAIN_GO.read_bytes()).hexdigest() == EXPECTED_MAIN_SHA256


def test_make_build_produces_ebta_binary():
    """Executable /app/bin/ebta must exist and exceed 2048 bytes."""
    result = subprocess.run(
        ["make", "build"], cwd="/app", capture_output=True, text=True, timeout=180, check=False
    )
    assert result.returncode == 0, result.stderr
    assert BIN.exists() and BIN.stat().st_size > 2048 and os.access(BIN, os.X_OK)


def test_stubs_removed_from_vault_and_audit():
    """Vault and audit stubs must be replaced with real implementations."""
    trust = TRUST_GO.read_text(encoding="utf-8")
    archive = ARCHIVE_GO.read_text(encoding="utf-8")
    assert STUB_ASSESS not in trust
    assert STUB_RESOLVE not in archive
    assert STUB_LOAD not in archive


def test_no_embedded_oracle_fingerprints_in_audit_package():
    """Anti-cheat: trust.go must not embed verifier checksums or report fingerprint."""
    text = TRUST_GO.read_text(encoding="utf-8")
    assert EXPECTED_REPORT_FINGERPRINT not in text
    for digest in BUNDLED_ARCHIVE_CHECKSUMS.values():
        assert digest not in text
    assert "EBTA_VERIFIER_ARTIFACT_DIR" not in text
    assert "/tests/" not in text


def test_report_is_strict_utf8_with_trailing_newline():
    """Report is UTF-8 JSON larger than 100 bytes with trailing newline."""
    _ensure_artifacts()
    raw = REPORT.read_bytes()
    assert len(raw) > 100 and raw.endswith(b"\n")
    raw.decode("utf-8")
    json.loads(raw)


def test_report_key_order_and_archive_ids():
    """Normative key order and archive_01..archive_20 row order."""
    report = _load(REPORT)
    assert list(report.keys()) == ["summary", "archives"]
    assert list(report["summary"].keys()) == SUMMARY_KEYS
    assert [a["archive_id"] for a in report["archives"]] == EXPECTED_IDS
    for row in report["archives"]:
        assert list(row.keys()) == ARCHIVE_KEYS
        for finding in row["findings"]:
            assert list(finding.keys()) == FINDING_KEYS


def test_summary_reconciles_with_archive_rows():
    """Summary counters must reconcile with per-archive rows."""
    report = _load(REPORT)
    s = report["summary"]
    rows = report["archives"]
    assert s["archives_analyzed"] == 20 == len(rows)
    at_risk = sum(1 for r in rows if r["risk_score"] > 0)
    clean = sum(1 for r in rows if r["risk_score"] == 0)
    assert s["archives_at_risk"] == at_risk == 14
    assert s["clean_archives"] == clean == 6
    assert s["total_findings"] == sum(len(r["findings"]) for r in rows) == 21
    assert s["critical_archives"] == sum(1 for r in rows if r["trust_tier"] == "critical")
    assert s["trustworthiness_mean"] == 85
    assert s["archives_abs_path"] == "/app/archives"


def test_bundled_scores_and_tiers():
    """Bundled archive risk scores and trust tiers must match oracle expectations."""
    by_id = _by_id(_load(REPORT))
    for aid, score in EXPECTED_SCORES.items():
        assert by_id[aid]["risk_score"] == score, aid
        assert by_id[aid]["trust_tier"] == EXPECTED_TIERS[aid], aid
        assert by_id[aid]["trustworthiness"] == 100 - score


def test_empty_collections_are_arrays_not_null():
    """Clean rows must emit empty arrays, never null, for typed finding lists."""
    raw = REPORT.read_text(encoding="utf-8")
    assert ": null" not in raw
    for row in _load(REPORT)["archives"]:
        if row["risk_score"] == 0:
            assert row["findings"] == []
            assert row["coverage_gaps"] == []
            assert row["unauthorized_mutations"] == []


def test_report_fingerprint_matches_bundled_inputs():
    """Structural fingerprint of the bundled report must match the oracle digest."""
    assert _fingerprint(_load(REPORT)) == EXPECTED_REPORT_FINGERPRINT


def test_report_byte_identical_across_runs():
    """Two consecutive runs on the same tree must be byte-identical."""
    assert REPORT_FIRST.read_bytes() == REPORT_SECOND.read_bytes()


def test_swap_fixture_ignores_extra_archive_and_changes_score():
    """EBTA_ARCHIVES_DIR swap: ignore archive_99 and recompute archive_02 from archive_11."""
    assert REPORT_SWAP.exists()
    swapped = _load(REPORT_SWAP)
    ids = [a["archive_id"] for a in swapped["archives"]]
    assert ids == EXPECTED_IDS
    assert "archive_99" not in ids
    by_id = _by_id(swapped)
    assert by_id["archive_02"]["risk_score"] == 0
    assert swapped["summary"]["archives_at_risk"] < 14


def test_cold_share_suppresses_recovery_weakness():
    """offline_cold_share must suppress recovery_weakness on an otherwise weak archive_05."""
    assert REPORT_PROBE_COLD.exists()
    row = _by_id(_load(REPORT_PROBE_COLD))["archive_05"]
    assert row["risk_score"] == 0
    assert row["recovery_weaknesses"] == []
    assert all(f["kind"] != "recovery_weakness" for f in row["findings"])


def test_unrevoking_shares_clears_escrow_break():
    """Revoked escrow shares must not count; un-revoking restores quorum on archive_04."""
    assert REPORT_PROBE_QUORUM.exists()
    row = _by_id(_load(REPORT_PROBE_QUORUM))["archive_04"]
    assert row["risk_score"] == 0
    assert row["escrow_breaks"] == []


def test_stale_cipher_emits_coverage_and_stale_findings():
    """AES-128-CBC must emit both coverage_gap and stale_dependency on archive_08."""
    row = _by_id(_load(REPORT))["archive_08"]
    kinds = [f["kind"] for f in row["findings"]]
    assert kinds == ["coverage_gap", "stale_dependency"]
    assert row["risk_score"] == 23


def test_legal_hold_suppresses_retention_tamper():
    """legal_hold with enforced >= declared must suppress mutable retention on archive_14."""
    row = _by_id(_load(REPORT))["archive_14"]
    assert row["risk_score"] == 0
    assert row["retention_tampers"] == []


def test_geographic_split_suppresses_recovery_weakness():
    """geographic_split must suppress single-path online HSM weakness on archive_19."""
    row = _by_id(_load(REPORT))["archive_19"]
    assert row["risk_score"] == 0
    assert row["recovery_weaknesses"] == []


def test_nonce_reuse_forces_restore_forgery_even_with_trusted_signer():
    """nonce_reuse must force restore_forgery on archive_17 despite trusted signer."""
    row = _by_id(_load(REPORT))["archive_17"]
    kinds = {f["kind"] for f in row["findings"]}
    assert "restore_forgery" in kinds
    assert "retention_tamper" in kinds
    assert "stale_dependency" in kinds
    assert row["risk_score"] == 38


def test_rules_yaml_weights_drive_scoring():
    """escrow_matrix.yaml scoring weights must explain archive_10 and archive_12 scores."""
    rules = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    by_id = _by_id(_load(REPORT))
    assert by_id["archive_10"]["risk_score"] == rules["scoring"]["silent_corruption"]
    assert by_id["archive_12"]["risk_score"] == rules["scoring"]["resilience_fail"]
    assert rules["escrow"]["min_quorum"] == 2
    assert rules["retention"]["requires_immutable"] is True


def test_archive_18_compound_findings_sorted():
    """archive_18 must emit five sorted finding kinds totaling risk 74."""
    row = _by_id(_load(REPORT))["archive_18"]
    kinds = [f["kind"] for f in row["findings"]]
    assert kinds == sorted(kinds)
    assert set(kinds) == {
        "coverage_gap",
        "escrow_break",
        "resilience_fail",
        "silent_corruption",
        "unauthorized_mutation",
    }
    assert row["risk_score"] == 74
    assert row["trust_tier"] == "high"
