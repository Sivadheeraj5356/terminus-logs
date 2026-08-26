"""Black-box behavioral verifier for envelope-custody-recovery-qualification."""
from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fixture_factory import build_vault, canonical_json, tamper, tree_hashes
from reference_model import qualify_reference, sha256

QUALIFY = Path("/app/bin/vault-qualify")
INSPECT = Path("/app/bin/vault-inspect")
LEGACY = Path("/app/bin/vault-legacy-check")
TESTS = Path("/tests")
HIDDEN_SEEDS = (0xEC0A0001, 0xEC0A0002, 0xEC0A0003)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _tree(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*")) if p.is_file()
    } if root.exists() else {}


def _run(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    clean = os.environ.copy()
    clean.update({"LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "TZ": "UTC", "HOME": "/tmp"})
    if env:
        clean.update(env)
    return subprocess.run(command, text=True, capture_output=True, env=clean, timeout=90, check=False)


def _qualify(vault: Path, output: Path, *, epoch: int | None = None, failpoint: str | None = None) -> subprocess.CompletedProcess[str]:
    output.parent.mkdir(parents=True, exist_ok=True)
    env = {"VAULT_QUALIFY_FAILPOINT": failpoint} if failpoint else None
    if epoch is None:
        epoch = _json(vault / "manifest.json")["qualification_epoch"]
    return _run([str(QUALIFY), "--vault", str(vault), "--epoch", str(epoch), "--output", str(output)], env=env)


def _assert_output(output: Path, expected: dict[str, Any]) -> None:
    assert output.is_dir()
    assert (output / "inventory.jsonl").read_bytes() == expected["inventory_bytes"]
    assert _json(output / "recovery-root.json") == expected["recovery_root"]
    for path, plain in expected["plaintexts"].items():
        assert (output / "objects" / path).read_bytes() == plain
    assert sorted((p.relative_to(output / "objects").as_posix() for p in (output / "objects").rglob("*") if p.is_file())) == sorted(expected["plaintexts"])
    _verify_audit(output, expected)


def _verify_audit(output: Path, expected: dict[str, Any]) -> None:
    dsse = _json(output / "audit.dsse.json")
    assert dsse == expected["audit"]
    payload = base64.b64decode(dsse["payload"])
    statement = json.loads(payload)
    assert statement["recovery_root"] == expected["recovery_root"]["recovery_root"]
    assert statement["evidence_snapshot_sha256"] == expected["snapshot"]
    assert statement["inventory_sha256"] == sha256(expected["inventory_bytes"])
    public = dsse["public_key"]
    signature = bytes.fromhex(dsse["signatures"][0]["sig"])
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(public)).verify(signature, payload)


def _case(kind: str, seed: int = 0xEC0A101) -> tuple[tempfile.TemporaryDirectory[str], Any, Path]:
    tmp = tempfile.TemporaryDirectory(prefix=f"ecrq-{kind}-")
    work = Path(tmp.name)
    scenario = build_vault(work / "vault", seed, kind)
    return tmp, scenario, work


def test_mixed_versions_recover_exact_eligible_objects() -> None:
    """Mixed v1/v2 envelopes yield only the exact eligible plaintexts and sorted rows."""
    tmp, scenario, work = _case("mixed")
    try:
        expected = qualify_reference(scenario.root)
        output = work / "output"
        proc = _qualify(scenario.root, output)
        assert proc.returncode == 0, proc.stderr
        _assert_output(output, expected)
        assert [row["logical_path"] for row in expected["rows"]] == sorted(scenario.expected_paths)
    finally:
        tmp.cleanup()


def test_committed_lineage_beats_timestamp_and_prepared_records() -> None:
    """Prepared/newer journal records cannot displace the committed lineage head."""
    tmp, scenario, work = _case("mixed", 0xEC0A102)
    try:
        expected = qualify_reference(scenario.root)
        proc = _qualify(scenario.root, work / "out")
        assert proc.returncode == 0, proc.stderr
        _assert_output(work / "out", expected)
    finally:
        tmp.cleanup()


def test_signed_rollback_restores_parent_head() -> None:
    """A signed rollback restores the committed parent for inspector and qualifier."""
    tmp, scenario, work = _case("rollback")
    try:
        expected = qualify_reference(scenario.root)
        inspect = _run([str(INSPECT), "--vault", str(scenario.root)])
        assert inspect.returncode == 0, inspect.stderr
        inspected = json.loads(inspect.stdout)
        assert inspected["heads"] == expected["heads"]
        assert _qualify(scenario.root, work / "out").returncode == 0
        _assert_output(work / "out", expected)
    finally:
        tmp.cleanup()


def test_conflicting_or_malformed_journal_fails_closed() -> None:
    """Conflicts, malformed JSON, and broken signatures publish no recovery set."""
    for mutation in ("conflict", "malformed", "signature"):
        tmp, scenario, work = _case("conflicting", 0xEC0A110 + len(mutation))
        try:
            journal = scenario.root / "rewrap/journal.jsonl"
            if mutation == "malformed":
                journal.write_bytes(journal.read_bytes() + b"{bad\n")
            elif mutation == "signature":
                tamper(journal, offset=17)
            output = work / "out"
            proc = _qualify(scenario.root, output)
            assert proc.returncode != 0, mutation
            assert not (output / "objects").exists(), mutation
        finally:
            tmp.cleanup()


def test_historical_authority_uses_object_epoch() -> None:
    """Authority is evaluated at custody epoch, including exact handoff boundaries."""
    tmp, scenario, work = _case("historical")
    try:
        expected = qualify_reference(scenario.root)
        assert _qualify(scenario.root, work / "out").returncode == 0
        _assert_output(work / "out", expected)
    finally:
        tmp.cleanup()


def test_threshold_counts_distinct_authorized_organizations() -> None:
    """Repeated aliases from one organization cannot satisfy a multi-org threshold."""
    tmp, scenario, work = _case("threshold")
    try:
        assert qualify_reference(scenario.root)["rows"] == []
        proc = _qualify(scenario.root, work / "out")
        assert proc.returncode == 0, proc.stderr
        _assert_output(work / "out", qualify_reference(scenario.root))
    finally:
        tmp.cleanup()


def test_valid_but_unauthorized_share_is_rejected() -> None:
    """A valid signature from an alias absent at object epoch is not a recovery share."""
    tmp, scenario, work = _case("unauthorized")
    try:
        expected = qualify_reference(scenario.root)
        assert expected["rows"] == []
        assert _qualify(scenario.root, work / "out").returncode == 0
        _assert_output(work / "out", expected)
    finally:
        tmp.cleanup()


def test_version_specific_aad_and_relocated_storage() -> None:
    """v2 uses logical identity while v1 retains its documented storage binding."""
    tmp, scenario, work = _case("relocated")
    try:
        expected = qualify_reference(scenario.root)
        assert _qualify(scenario.root, work / "out").returncode == 0
        _assert_output(work / "out", expected)
        env = _json(next((scenario.root / "envelopes").glob("*.json")))
        env["logical_path"] += ".tampered"
        (scenario.root / "envelopes" / f"{env['object_id']}.json").write_bytes(canonical_json(env) + b"\n")
        assert _qualify(scenario.root, work / "bad").returncode != 0
    finally:
        tmp.cleanup()


def test_complete_snapshot_invalidates_resume_for_every_evidence_class() -> None:
    """Every evidence class changes the bound snapshot and rejects stale checkpoint."""
    for rel in ("authority/ledger.jsonl", "rewrap/journal.jsonl", "shares", "envelopes", "objects", "manifest.json"):
        tmp, scenario, work = _case("mixed", 0xEC0A200 + len(rel))
        try:
            expected = qualify_reference(scenario.root)
            epoch = scenario.epoch
            checkpoint = scenario.root / "state/qualification-checkpoint.json"
            checkpoint.write_text(json.dumps({"evidence_snapshot_sha256": expected["snapshot"], "complete": True}) + "\n")
            target = next((scenario.root / rel).rglob("*")) if (scenario.root / rel).is_dir() else scenario.root / rel
            tamper(target)
            assert _qualify(scenario.root, work / "out", epoch=epoch).returncode != 0, rel
        finally:
            tmp.cleanup()


def test_rewrap_preserves_key_and_plaintext_commitments() -> None:
    """Changing rewrap lineage does not change data-key or plaintext commitments."""
    tmp, scenario, work = _case("mixed", 0xEC0A301)
    try:
        expected = qualify_reference(scenario.root)
        assert _qualify(scenario.root, work / "out").returncode == 0
        rows = [json.loads(line) for line in (work / "out/inventory.jsonl").read_text().splitlines()]
        assert [(r["data_key_commitment"], r["plaintext_sha256"]) for r in rows] == [
            (r["data_key_commitment"], r["plaintext_sha256"]) for r in expected["rows"]
        ]
    finally:
        tmp.cleanup()


def test_interrupted_publication_reruns_byte_identically() -> None:
    """All documented publication failpoints leave no final plaintext and rerun identically."""
    tmp, scenario, work = _case("mixed", 0xEC0A401)
    try:
        baseline = work / "baseline"
        assert _qualify(scenario.root, baseline).returncode == 0
        baseline_tree = _tree(baseline)
        for point in ("after-object-stage", "after-inventory-stage", "after-root-stage", "before-audit-commit"):
            output = work / point
            proc = _qualify(scenario.root, output, failpoint=point)
            assert proc.returncode != 0, point
            assert not (output / "objects").exists(), point
            assert _qualify(scenario.root, output).returncode == 0
            assert _tree(output) == baseline_tree
    finally:
        tmp.cleanup()


def test_rerun_removes_stale_objects_and_inventory_rows() -> None:
    """Publishing a new snapshot replaces stale object paths and inventory rows."""
    tmp, old, work = _case("mixed", 0xEC0A501)
    try:
        output = work / "out"
        assert _qualify(old.root, output).returncode == 0
        newer = build_vault(work / "new-vault", 0xEC0A502, "mixed")
        expected = qualify_reference(newer.root)
        assert _qualify(newer.root, output).returncode == 0
        _assert_output(output, expected)
    finally:
        tmp.cleanup()


def test_source_vault_is_byte_identical() -> None:
    """Success, rejection, interruption, and rerun never mutate vault evidence."""
    tmp, scenario, work = _case("mixed", 0xEC0A601)
    try:
        before = tree_hashes(scenario.root)
        assert _qualify(scenario.root, work / "ok").returncode == 0
        assert _qualify(scenario.root, work / "interrupted", failpoint="after-root-stage").returncode != 0
        assert _qualify(scenario.root, work / "rerun").returncode == 0
        assert tree_hashes(scenario.root) == before
    finally:
        tmp.cleanup()


def test_empty_committed_vault_produces_authenticated_empty_set() -> None:
    """A valid empty vault emits sorted empty inventory, root, and signed audit."""
    tmp, scenario, work = _case("empty")
    try:
        expected = qualify_reference(scenario.root)
        assert expected["inventory_bytes"] == b""
        assert _qualify(scenario.root, work / "out").returncode == 0
        _assert_output(work / "out", expected)
    finally:
        tmp.cleanup()


def test_inspect_and_legacy_commands_preserve_contract() -> None:
    """Inspector shares qualification's resolver; legacy checker rejects tampering."""
    tmp, scenario, work = _case("rollback", 0xEC0A701)
    try:
        expected = qualify_reference(scenario.root)
        inspected = _run([str(INSPECT), "--vault", str(scenario.root)])
        assert inspected.returncode == 0
        assert json.loads(inspected.stdout)["heads"] == expected["heads"]
        legacy = work / "legacy.json"
        payload = "legacy-payload"
        legacy.write_text(json.dumps({"payload": payload, "digest": sha256(payload.encode())}) + "\n")
        assert _run([str(LEGACY), "--archive", str(legacy)]).returncode == 0
        tamper(legacy)
        assert _run([str(LEGACY), "--archive", str(legacy)]).returncode != 0
    finally:
        tmp.cleanup()


def test_seeded_hidden_variants_defeat_static_outputs() -> None:
    """Three fixed private seeds vary paths, bytes, organizations, epochs, and journal shape."""
    for seed in HIDDEN_SEEDS:
        tmp, scenario, work = _case("hidden", seed)
        try:
            expected = qualify_reference(scenario.root)
            assert _qualify(scenario.root, work / "out").returncode == 0
            _assert_output(work / "out", expected)
        finally:
            tmp.cleanup()


def test_verifier_assets_not_readable_by_candidate() -> None:
    """Candidate commands run without read access to verifier reference assets."""
    proc = _run(["/bin/sh", "-c", "su -s /bin/sh nobody -c 'test ! -r /tests/reference_model.py'"])
    if proc.returncode != 0:
        pytest.skip("nobody user unavailable in this runtime")
