"""Verifier for iam-policy-regression-auditor."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import subprocess
import tempfile
from functools import lru_cache
from itertools import product
from pathlib import Path


TASK_ROOT = Path(os.environ.get("TASK_FILE_DIR", "/app/task_file"))
VISIBLE_CASE = TASK_ROOT / "policy_case.txt"
OUTPUT_DIR = TASK_ROOT / "output"
REPORT_PATH = OUTPUT_DIR / "policy_regression_report.json"
ANALYZER_PATH = OUTPUT_DIR / "policy_regression_analyzer.rs"
RUN_TIMEOUT_SEC = int(os.environ.get("RUNBOOK_TIMEOUT_SEC", "120"))

INPUT_HASHES = {
    "policy_case.txt": "137a695a1ad4e966ecc88167dbd68647e83a46c6d68f37c27e50926ab44003dc",
}


def renamed_visible_case() -> str:
    text = VISIBLE_CASE.read_text(encoding="utf-8")
    replacements = {
        "user_alice": "user_ava",
        "user_bob": "user_blair",
        "role_ci_build": "role_pipeline_build",
        "role_ci_deploy": "role_pipeline_deploy",
        "role_audit": "role_log_audit",
        "role_breakglass": "role_emergency",
        "arn:dev:artifact": "arn:stage:artifact",
        "arn:prod:artifact": "arn:live:artifact",
        "arn:prod:secret": "arn:live:secret",
        "arn:prod:kms": "arn:live:kms",
        "arn:finance:ledger": "arn:finops:ledger",
        "arn:audit:logs": "arn:logs:audit",
        "arn:breakglass:admin": "arn:emergency:admin",
        "arn:dev:*": "arn:stage:*",
        "arn:prod:*": "arn:live:*",
        "arn:finance:*": "arn:finops:*",
        "arn:audit:*": "arn:logs:*",
        "arn:breakglass:*": "arn:emergency:*",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def alternate_case() -> str:
    return "\n".join(
        [
            "PRINCIPAL user_dev dept=eng,clearance=dev,type=human",
            "PRINCIPAL user_ops dept=ops,clearance=prod,type=human",
            "PRINCIPAL role_bot dept=eng,clearance=dev,type=service",
            "ACTION app:Read",
            "ACTION app:Write",
            "ACTION app:Admin",
            "ACTION iam:PassRole",
            "RESOURCE app:dev 3 env=dev,owner=eng",
            "RESOURCE app:prod 12 env=prod,owner=ops",
            "RESOURCE iam:prod-role 16 env=prod,owner=ops",
            "CONTEXT mfa true,false",
            "CONTEXT source_ip 10.0.0.5,203.0.113.5",
            "SESSION_TAG env dev,prod",
            "SESSION_TAG breakglass true,false",
            "COND mfa Bool request.mfa true",
            "COND corp IpAddress request.source_ip 10.0.0.0/8",
            "COND prod_session StringEquals session.env prod",
            "COND not_prod_session StringNotEquals session.env prod",
            "COND no_breakglass Null session.breakglass true",
            "COND breakglass StringEquals session.breakglass true",
            "COND prod_res StringEquals resource.env prod",
            "STMT BASE B1 IDENTITY ALLOW user_dev,role_bot app:Read app:dev -",
            "STMT BASE B2 IDENTITY ALLOW user_ops app:Read,app:Write app:prod mfa,corp",
            "STMT BASE B3 IDENTITY ALLOW role_bot iam:PassRole iam:prod-role not_prod_session",
            "STMT BASE B4 IDENTITY DENY role_bot app:Admin app:prod -",
            "STMT BASE B5 BOUNDARY ALLOW role_bot app:Read,iam:PassRole app:dev,iam:prod-role -",
            "STMT BASE B6 SCP ALLOW user_ops app:* app:prod mfa",
            "STMT BASE B7 SCP ALLOW role_bot app:Read,iam:PassRole app:dev,iam:prod-role -",
            "STMT PATCHED P1 IDENTITY ALLOW user_dev,role_bot app:Read app:dev -",
            "STMT PATCHED P2 IDENTITY ALLOW user_ops app:Read app:prod mfa,corp",
            "STMT PATCHED P3 IDENTITY ALLOW role_bot iam:PassRole,app:Admin iam:prod-role,app:prod prod_session",
            "STMT PATCHED P4 BOUNDARY ALLOW role_bot app:Read,iam:PassRole,app:Admin app:dev,iam:prod-role,app:prod prod_session",
            "STMT PATCHED P5 SCP ALLOW *,!user_dev app:*,iam:* app:prod,iam:prod-role prod_res",
            "INVARIANT no_bot_admin role_bot app:Admin app:prod -",
            "INVARIANT no_public_prod * app:* app:prod no_breakglass",
            "",
        ]
    )


def hard_case() -> str:
    lines = [
        "PRINCIPAL user_eng dept=eng,clearance=dev,type=human",
        "PRINCIPAL user_fin dept=finance,clearance=prod,type=human",
        "PRINCIPAL role_build dept=eng,clearance=dev,type=service",
        "PRINCIPAL role_release dept=eng,clearance=prod,type=service",
        "PRINCIPAL role_audit dept=audit,clearance=prod,type=human",
        "PRINCIPAL role_sec dept=security,clearance=prod,type=human",
    ]
    for action in [
        "svc:Read",
        "svc:Write",
        "svc:Admin",
        "iam:PassRole",
        "kms:Decrypt",
        "secret:Get",
        "audit:Read",
        "billing:Read",
    ]:
        lines.append(f"ACTION {action}")
    resources = [
        ("res:dev-app", 4, "env=dev,owner=eng,data=app"),
        ("res:prod-app", 15, "env=prod,owner=eng,data=app"),
        ("res:prod-admin", 25, "env=prod,owner=security,data=admin"),
        ("res:kms", 18, "env=prod,owner=security,data=key"),
        ("res:secret", 20, "env=prod,owner=security,data=secret"),
        ("res:audit", 8, "env=prod,owner=audit,data=logs"),
        ("res:billing", 12, "env=prod,owner=finance,data=ledger"),
    ]
    for rid, value, tags in resources:
        lines.append(f"RESOURCE {rid} {value} {tags}")
    lines.extend(
        [
            "CONTEXT mfa true,false",
            "CONTEXT source_ip 10.1.2.3,10.9.8.7,198.51.100.20",
            "CONTEXT device managed,unmanaged",
            "SESSION_TAG env dev,prod",
            "SESSION_TAG project alpha,beta",
            "SESSION_TAG ticket open,closed",
            "SESSION_TAG emergency true,false",
            "COND mfa Bool request.mfa true",
            "COND managed StringEquals request.device managed",
            "COND corp IpAddress request.source_ip 10.0.0.0/8",
            "COND prod_session StringEquals session.env prod",
            "COND dev_session StringEquals session.env dev",
            "COND alpha StringEquals session.project alpha",
            "COND ticket_open StringEquals session.ticket open",
            "COND emergency StringEquals session.emergency true",
            "COND no_emergency Null session.emergency true",
            "COND prod_res StringEquals resource.env prod",
            "COND secret_data StringEquals resource.data secret,key",
            "STMT BASE B1 IDENTITY ALLOW user_eng,role_build svc:Read res:dev-* -",
            "STMT BASE B2 IDENTITY ALLOW role_build svc:Write res:dev-app dev_session",
            "STMT BASE B3 IDENTITY ALLOW role_release iam:PassRole res:prod-app prod_session",
            "STMT BASE B4 IDENTITY ALLOW role_audit audit:Read res:audit mfa,corp",
            "STMT BASE B5 IDENTITY ALLOW user_fin billing:Read res:billing mfa,corp",
            "STMT BASE B6 IDENTITY DENY * kms:Decrypt,secret:Get res:kms,res:secret -",
            "STMT BASE B7 BOUNDARY ALLOW role_build svc:Read,svc:Write res:dev-* -",
            "STMT BASE B8 BOUNDARY ALLOW role_release iam:PassRole res:prod-app prod_session",
            "STMT BASE B9 SCP ALLOW *,!user_eng svc:*,iam:PassRole,audit:Read,billing:Read res:prod-*,res:audit,res:billing mfa",
            "STMT BASE B10 SCP ALLOW * svc:* res:dev-* -",
            "STMT PATCHED P1 IDENTITY ALLOW user_eng,role_build svc:Read res:dev-* -",
            "STMT PATCHED P2 IDENTITY ALLOW role_build svc:Write res:dev-app dev_session",
            "STMT PATCHED P3 IDENTITY ALLOW role_release iam:PassRole,svc:Admin res:prod-app,res:prod-admin prod_session,alpha",
            "STMT PATCHED P4 IDENTITY ALLOW role_audit audit:Read,secret:Get res:audit,res:secret mfa,corp",
            "STMT PATCHED P5 IDENTITY ALLOW user_fin billing:Read res:billing mfa,corp",
            "STMT PATCHED P6 IDENTITY DENY * secret:Get res:secret no_emergency",
            "STMT PATCHED P7 BOUNDARY ALLOW role_build svc:Read,svc:Write,svc:Admin res:dev-*,res:prod-admin alpha",
            "STMT PATCHED P8 BOUNDARY ALLOW role_release iam:PassRole,svc:Admin res:prod-app,res:prod-admin prod_session",
            "STMT PATCHED P9 SCP ALLOW *,!user_eng svc:*,iam:PassRole,audit:Read,billing:Read,secret:Get res:prod-*,res:audit,res:billing,res:secret mfa",
            "STMT PATCHED P10 SCP ALLOW * svc:* res:dev-* -",
            "STMT PATCHED P11 RESOURCE ALLOW role_release,role_build svc:Admin res:prod-admin alpha",
            "STMT PATCHED P12 RESOURCE ALLOW role_audit secret:Get res:secret emergency",
            "INVARIANT no_build_admin role_build svc:Admin res:prod-admin -",
            "INVARIANT no_audit_secret role_audit secret:Get res:secret -",
            "INVARIANT no_unmanaged_prod *,!role_sec svc:* res:prod-* managed",
            "",
        ]
    )
    return "\n".join(lines)


@lru_cache(maxsize=1)
def hidden_case_paths() -> tuple[Path, ...]:
    root = Path(tempfile.mkdtemp(prefix="policy_regression_cases_"))
    cases = {
        "case_renamed.txt": renamed_visible_case(),
        "case_alternate.txt": alternate_case(),
        "case_hard.txt": hard_case(),
    }
    paths = []
    for name, text in cases.items():
        path = root / name
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    return tuple(paths)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_csv(token: str) -> list[str]:
    return [] if token == "-" else token.split(",")


def parse_tags(token: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for item in parse_csv(token):
        key, value = item.split("=", 1)
        tags[key] = value
    return tags


@lru_cache(maxsize=None)
def glob_match(pattern: str, text: str) -> bool:
    def rec(pi: int, ti: int) -> bool:
        if pi == len(pattern):
            return ti == len(text)
        if pattern[pi] == "*":
            return rec(pi + 1, ti) or (ti < len(text) and rec(pi, ti + 1))
        if pattern[pi] == "?":
            return ti < len(text) and rec(pi + 1, ti + 1)
        return ti < len(text) and pattern[pi] == text[ti] and rec(pi + 1, ti + 1)

    return rec(0, 0)


def pattern_list_match(patterns: list[str], text: str) -> bool:
    positives = [item for item in patterns if not item.startswith("!")]
    negatives = [item[1:] for item in patterns if item.startswith("!")]
    positive_ok = any(glob_match(item, text) for item in positives) if positives else True
    negative_hit = any(glob_match(item, text) for item in negatives)
    return positive_ok and not negative_hit


def parse_case(path: Path) -> dict:
    principals: list[dict] = []
    actions: list[str] = []
    resources: list[dict] = []
    contexts: list[dict] = []
    session_tags: list[dict] = []
    conditions: dict[str, dict] = {}
    statements = {"BASE": [], "PATCHED": []}
    invariants: list[dict] = []

    with path.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            row = parts[0]
            if row == "PRINCIPAL":
                principals.append({"id": parts[1], "tags": parse_tags(parts[2])})
            elif row == "ACTION":
                actions.append(parts[1])
            elif row == "RESOURCE":
                resources.append({"id": parts[1], "value": int(parts[2]), "tags": parse_tags(parts[3])})
            elif row == "CONTEXT":
                contexts.append({"key": parts[1], "values": parse_csv(parts[2])})
            elif row == "SESSION_TAG":
                session_tags.append({"key": parts[1], "values": parse_csv(parts[2])})
            elif row == "COND":
                conditions[parts[1]] = {"id": parts[1], "op": parts[2], "key": parts[3], "values": parse_csv(parts[4])}
            elif row == "STMT":
                statements[parts[1]].append(
                    {
                        "id": parts[2],
                        "layer": parts[3],
                        "effect": parts[4],
                        "principals": parse_csv(parts[5]),
                        "actions": parse_csv(parts[6]),
                        "resources": parse_csv(parts[7]),
                        "conditions": parse_csv(parts[8]),
                    }
                )
            elif row == "INVARIANT":
                invariants.append(
                    {
                        "id": parts[1],
                        "principals": parse_csv(parts[2]),
                        "actions": parse_csv(parts[3]),
                        "resources": parse_csv(parts[4]),
                        "conditions": parse_csv(parts[5]),
                    }
                )
            else:
                raise AssertionError(f"unknown row {row}")

    return {
        "principals": principals,
        "actions": actions,
        "resources": resources,
        "contexts": contexts,
        "session_tags": session_tags,
        "conditions": conditions,
        "statements": statements,
        "invariants": invariants,
    }


def request_value(case: dict, req: dict, key: str) -> str | None:
    scope, name = key.split(".", 1)
    if scope == "principal":
        return req["principal"]["tags"].get(name)
    if scope == "resource":
        return req["resource"]["tags"].get(name)
    if scope == "request":
        return req["context"].get(name)
    if scope == "session":
        return req["session"].get(name)
    raise AssertionError(f"bad condition key {key}")


def condition_true(case: dict, req: dict, cond_id: str) -> bool:
    cond = case["conditions"][cond_id]
    value = request_value(case, req, cond["key"])
    values = cond["values"]
    op = cond["op"]
    if op in {"StringEquals", "Bool"}:
        return value is not None and value in values
    if op == "StringNotEquals":
        return value is None or value not in values
    if op == "StringLike":
        return value is not None and any(glob_match(pattern, value) for pattern in values)
    if op == "Null":
        assert len(values) == 1
        return (value is None) == (values[0] == "true")
    if op == "IpAddress":
        if value is None:
            return False
        ip = ipaddress.ip_address(value)
        return any(ip in ipaddress.ip_network(item, strict=False) for item in values)
    raise AssertionError(f"bad op {op}")


def conditions_true(case: dict, req: dict, cond_ids: list[str]) -> bool:
    return all(condition_true(case, req, cond_id) for cond_id in cond_ids)


def request_matches_shape(case: dict, req: dict, shape: dict, check_conditions: bool = True) -> bool:
    return (
        pattern_list_match(shape["principals"], req["principal"]["id"])
        and pattern_list_match(shape["actions"], req["action"])
        and pattern_list_match(shape["resources"], req["resource"]["id"])
        and (not check_conditions or conditions_true(case, req, shape["conditions"]))
    )


def decision(case: dict, bundle: str, req: dict) -> dict:
    stmts = case["statements"][bundle]
    matched = [stmt for stmt in stmts if request_matches_shape(case, req, stmt)]
    deny_ids = [stmt["id"] for stmt in matched if stmt["effect"] == "DENY"]
    allow_ids = [stmt["id"] for stmt in matched if stmt["effect"] == "ALLOW"]
    identity_or_resource_allow = any(
        stmt["effect"] == "ALLOW" and stmt["layer"] in {"IDENTITY", "RESOURCE"} for stmt in matched
    )
    boundary_needed = any(
        stmt["layer"] == "BOUNDARY" and pattern_list_match(stmt["principals"], req["principal"]["id"]) for stmt in stmts
    )
    scp_needed = any(
        stmt["layer"] == "SCP" and request_matches_shape(case, req, stmt, check_conditions=False) for stmt in stmts
    )
    boundary_ok = not boundary_needed or any(
        stmt["effect"] == "ALLOW" and stmt["layer"] == "BOUNDARY" for stmt in matched
    )
    scp_ok = not scp_needed or any(stmt["effect"] == "ALLOW" and stmt["layer"] == "SCP" for stmt in matched)
    missing = []
    if not boundary_ok:
        missing.append("BOUNDARY")
    if not scp_ok:
        missing.append("SCP")
    allowed = not deny_ids and identity_or_resource_allow and boundary_ok and scp_ok
    return {
        "allowed": allowed,
        "matched_deny_statement_ids": deny_ids,
        "matched_allow_statement_ids": allow_ids,
        "missing_gate_layers": missing,
    }


def enumerate_requests(case: dict):
    context_values = [ctx["values"] for ctx in case["contexts"]]
    session_values = [[None] + tag["values"] for tag in case["session_tags"]]
    for principal in case["principals"]:
        for action in case["actions"]:
            for resource in case["resources"]:
                for ctx_combo in product(*context_values):
                    context = {ctx["key"]: value for ctx, value in zip(case["contexts"], ctx_combo)}
                    for sess_combo in product(*session_values):
                        session = {
                            tag["key"]: value
                            for tag, value in zip(case["session_tags"], sess_combo)
                            if value is not None
                        }
                        yield {
                            "principal": principal,
                            "action": action,
                            "resource": resource,
                            "context": context,
                            "session": session,
                        }


def request_object(case: dict, req: dict, base_decision: dict, patched_decision: dict) -> dict:
    return {
        "principal_id": req["principal"]["id"],
        "action_id": req["action"],
        "resource_id": req["resource"]["id"],
        "request_context": {ctx["key"]: req["context"][ctx["key"]] for ctx in case["contexts"]},
        "session_tags": {tag["key"]: req["session"][tag["key"]] for tag in case["session_tags"] if tag["key"] in req["session"]},
        "base_decision": base_decision,
        "patched_decision": patched_decision,
    }


def solve_case(path: Path) -> dict:
    case = parse_case(path)
    base_allow_count = 0
    patched_allow_count = 0
    regression_count = 0
    blocked_count = 0
    regression_counterexample = None
    blocked_counterexample = None
    invariant_hits: list[dict | None] = [None] * len(case["invariants"])

    for req in enumerate_requests(case):
        base = decision(case, "BASE", req)
        patched = decision(case, "PATCHED", req)
        if base["allowed"]:
            base_allow_count += 1
        if patched["allowed"]:
            patched_allow_count += 1
        if not base["allowed"] and patched["allowed"]:
            regression_count += 1
            if regression_counterexample is None:
                regression_counterexample = request_object(case, req, base, patched)
        if base["allowed"] and not patched["allowed"]:
            blocked_count += 1
            if blocked_counterexample is None:
                blocked_counterexample = request_object(case, req, base, patched)
        if patched["allowed"]:
            for idx, invariant in enumerate(case["invariants"]):
                if invariant_hits[idx] is None and request_matches_shape(case, req, invariant):
                    invariant_hits[idx] = {
                        "invariant_id": invariant["id"],
                        "counterexample": request_object(case, req, base, patched),
                    }

    violated = [item for item in invariant_hits if item is not None]
    unsafe = regression_count > 0 or bool(violated)
    if unsafe and blocked_count > 0:
        classification = "mixed"
    elif unsafe:
        classification = "regression"
    elif blocked_count > 0:
        classification = "safer"
    else:
        classification = "equivalent"
    return {
        "classification": classification,
        "base_allow_count": base_allow_count,
        "patched_allow_count": patched_allow_count,
        "regression_count": regression_count,
        "blocked_count": blocked_count,
        "regression_counterexample": regression_counterexample,
        "blocked_counterexample": blocked_counterexample,
        "violated_invariants": violated,
    }


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def assert_decision_schema(item: dict) -> None:
    assert set(item) == {
        "allowed",
        "matched_deny_statement_ids",
        "matched_allow_statement_ids",
        "missing_gate_layers",
    }
    assert isinstance(item["allowed"], bool)
    assert isinstance(item["matched_deny_statement_ids"], list)
    assert isinstance(item["matched_allow_statement_ids"], list)
    assert isinstance(item["missing_gate_layers"], list)


def assert_counterexample_schema(item: dict | None) -> None:
    if item is None:
        return
    assert set(item) == {
        "principal_id",
        "action_id",
        "resource_id",
        "request_context",
        "session_tags",
        "base_decision",
        "patched_decision",
    }
    assert isinstance(item["principal_id"], str)
    assert isinstance(item["action_id"], str)
    assert isinstance(item["resource_id"], str)
    assert isinstance(item["request_context"], dict)
    assert isinstance(item["session_tags"], dict)
    assert_decision_schema(item["base_decision"])
    assert_decision_schema(item["patched_decision"])


def assert_valid_schema(report: dict) -> None:
    assert set(report) == {
        "classification",
        "base_allow_count",
        "patched_allow_count",
        "regression_count",
        "blocked_count",
        "regression_counterexample",
        "blocked_counterexample",
        "violated_invariants",
    }
    assert report["classification"] in {"mixed", "regression", "safer", "equivalent"}
    for key in ["base_allow_count", "patched_allow_count", "regression_count", "blocked_count"]:
        assert isinstance(report[key], int)
    assert_counterexample_schema(report["regression_counterexample"])
    assert_counterexample_schema(report["blocked_counterexample"])
    assert isinstance(report["violated_invariants"], list)
    for item in report["violated_invariants"]:
        assert set(item) == {"invariant_id", "counterexample"}
        assert isinstance(item["invariant_id"], str)
        assert_counterexample_schema(item["counterexample"])


def compile_analyzer(tmp_path: Path) -> Path:
    binary = tmp_path / "policy_regression_analyzer"
    subprocess.run(
        ["rustc", "--edition", "2021", "-C", "opt-level=3", str(ANALYZER_PATH), "-o", str(binary)],
        check=True,
        timeout=RUN_TIMEOUT_SEC,
    )
    return binary


def run_analyzer(binary: Path, input_path: Path, output_path: Path) -> dict:
    subprocess.run([str(binary), str(input_path), str(output_path)], check=True, timeout=RUN_TIMEOUT_SEC)
    report = load_json(output_path)
    assert_valid_schema(report)
    return report


def test_visible_case_is_unchanged() -> None:
    assert sha256_file(VISIBLE_CASE) == INPUT_HASHES["policy_case.txt"]


def test_output_and_analyzer_exist_with_valid_schema() -> None:
    assert REPORT_PATH.exists(), "missing policy_regression_report.json"
    assert ANALYZER_PATH.exists(), "missing policy_regression_analyzer.rs"
    assert_valid_schema(load_json(REPORT_PATH))


def test_analyzer_source_has_no_harness_shortcuts() -> None:
    source = ANALYZER_PATH.read_text(encoding="utf-8").lower()
    forbidden = [
        "/tests",
        "test_outputs",
        "/solution",
        "/logs/verifier",
        "reward.txt",
        "reward.json",
        "std::process::command",
        "command::new",
        "/bin/sh",
        "bash",
        "python",
        "pytest",
        "role_ci_deploy",
        "p_id_ci_project_admin",
        "no_ci_prod_admin",
    ]
    for needle in forbidden:
        assert needle not in source, f"analyzer source contains shortcut marker {needle!r}"


def test_visible_report_matches_reference_exactly() -> None:
    assert load_json(REPORT_PATH) == solve_case(VISIBLE_CASE)


def test_emitted_analyzer_matches_hidden_cases(tmp_path: Path) -> None:
    binary = compile_analyzer(tmp_path)
    for input_path in hidden_case_paths()[:2]:
        assert run_analyzer(binary, input_path, tmp_path / f"{input_path.stem}.json") == solve_case(input_path)


def test_emitted_analyzer_handles_hard_hidden_case(tmp_path: Path) -> None:
    binary = compile_analyzer(tmp_path)
    input_path = hidden_case_paths()[2]
    assert run_analyzer(binary, input_path, tmp_path / "hard.json") == solve_case(input_path)


def test_reference_sanity_catches_common_traps() -> None:
    visible = solve_case(VISIBLE_CASE)
    assert visible["classification"] == "mixed"
    assert visible["regression_count"] == 534
    assert visible["blocked_count"] == 648
    assert visible["regression_counterexample"]["principal_id"] == "role_ci_deploy"
    assert visible["regression_counterexample"]["action_id"] == "prod:Admin"
    assert visible["regression_counterexample"]["resource_id"] == "arn:prod:artifact"
    assert visible["regression_counterexample"]["session_tags"] == {"env": "prod", "project": "alpha"}
    assert visible["violated_invariants"][0]["invariant_id"] == "no_ci_prod_admin"

    alternate = solve_case(hidden_case_paths()[1])
    assert alternate["classification"] == "mixed"
    assert alternate["regression_counterexample"]["principal_id"] == "role_bot"
    assert alternate["violated_invariants"][0]["invariant_id"] == "no_bot_admin"
