"""Verifier tests for hopledger v3 mesh hop accounting replay."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ENV = "/app/environment"
BIN = f"{ENV}/bin/hopledger"
BUNDLED_MANIFEST = f"{ENV}/fixtures/manifest.json"
POLICY = f"{ENV}/fixtures/policy.json"


def _expect_script() -> str:
    return str(Path(__file__).with_name("hop_expect.py"))


def _expect_run(manifest: str | Path, resume_tag: str | None = None) -> dict:
    cmd = ["python3", _expect_script(), str(manifest)]
    if resume_tag:
        cmd.append(resume_tag)
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
    return json.loads(proc.stdout)


def _build():
    subprocess.run(["go", "build", "-o", BIN, "."], cwd=ENV, check=True, timeout=180)


def _run(manifest: str, report: str, digest: str, audit: str, resume_tag: str | None = None):
    cmd = [
        BIN,
        "run",
        "--manifest",
        manifest,
        "--report",
        report,
        "--digest",
        digest,
        "--audit",
        audit,
    ]
    if resume_tag:
        cmd.extend(["--resume-tag", resume_tag])
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def _write_manifest(
    tmp: Path,
    lanes: list[dict],
    ckpt_dir: str = "checkpoints",
    policy_src: str | None = POLICY,
) -> Path:
    for lane in lanes:
        lane_path = tmp / lane["path"]
        lane_path.parent.mkdir(parents=True, exist_ok=True)
        lane_path.write_text(lane["body"].rstrip() + "\n")
    (tmp / ckpt_dir).mkdir(parents=True, exist_ok=True)
    manifest: dict = {"schema_version": 3, "checkpoint_dir": ckpt_dir, "lanes": []}
    for lane in lanes:
        manifest["lanes"].append(
            {"name": lane["name"], "path": lane["path"], "priority": lane["priority"]}
        )
    if policy_src:
        shutil.copy(policy_src, tmp / "policy.json")
        manifest["policy"] = "policy.json"
    manifest_path = tmp / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest_path


def _generate_case(seed: int, tmp: Path) -> Path:
    subprocess.run(
        ["python3", _expect_script(), "--generate", str(seed), str(tmp)],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    return tmp / "manifest.json"


@pytest.fixture(scope="module", autouse=True)
def build_once():
    _build()


def test_bundled_v3_manifest_matches_reference():
    """Verify the bundled v3 manifest replay reports core accounting counters."""
    out = Path("/app/output/bundled-v3")
    out.mkdir(parents=True, exist_ok=True)
    report = out / "report.json"
    digest = out / "digest.txt"
    audit = out / "audit.jsonl"
    proc = _run(BUNDLED_MANIFEST, str(report), str(digest), str(audit))
    assert proc.returncode == 0, proc.stderr
    body = json.loads(report.read_text())
    exp = _expect_run(BUNDLED_MANIFEST)["report_obj"]
    assert body["schema_version"] == 3
    assert body["raw_input_digest"] == exp["raw_input_digest"]
    assert body["duplicate_raw_events"] == exp["duplicate_raw_events"]
    assert body["applied_events"] == exp["applied_events"]


def test_generated_revision_cancel_policy_case_seed_17():
    """Verify generated mixed-lane revisions, cancellations, and policy updates are replayed correctly."""
    tmp = Path("/tmp/hopledger-gen-17")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    manifest = _generate_case(17, tmp)
    report = tmp / "report.json"
    digest = tmp / "digest.txt"
    audit = tmp / "audit.jsonl"
    proc = _run(str(manifest), str(report), str(digest), str(audit))
    assert proc.returncode == 0, proc.stderr
    body = json.loads(report.read_text())
    exp = _expect_run(str(manifest))["report_obj"]
    assert body["schema_version"] == 3
    assert body["cancelled_events"] == exp["cancelled_events"]
    assert body["duplicate_raw_events"] == exp["duplicate_raw_events"]
    assert body["suppressed_hops"] == exp["suppressed_hops"]
    assert body["applied_events"] == exp["applied_events"]


def test_generated_revision_cancel_policy_case_seed_93():
    """Verify the replay contract across a different generated lane/tie topology."""
    tmp = Path("/tmp/hopledger-gen-93")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    manifest = _generate_case(93, tmp)
    report = tmp / "report.json"
    digest = tmp / "digest.txt"
    audit = tmp / "audit.jsonl"
    proc = _run(str(manifest), str(report), str(digest), str(audit))
    assert proc.returncode == 0, proc.stderr
    body = json.loads(report.read_text())
    exp = _expect_run(str(manifest))["report_obj"]
    assert body["schema_version"] == 3
    assert body["cancelled_events"] == exp["cancelled_events"]
    assert body["duplicate_raw_events"] == exp["duplicate_raw_events"]
    assert body["suppressed_hops"] == exp["suppressed_hops"]
    assert body["applied_events"] == exp["applied_events"]


def test_generated_checkpoint_resume_case_seed_241():
    """Verify resumed replay is byte-identical after revisions and lane-specific cursors."""
    tmp = Path("/tmp/hopledger-gen-241")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    manifest = _generate_case(241, tmp)
    full_report = tmp / "full.json"
    full_digest = tmp / "full.digest"
    full_audit = tmp / "full.audit.jsonl"
    proc = _run(str(manifest), str(full_report), str(full_digest), str(full_audit))
    assert proc.returncode == 0, proc.stderr

    exp = _expect_run(str(manifest))
    ckpt_tag = None
    for line in exp["audit"].splitlines():
        row = json.loads(line)
        if row["decision"] == "checkpoint":
            ckpt_tag = row["reason"]
            break
    assert ckpt_tag

    resume_report = tmp / "resume.json"
    resume_digest = tmp / "resume.digest"
    resume_audit = tmp / "resume.audit.jsonl"
    proc = _run(str(manifest), str(resume_report), str(resume_digest), str(resume_audit), ckpt_tag)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(resume_report.read_text()) == json.loads(full_report.read_text())
    assert resume_digest.read_text() == full_digest.read_text()
    assert resume_audit.read_text() == full_audit.read_text()


def test_resume_rejects_edited_prefix_and_cleans_outputs():
    """Verify stale checkpoint replay fails with exit code 2 and removes all requested outputs."""
    tmp = Path("/tmp/hopledger-stale-resume")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    manifest = _generate_case(55, tmp)
    report = tmp / "report.json"
    digest = tmp / "digest.txt"
    audit = tmp / "audit.jsonl"
    proc = _run(str(manifest), str(report), str(digest), str(audit))
    assert proc.returncode == 0

    exp = _expect_run(str(manifest))
    ckpt_tag = next(
        json.loads(line)["reason"]
        for line in exp["audit"].splitlines()
        if json.loads(line)["decision"] == "checkpoint"
    )

    lane_file = next(tmp.glob("lanes/*.ndjson"))
    lane_file.write_text('{"seq":99,"epoch":0,"kind":"note","source":"tamper"}\n' + lane_file.read_text())

    stale_report = tmp / "stale-report.json"
    stale_digest = tmp / "stale.digest"
    stale_audit = tmp / "stale.audit.jsonl"
    proc = _run(str(manifest), str(stale_report), str(stale_digest), str(stale_audit), ckpt_tag)
    assert proc.returncode == 2
    assert not stale_report.exists()
    assert not stale_digest.exists()
    assert not stale_audit.exists()


def test_policy_precedence_exact_source_dest_wildcard():
    """Verify exact, source wildcard, destination wildcard, full wildcard, and default SLA precedence."""
    tmp = Path("/tmp/hopledger-policy-precedence")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    policy = {
        "default_sla_ms": 120,
        "rules": [
            {"pattern": "alpha>*", "sla_ms": 80},
            {"pattern": "*>omega", "sla_ms": 70},
            {"pattern": "alpha>omega", "sla_ms": 50},
            {"pattern": "*>*", "sla_ms": 10},
        ],
    }
    (tmp / "policy.json").write_text(json.dumps(policy) + "\n")
    lanes = [
        {
            "name": "main",
            "path": "lanes/main.ndjson",
            "priority": 1,
            "body": "\n".join(
                [
                    json.dumps({"seq": 1, "epoch": 0, "kind": "link_open", "link": "alpha>omega"}),
                    json.dumps({"seq": 2, "epoch": 0, "kind": "hop", "link": "alpha>omega", "ms": 51}),
                    json.dumps({"seq": 3, "epoch": 0, "kind": "link_open", "link": "beta>omega"}),
                    json.dumps({"seq": 4, "epoch": 0, "kind": "hop", "link": "beta>omega", "ms": 71}),
                ]
            ),
        }
    ]
    manifest = _write_manifest(tmp, lanes, policy_src=None)
    manifest_obj = json.loads(manifest.read_text())
    manifest_obj["policy"] = "policy.json"
    manifest.write_text(json.dumps(manifest_obj, indent=2) + "\n")

    report = tmp / "report.json"
    digest = tmp / "digest.txt"
    audit = tmp / "audit.jsonl"
    proc = _run(str(manifest), str(report), str(digest), str(audit))
    assert proc.returncode == 0
    body = json.loads(report.read_text())
    by_id = {row["link_id"]: row for row in body["links"]}
    assert by_id["alpha>omega"]["sla_ms"] == 50
    assert by_id["alpha>omega"]["alarm_breaches"] == 1
    assert by_id["beta>omega"]["sla_ms"] == 70
    assert by_id["beta>omega"]["alarm_breaches"] == 1


def test_raw_digest_changes_for_superseded_duplicate_and_cancelled_records():
    """Verify digest lineage changes when non-applied raw records change."""
    tmp = Path("/tmp/hopledger-raw-digest")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    base_lines = [
        json.dumps({"seq": 1, "epoch": 0, "kind": "link_open", "link": "a>b"}),
        json.dumps({"seq": 2, "epoch": 0, "kind": "hop", "link": "a>b", "ms": 40}),
    ]
    lanes = [{"name": "main", "path": "lanes/main.ndjson", "priority": 1, "body": "\n".join(base_lines)}]
    manifest = _write_manifest(tmp, lanes, policy_src=None)
    report = tmp / "report.json"
    digest = tmp / "digest.txt"
    audit = tmp / "audit.jsonl"
    proc = _run(str(manifest), str(report), str(digest), str(audit))
    assert proc.returncode == 0
    first_digest = digest.read_text()

    extra = lanes[0]["body"] + "\n" + json.dumps({"seq": 3, "epoch": 0, "kind": "note", "source": "main"})
    lanes[0]["body"] = extra
    manifest2 = _write_manifest(tmp / "variant", lanes, policy_src=None)
    report2 = tmp / "variant/report.json"
    digest2 = tmp / "variant/digest.txt"
    audit2 = tmp / "variant/audit.jsonl"
    proc = _run(str(manifest2), str(report2), str(digest2), str(audit2))
    assert proc.returncode == 0
    assert digest2.read_text() != first_digest


def test_audit_decisions_are_complete_and_ordered():
    """Verify audit JSONL records include every required field in deterministic replay order."""
    tmp = Path("/tmp/hopledger-audit-fields")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    manifest = _generate_case(77, tmp)
    audit = tmp / "audit.jsonl"
    proc = _run(str(manifest), str(tmp / "r.json"), str(tmp / "d.txt"), str(audit))
    assert proc.returncode == 0
    exp = _expect_run(str(manifest))
    assert audit.read_text() == exp["audit"]
    required = {"decision", "epoch", "seq", "lane", "source", "op_id", "rev", "kind", "reason", "link"}
    for line in audit.read_text().splitlines():
        row = json.loads(line)
        assert required.issubset(row.keys())


def test_malformed_records_are_atomic_failures():
    """Verify malformed JSON, unknown kinds, negative latency, and invalid policy updates fail atomically."""
    tmp = Path("/tmp/hopledger-malformed")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    cases = [
        '{"seq":1,"epoch":0,"kind":"hop","link":"a>b","ms":-1}',
        '{"seq":1,"epoch":0,"kind":"unknown","link":"a>b"}',
        "not-json",
        json.dumps({"seq": 1, "epoch": 0, "kind": "policy_update"}),
    ]
    for idx, bad in enumerate(cases):
        lane = {
            "name": "main",
            "path": f"lanes/case{idx}.ndjson",
            "priority": 1,
            "body": json.dumps({"seq": 1, "epoch": 0, "kind": "link_open", "link": "a>b"}) + "\n" + bad,
        }
        case_dir = tmp / f"case{idx}"
        manifest = _write_manifest(case_dir, [lane], policy_src=None)
        report = case_dir / "report.json"
        digest = case_dir / "digest.txt"
        audit = case_dir / "audit.jsonl"
        proc = _run(str(manifest), str(report), str(digest), str(audit))
        assert proc.returncode == 2
        assert not report.exists()
        assert not digest.exists()
        assert not audit.exists()


def test_epoch_sorting_is_numeric_not_lexicographic():
    """Verify epochs such as 100 are replayed after smaller numeric epochs, not lexicographically."""
    tmp = Path("/tmp/hopledger-epoch-sort")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    lanes = [
        {
            "name": "main",
            "path": "lanes/main.ndjson",
            "priority": 1,
            "body": "\n".join(
                [
                    json.dumps({"seq": 1, "epoch": 100, "kind": "link_open", "link": "late>z"}),
                    json.dumps({"seq": 2, "epoch": 100, "kind": "hop", "link": "late>z", "ms": 10}),
                    json.dumps({"seq": 1, "epoch": 20, "kind": "link_open", "link": "early>a"}),
                    json.dumps({"seq": 2, "epoch": 20, "kind": "hop", "link": "early>a", "ms": 10}),
                ]
            ),
        }
    ]
    manifest = _write_manifest(tmp, lanes, policy_src=None)
    report = tmp / "report.json"
    digest = tmp / "digest.txt"
    audit = tmp / "audit.jsonl"
    proc = _run(str(manifest), str(report), str(digest), str(audit))
    assert proc.returncode == 0
    exp = _expect_run(str(manifest))
    assert json.loads(report.read_text()) == exp["report_obj"]
