from __future__ import annotations

import hashlib
import json
import os
import shutil
import statistics
import subprocess
from pathlib import Path

import pytest

from model_for_tests import EXPECTED_RULES, THRESHOLD, load_sarif_results, score

TASK_ROOT = Path("/app/task_file")
if not TASK_ROOT.exists():
    TASK_ROOT = Path(__file__).resolve().parents[1] / "environment" / "task_file"

REPO_PATH = TASK_ROOT / "input_data" / "repo"
OUTPUT_PATH = TASK_ROOT / "output_data" / "findings.sarif"

EXPECTED_HASHES = {
    ".github/workflows/ci.yml": "8c293fdcec8c2ebaa693a620fd6998135bb5b385fb6f28774e0b91ef5dbca87b",
    ".github/workflows/deploy-prod.yml": "1f0481a037c70fb6ac597d7129dbfbd2b6e17050d176c0260a944c06d8c837ec",
    "README.md": "3485db03d436bd35ed0fc4b282c91f7abd824aa2d38f55e2c0fccc3f3d308811",
    "assets/network-map.png": "805bd0137da71604332962c20bea4e00e2dc5e736ef2b91f95865728655b343f",
    "docs/access-patterns.md": "c5a21a55ee9b688085299197dfb95f772dc59b24cae7149095b0cf146be9f2fd",
    "infra/iam/breakglass-policy.json": "8624b07cbb0ad334ee91bb94f0576c1633fef8abd0f7dd1a11510ef17e7f6a73",
    "infra/terraform/dev/network.tf": "45bfe75cc7ca1abd359baf90fd317c66a23bc8912cdc336c44496f13d251fec3",
    "infra/terraform/prod/iam.tf": "21ec9eab0d558fce4414798c9b521a716aaefa7ecc46be630aa89f638b408d90",
    "infra/terraform/prod/network.tf": "c8d66a1313c67f57b54d62cd78a9609ca5ed5db1ae67ec3a98efc1b55d6d7260",
    "k8s/dev/sandbox.yaml": "18a810c2d04005dacc59f9488a6df965faa68c91203d50c33360c6b2b30d1d92",
    "k8s/prod/api-deployment.yaml": "60a9bd065dac47d58959aa26314d2fd7efcf7f9440e7b1af9e5981ba51ddb459",
    "k8s/prod/node-debug-daemonset.yaml": "96021c9e893c49734b547e6c495c8671190d475f79a1e2f1b991fd5ffa73695f",
    "scripts/dev-bootstrap.sh": "2198d20bff1f2def174b1e7bfe91145963503652e3f9e6e14e02ddea9ea7dfa6",
    "scripts/install-prod.sh": "e5d2793f3ffd4b194f1705b9e1db1eb4656b867d31f17ff449b62bfbe15959a7",
}


def _load_sarif(path: Path = OUTPUT_PATH) -> dict:
    assert path.exists(), f"SARIF output missing: {path}"
    return json.loads(path.read_text())


def _policy_binary() -> str:
    found = shutil.which("policy-auditor")
    candidates = [found, "/usr/local/bin/policy-auditor", "/app/policy-auditor", "/tmp/policy-auditor"]
    for candidate in candidates:
        if candidate and Path(candidate).exists() and os.access(candidate, os.X_OK):
            return candidate
    raise AssertionError("No executable policy-auditor binary found on PATH, /usr/local/bin, /app, or /tmp")


