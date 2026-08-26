import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ENV = (
    Path("/app/environment")
    if Path("/app/environment").exists()
    else Path(__file__).parents[1] / "environment"
)
OUT = (
    Path("/app/out")
    if Path("/app").exists() and Path("/app/environment").exists()
    else Path("/tmp/lua-tls-test-out")
)
sys.path.insert(0, str(Path(__file__).parent / "support"))
from policy_graph import (  # noqa: E402
    canonical,
    commitment,
    counterfactual_disposition,
    expected_rollback_constraints,
    merged,
    optimal_cut,
    path_verdicts,
    subject_outcome,
)


def setup_module():
    shutil.rmtree(OUT, ignore_errors=True)
    command = (
        ["/app/environment/run.sh"]
        if Path("/app/environment/run.sh").exists()
        else [
            sys.executable,
            str(Path(__file__).parents[1] / "solution/engine.py"),
            "--environment",
            str(ENV),
            "--output",
            str(OUT),
        ]
    )
    subprocess.run(command, check=True, timeout=60)


def load(name):
    root = OUT / name
    return (
        json.loads((root / "trust_assessment.json").read_text()),
        json.loads((root / "containment_plan.json").read_text()),
        (root / "decision_commitment.bin").read_bytes(),
    )


def test_complete_record_set_and_contract_vocabulary():
    """Every required case exists and every verifier domain is public."""
    names = {
        json.loads(p.read_text())["profile"] for p in (ENV / "cases").glob("*.json")
    }
    assert names == {p.name for p in OUT.iterdir() if p.is_dir()}
    public = "\n".join(p.read_text() for p in (ENV / "contracts").glob("*.md"))
    for token in [
        "RETAIN",
        "QUARANTINE",
        "ROTATE",
        "MANUAL_REVIEW",
        "VALID_PATH",
        "COMPROMISED_PATH",
        "QUORUM_FAILURE",
        "REVOKED",
        "EXCEPTION_SCOPE",
        "UNRESOLVED_POLICY",
        "PRECEDENCE_RESOLVED",
        "SCOPE_DISTINGUISHED",
        "SUPERSEDED",
        "UNRESOLVED",
        "INC8821",
    ]:
        assert token in public


def test_independent_semantic_reconstruction():
    """Reconstruct all assessment, containment, and commitment semantics."""
    for pp in sorted((ENV / "cases").glob("*.json")):
        evidence, profile = merged(ENV, pp)
        report, plan, binary = load(profile["profile"])
        verdicts, witnesses, threshold = path_verdicts(evidence)
        rows = {a["subject_id"]: a for a in report["assessments"]}
        assert set(rows) == {s["id"] for s in evidence["services"]}
        for service, row in rows.items():
            expected_accept = sorted(
                p["id"]
                for p in evidence["paths"]
                if p["service"] == service and verdicts[p["id"]] is None
            )
            expected_reject = sorted(
                p["id"]
                for p in evidence["paths"]
                if p["service"] == service and verdicts[p["id"]] is not None
            )
            assert (
                row["accepted_paths"] == expected_accept
                and row["rejected_paths"] == expected_reject
            )
            assert row["quorum"] == {
                "required": threshold,
                "counted": len(witnesses),
                "witness_ids": witnesses,
            }
            assert row["disposition"] == (
                "RETAIN"
                if expected_accept
                else (
                    "MANUAL_REVIEW"
                    if any(verdicts[p] == "UNRESOLVED_POLICY" for p in expected_reject)
                    else "QUARANTINE"
                )
            )
            assert row["reason_code"] == subject_outcome(evidence, service)[1]
            counterfactual = row["counterfactual"]
            assert counterfactual[
                "resulting_disposition"
            ] == counterfactual_disposition(
                evidence, service, counterfactual["changed_fact"]
            )
        expected_cut = optimal_cut(evidence, verdicts)
        assert (
            expected_cut
            and plan["minimum_cut"] == list(expected_cut[2])
            and plan["blast_radius"] == expected_cut[1]
        )
        quarantined = sorted(
            row["subject_id"]
            for row in report["assessments"]
            if row["disposition"] == "QUARANTINE"
        )
        assert plan["execution_order"] == [
            *(f"disable:{object_id}" for object_id in expected_cut[2]),
            *(f"quarantine:{subject_id}" for subject_id in quarantined),
        ]
        assert plan["rollback_constraints"] == expected_rollback_constraints(
            evidence, set(plan["unresolved_conflicts"])
        )
        digest = hashlib.sha256(
            canonical({"evidence": evidence, "profile": profile})
        ).hexdigest()
        assert report["evidence_set_digest"] == digest
        assert binary == commitment(evidence, profile, report, plan)


def test_conflict_classification_and_fail_closed():
    """Classify authority contradictions and fail closed on the unresolved row."""
    report, plan, _ = load("baseline_compromise")
    classes = {
        x["conflict_id"]: x["classification"]
        for x in report["conflict_classifications"]
    }
    assert classes == {
        "CF-1": "PRECEDENCE_RESOLVED",
        "CF-2": "SCOPE_DISTINGUISHED",
        "CF-3": "SUPERSEDED",
        "CF-4": "UNRESOLVED",
    }
    assert plan["unresolved_conflicts"] == ["CF-4"]
    settlement = next(
        a for a in report["assessments"] if a["subject_id"] == "settlement_api"
    )
    assert settlement["disposition"] == "MANUAL_REVIEW"


def test_metamorphic_branches_and_counterfactuals():
    """Exercise quorum, revocation, exception scope, and counterfactual branches."""
    base, _, _ = load("baseline_compromise")
    fail, _, _ = load("quorum_independence_failure")
    scope, _, _ = load("emergency_exception_scope")
    retro, _, _ = load("retroactive_revocation")
    b = {x["subject_id"]: x for x in base["assessments"]}
    f = {x["subject_id"]: x for x in fail["assessments"]}
    s = {x["subject_id"]: x for x in scope["assessments"]}
    r = {x["subject_id"]: x for x in retro["assessments"]}
    assert b["payments_ingress"]["accepted_paths"] == ["P_PAY_BLUE", "P_PAY_RED"]
    assert (
        f["payments_ingress"]["accepted_paths"] == ["P_PAY_BLUE"]
        and "P_PAY_RED" in f["payments_ingress"]["rejected_paths"]
    )
    assert (
        b["emergency_capture"]["disposition"] == "RETAIN"
        and s["emergency_capture"]["disposition"] == "QUARANTINE"
    )
    assert "P_SETTLE" in r["settlement_api"]["rejected_paths"]
    for report in [base, fail, scope, retro]:
        for row in report["assessments"]:
            assert row["counterfactual"]["changed_fact"].startswith(
                ("remove witness ", "remove exception ", "remove path ")
            )


def test_canonical_json_and_ordering():
    """Require canonical JSON and deterministic subject ordering."""
    for pp in (ENV / "cases").glob("*.json"):
        profile_name = json.loads(pp.read_text())["profile"]
        report, plan, _ = load(profile_name)
        assert (OUT / profile_name / "trust_assessment.json").read_bytes() == canonical(
            report
        )
        assert (OUT / profile_name / "containment_plan.json").read_bytes() == canonical(
            plan
        )
        assert [a["subject_id"] for a in report["assessments"]] == sorted(
            a["subject_id"] for a in report["assessments"]
        )