def _run_auditor(repo: Path, out: Path) -> list[dict[str, object]]:
    binary = _policy_binary()
    result = subprocess.run([binary, str(repo), str(out)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr[-800:]
    assert result.stderr == ""
    assert out.exists(), "policy-auditor did not create SARIF output"
    return load_sarif_results(out)


def _has_finding(findings: list[dict[str, object]], rule: str, file: str, line: int) -> bool:
    return any(
        finding["rule"] == rule
        and finding["file"] == file
        and isinstance(finding["line"], int)
        and abs(finding["line"] - line) <= 1
        for finding in findings
    )


class TestInputIntegrity:
    def test_repo_file_set_is_unchanged(self):
        actual = {str(path.relative_to(REPO_PATH)) for path in REPO_PATH.rglob("*") if path.is_file()}
        assert actual == set(EXPECTED_HASHES), "Input repo files were added, removed, or renamed"

    def test_repo_hashes_are_unchanged(self):
        mismatches = []
        for rel_path, expected in EXPECTED_HASHES.items():
            actual = hashlib.sha256((REPO_PATH / rel_path).read_bytes()).hexdigest()
            if actual != expected:
                mismatches.append(rel_path)
        assert not mismatches, "Input repo files were modified: " + ", ".join(mismatches)


class TestSarifOutput:
    def test_sarif_file_exists(self):
        assert OUTPUT_PATH.exists(), f"Expected output file at {OUTPUT_PATH}"
        assert OUTPUT_PATH.stat().st_size > 0, "findings.sarif is empty"

    def test_sarif_top_level_shape(self):
        data = _load_sarif()
        assert data.get("version") == "2.1.0"
        assert data.get("$schema") == "https://json.schemastore.org/sarif-2.1.0.json"
        assert isinstance(data.get("runs"), list) and data["runs"]
        driver = data["runs"][0].get("tool", {}).get("driver", {})
        assert driver.get("name"), "SARIF tool.driver.name is required"
        rule_ids = {rule.get("id") for rule in driver.get("rules", [])}
        assert EXPECTED_RULES.issubset(rule_ids), "SARIF driver rules must declare all policy rule IDs"

    def test_results_have_required_locations(self):
        data = _load_sarif()
        results = data["runs"][0].get("results", [])
        assert results, "SARIF results must not be empty"
        for idx, result in enumerate(results):
            assert result.get("ruleId") in EXPECTED_RULES, f"result[{idx}] has unknown ruleId"
            assert result.get("message", {}).get("text"), f"result[{idx}] missing message.text"
            locations = result.get("locations", [])
            assert locations, f"result[{idx}] missing locations"
            physical = locations[0].get("physicalLocation", {})
            uri = physical.get("artifactLocation", {}).get("uri", "")
            line = physical.get("region", {}).get("startLine")
            assert uri and not uri.startswith("/"), f"result[{idx}] URI must be relative"
            assert isinstance(line, int) and line > 0, f"result[{idx}] has invalid startLine"

    def test_no_known_near_miss_files_reported(self):
        forbidden_files = {
            ".github/workflows/ci.yml",
            "README.md",
            "assets/network-map.png",
            "docs/access-patterns.md",
            "infra/terraform/dev/network.tf",
            "k8s/dev/sandbox.yaml",
            "scripts/dev-bootstrap.sh",
        }
        for finding in load_sarif_results(OUTPUT_PATH):
            assert finding["file"] not in forbidden_files


class TestScoring:
    def test_public_f1_score_passes_threshold(self):
        result = score(OUTPUT_PATH)
        print("\nPolicy-auditor scoring breakdown:")
        for key in ("true_positives", "false_positives", "false_negatives", "precision", "recall", "f1"):
            print(f"  {key}: {result[key]}")
        assert result["passed"], f"F1 {result['f1']} is below threshold {THRESHOLD}: {result}"

    def test_finding_distribution_is_not_one_rule_only(self):
        counts = {}
        for finding in load_sarif_results(OUTPUT_PATH):
            counts[finding["rule"]] = counts.get(finding["rule"], 0) + 1
        assert len(counts) >= 6, "findings must cover the documented rule families"
        assert statistics.pstdev(counts.values()) > 0.0, "rule distribution should not look like a constant stub"


class TestPolicyAuditorBinary:
    def test_c_source_present_and_no_process_delegation(self):
        if not Path("/app").exists():
            pytest.skip("source-language proof runs inside the task image")
        sources = list(Path("/app").rglob("*.c")) + list(Path("/tmp").rglob("*.c"))
        assert sources, "no C source file found"
        text = "\n".join(p.read_text(errors="ignore") for p in sources)
        banned = ["system(", "popen(", "fork(", "execl(", "execv(", "posix_spawn"]
        assert not any(token in text for token in banned), "C source delegates to a subprocess"

    def test_compiled_binary_present(self):
        if not Path("/app").exists():
            pytest.skip("binary proof runs inside the task image")
        binary = Path(_policy_binary())
        assert binary.read_bytes()[:4] == b"\x7fELF", "policy-auditor is not an ELF binary"

    def test_binary_regenerates_high_scoring_original_output(self, tmp_path):
        regenerated = tmp_path / "regenerated.sarif"
        _run_auditor(REPO_PATH, regenerated)
        regenerated_score = score(regenerated)
        assert regenerated_score["passed"], regenerated_score

    def test_binary_default_invocation_writes_default_output(self):
        if not Path("/app/task_file/input_data/repo").exists():
            pytest.skip("default path check runs inside the task image")
        binary = _policy_binary()
        old_output = OUTPUT_PATH.read_bytes() if OUTPUT_PATH.exists() else None
        if OUTPUT_PATH.exists():
            OUTPUT_PATH.unlink()
        try:
            result = subprocess.run([binary], capture_output=True, text=True, timeout=30)
            assert result.returncode == 0, result.stderr[-800:]
            assert result.stderr == ""
            assert OUTPUT_PATH.exists(), "no-argument run did not create the default SARIF output"
            default_score = score(OUTPUT_PATH)
            assert default_score["passed"], default_score
        finally:
            if old_output is not None:
                OUTPUT_PATH.write_bytes(old_output)

    def test_binary_reacts_to_new_public_admin_rule(self, tmp_path):
        probe_repo = tmp_path / "repo"
        shutil.copytree(REPO_PATH, probe_repo)
        new_file = probe_repo / "infra" / "terraform" / "prod" / "generated-cache.tf"
        new_file.write_text(
            "\n".join(
                [
                    'resource "aws_security_group" "generated_cache" {',
                    "  ingress {",
                    "    from_port   = 0",
                    "    to_port     = 65535",
                    '    protocol    = "tcp"',
                    '    cidr_blocks = ["0.0.0.0/0"]',
                    "  }",
                    "}",
                    "",
                ]
            )
        )
        out = tmp_path / "probe.sarif"
        findings = _run_auditor(probe_repo, out)
        assert _has_finding(findings, "SEC-PUBLIC-ADMIN", "infra/terraform/prod/generated-cache.tf", 6)
        assert out.read_text() != OUTPUT_PATH.read_text(), "scanner output did not change for changed input"


MUTATION_CASES = [
    (
        "terraform_ipv6_redis",
        "infra/terraform/prod/generated-redis.tf",
        'resource "aws_security_group" "redis" {\n  ingress {\n    from_port = 6379\n    to_port = 6379\n    protocol = "tcp"\n    cidr_ipv6_blocks = ["::/0"]\n  }\n}\n',
        ("SEC-PUBLIC-ADMIN", "infra/terraform/prod/generated-redis.tf", 6),
        True,
    ),
    (
        "terraform_https_near_miss",
        "infra/terraform/prod/generated-https.tf",
        'resource "aws_security_group" "web" {\n  ingress {\n    from_port = 443\n    to_port = 443\n    protocol = "tcp"\n    cidr_blocks = ["0.0.0.0/0"]\n  }\n}\n',
        ("SEC-PUBLIC-ADMIN", "infra/terraform/prod/generated-https.tf", 6),
        False,
    ),
    (
        "dev_public_admin_near_miss",
        "infra/terraform/dev/generated-ssh.tf",
        'resource "aws_security_group" "dev" {\n  ingress {\n    from_port = 22\n    to_port = 22\n    protocol = "tcp"\n    cidr_blocks = ["0.0.0.0/0"]\n  }\n}\n',
        ("SEC-PUBLIC-ADMIN", "infra/terraform/dev/generated-ssh.tf", 6),
        False,
    ),
    (
        "terraform_rule_ssh_ipv4",
        "infra/terraform/prod/generated-sg-rule.tf",
        'resource "aws_security_group_rule" "ssh_world" {\n  type = "ingress"\n  from_port = 22\n  to_port = 22\n  protocol = "tcp"\n  cidr_blocks = ["0.0.0.0/0"]\n}\n',
        ("SEC-PUBLIC-ADMIN", "infra/terraform/prod/generated-sg-rule.tf", 6),
        True,
    ),
    (
        "terraform_vpc_rule_ipv6_postgres",
        "infra/terraform/prod/generated-vpc-rule.tf",
        'resource "aws_vpc_security_group_ingress_rule" "postgres_ipv6" {\n  from_port = 5432\n  to_port = 5432\n  ip_protocol = "tcp"\n  cidr_ipv6 = "::/0"\n}\n',
        ("SEC-PUBLIC-ADMIN", "infra/terraform/prod/generated-vpc-rule.tf", 5),
        True,
    ),
    (
        "terraform_rule_https_near_miss",
        "infra/terraform/prod/generated-rule-https.tf",
        'resource "aws_security_group_rule" "web_world" {\n  type = "ingress"\n  from_port = 443\n  to_port = 443\n  protocol = "tcp"\n  cidr_blocks = ["0.0.0.0/0"]\n}\n',
        ("SEC-PUBLIC-ADMIN", "infra/terraform/prod/generated-rule-https.tf", 6),
        False,
    ),
    (
        "terraform_egress_rule_near_miss",
        "infra/terraform/prod/generated-egress-rule.tf",
        'resource "aws_vpc_security_group_egress_rule" "ssh_out" {\n  from_port = 22\n  to_port = 22\n  ip_protocol = "tcp"\n  cidr_ipv4 = "0.0.0.0/0"\n}\n',
        ("SEC-PUBLIC-ADMIN", "infra/terraform/prod/generated-egress-rule.tf", 5),
        False,
    ),
    (
        "terraform_security_group_rule_egress_near_miss",
        "infra/terraform/prod/generated-sg-rule-egress.tf",
        'resource "aws_security_group_rule" "ssh_out" {\n  type = "egress"\n  from_port = 22\n  to_port = 22\n  protocol = "tcp"\n  cidr_blocks = ["0.0.0.0/0"]\n}\n',
        ("SEC-PUBLIC-ADMIN", "infra/terraform/prod/generated-sg-rule-egress.tf", 6),
        False,
    ),
    (
        "iam_json_star",
        "infra/iam/generated-star.json",
        '{\n  "Statement": [{\n    "Effect": "Allow",\n    "Action": "*",\n    "Resource": "*"\n  }]\n}\n',
        ("SEC-IAM-WILDCARD", "infra/iam/generated-star.json", 4),
        True,
    ),
    (
        "iam_json_passrole",
        "infra/iam/generated-passrole.json",
        '{\n  "Statement": [{\n    "Effect": "Allow",\n    "Action": ["iam:PassRole", "ecs:RunTask"],\n    "Resource": "*"\n  }]\n}\n',
        ("SEC-IAM-WILDCARD", "infra/iam/generated-passrole.json", 4),
        True,
    ),
    (
        "iam_hcl_service_star",
        "infra/terraform/prod/generated-iam.tf",
        'data "aws_iam_policy_document" "generated" {\n  statement {\n    effect = "Allow"\n    actions = ["s3:*"]\n    resources = ["*"]\n  }\n}\n',
        ("SEC-IAM-WILDCARD", "infra/terraform/prod/generated-iam.tf", 4),
        True,
    ),
    (
        "iam_read_only_near_miss",
        "infra/iam/generated-readonly.json",
        '{\n  "Statement": [{\n    "Effect": "Allow",\n    "Action": ["s3:GetObject", "logs:GetLogEvents"],\n    "Resource": "*"\n  }]\n}\n',
        ("SEC-IAM-WILDCARD", "infra/iam/generated-readonly.json", 4),
        False,
    ),
    (
        "iam_json_compact_inline",
        "infra/iam/generated-compact.json",
        '{"Statement":[{"Effect":"Allow","Action":"organizations:*","Resource":"*"}]}\n',
        ("SEC-IAM-WILDCARD", "infra/iam/generated-compact.json", 1),
        True,
    ),
    (
        "iam_hcl_mixed_actions",
        "infra/terraform/prod/generated-mixed-iam.tf",
        'data "aws_iam_policy_document" "mixed" {\n  statement {\n    effect = "Allow"\n    actions = [\n      "logs:GetLogEvents",\n      "iam:PassRole",\n    ]\n    resources = ["*"]\n  }\n}\n',
        ("SEC-IAM-WILDCARD", "infra/terraform/prod/generated-mixed-iam.tf", 6),
        True,
    ),
    (
        "iam_deny_star_near_miss",
        "infra/iam/generated-deny-star.json",
        '{\n  "Statement": [{\n    "Effect": "Deny",\n    "Action": "*",\n    "Resource": "*"\n  }]\n}\n',
        ("SEC-IAM-WILDCARD", "infra/iam/generated-deny-star.json", 4),
        False,
    ),
    (
        "k8s_privilege_escalation",
        "k8s/prod/generated-shell.yaml",
        "apiVersion: v1\nkind: Pod\nmetadata:\n  name: prod-shell\n  namespace: production\nspec:\n  containers:\n    - name: shell\n      image: busybox\n      securityContext:\n        allowPrivilegeEscalation: true\n",
        ("SEC-K8S-PRIVILEGED", "k8s/prod/generated-shell.yaml", 11),
        True,
    ),
    (
        "k8s_host_ipc",
        "k8s/prod/generated-hostipc.yaml",
        "apiVersion: v1\nkind: Pod\nmetadata:\n  name: host-ipc\n  namespace: production\nspec:\n  hostIPC: true\n  containers:\n    - name: worker\n      image: busybox\n",
        ("SEC-K8S-HOST-ACCESS", "k8s/prod/generated-hostipc.yaml", 7),
        True,
    ),
    (
        "k8s_dev_privileged_near_miss",
        "k8s/dev/generated-root.yaml",
        "apiVersion: v1\nkind: Pod\nmetadata:\n  name: dev-root\n  namespace: dev\nspec:\n  containers:\n    - name: shell\n      image: busybox\n      securityContext:\n        privileged: true\n",
        ("SEC-K8S-PRIVILEGED", "k8s/dev/generated-root.yaml", 11),
        False,
    ),
    (
        "workflow_pr_target",
        ".github/workflows/generated-prod.yml",
        "name: generated-prod\n\non:\n  pull_request_target:\n    branches: [main]\n\njobs:\n  deploy:\n    environment: production\n    steps:\n      - uses: actions/checkout@v4\n",
        ("SEC-CI-DEPLOY-WRITE", ".github/workflows/generated-prod.yml", 4),
        True,
    ),
    (
        "workflow_unpinned_action",
        ".github/workflows/generated-prod-action.yml",
        "name: generated-prod-action\n\non:\n  workflow_dispatch:\n\njobs:\n  deploy:\n    environment: production\n    steps:\n      - uses: acme/deploy-action@v2\n",
        ("SEC-UNPINNED-ACTION", ".github/workflows/generated-prod-action.yml", 10),
        True,
    ),
    (
        "workflow_name_content_unpinned_action",
        ".github/workflows/release.yml",
        "name: production deploy\n\non:\n  workflow_dispatch:\n\njobs:\n  release:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: acme/deploy-action@main\n",
        ("SEC-UNPINNED-ACTION", ".github/workflows/release.yml", 10),
        True,
    ),
    (
        "workflow_pinned_near_miss",
        ".github/workflows/generated-prod-pinned.yml",
        "name: generated-prod-pinned\n\non:\n  workflow_dispatch:\n\njobs:\n  deploy:\n    environment: production\n    steps:\n      - uses: acme/deploy-action@0123456789abcdef0123456789abcdef01234567\n",
        ("SEC-UNPINNED-ACTION", ".github/workflows/generated-prod-pinned.yml", 10),
        False,
    ),
    (
        "workflow_missing_at_action",
        ".github/workflows/generated-prod-missing-at.yml",
        "name: generated-prod-missing-at\n\non:\n  workflow_dispatch:\n\njobs:\n  deploy:\n    environment: production\n    steps:\n      - uses: acme/deploy-action\n",
        ("SEC-UNPINNED-ACTION", ".github/workflows/generated-prod-missing-at.yml", 10),
        True,
    ),
    (
        "workflow_main_ref_action",
        ".github/workflows/generated-prod-main-ref.yml",
        "name: generated-prod-main-ref\n\non:\n  workflow_dispatch:\n\njobs:\n  deploy:\n    environment: production\n    steps:\n      - uses: acme/deploy-action@main\n",
        ("SEC-UNPINNED-ACTION", ".github/workflows/generated-prod-main-ref.yml", 10),
        True,
    ),
    (
        "shell_curl_exec",
        "scripts/generated-prod.sh",
        "#!/bin/sh\nset -eu\nwget -qO- https://deploy.example.internal/agent.sh | sh\n",
        ("SEC-SHELL-CURL-EXEC", "scripts/generated-prod.sh", 3),
        True,
    ),
    (
        "shell_deploy_path_curl_exec",
        "scripts/deploy.sh",
        "#!/bin/sh\nset -eu\ncurl -fsSL https://deploy.example.internal/agent.sh | /bin/sh\n",
        ("SEC-SHELL-CURL-EXEC", "scripts/deploy.sh", 3),
        True,
    ),
    (
        "shell_bin_bash_exec",
        "scripts/generated-prod-bin-bash.sh",
        "#!/bin/sh\nset -eu\ncurl -fsSL https://deploy.example.internal/agent.sh | /bin/bash\n",
        ("SEC-SHELL-CURL-EXEC", "scripts/generated-prod-bin-bash.sh", 3),
        True,
    ),
    (
        "shell_sudo_sh_exec",
        "scripts/generated-prod-sudo-sh.sh",
        "#!/bin/sh\nset -eu\ncurl -fsSL https://deploy.example.internal/agent.sh | sudo sh\n",
        ("SEC-SHELL-CURL-EXEC", "scripts/generated-prod-sudo-sh.sh", 3),
        True,
    ),
    (
        "docs_shell_near_miss",
        "docs/generated-runbook.md",
        "# Example only\n\ncurl -fsSL https://deploy.example.internal/agent.sh | bash\n",
        ("SEC-SHELL-CURL-EXEC", "docs/generated-runbook.md", 3),
        False,
    ),
]


@pytest.mark.parametrize("name,rel_path,content,expected,should_report", MUTATION_CASES)
def test_generated_compatible_policy_cases(tmp_path, name, rel_path, content, expected, should_report):
    probe_repo = tmp_path / f"repo-{name}"
    shutil.copytree(REPO_PATH, probe_repo)
    target = probe_repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    output = tmp_path / f"{name}.sarif"

    findings = _run_auditor(probe_repo, output)
    rule, file, line = expected
    got = _has_finding(findings, rule, file, line)
    assert got is should_report
