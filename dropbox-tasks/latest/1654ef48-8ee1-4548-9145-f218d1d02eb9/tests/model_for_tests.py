from __future__ import annotations

import json
from pathlib import Path

THRESHOLD = 0.93

EXPECTED_RULES = {
    "SEC-CI-DEPLOY-WRITE",
    "SEC-IAM-WILDCARD",
    "SEC-K8S-HOST-ACCESS",
    "SEC-K8S-PRIVILEGED",
    "SEC-PUBLIC-ADMIN",
    "SEC-SHELL-CURL-EXEC",
    "SEC-UNPINNED-ACTION",
}

GROUND_TRUTH = {
    ("SEC-CI-DEPLOY-WRITE", ".github/workflows/deploy-prod.yml", 4),
    ("SEC-CI-DEPLOY-WRITE", ".github/workflows/deploy-prod.yml", 7),
    ("SEC-UNPINNED-ACTION", ".github/workflows/deploy-prod.yml", 14),
    ("SEC-IAM-WILDCARD", "infra/iam/breakglass-policy.json", 7),
    ("SEC-IAM-WILDCARD", "infra/iam/breakglass-policy.json", 13),
    ("SEC-IAM-WILDCARD", "infra/terraform/prod/iam.tf", 5),
    ("SEC-IAM-WILDCARD", "infra/terraform/prod/iam.tf", 6),
    ("SEC-IAM-WILDCARD", "infra/terraform/prod/iam.tf", 23),
    ("SEC-PUBLIC-ADMIN", "infra/terraform/prod/network.tf", 10),
    ("SEC-PUBLIC-ADMIN", "infra/terraform/prod/network.tf", 26),
    ("SEC-K8S-HOST-ACCESS", "k8s/prod/api-deployment.yaml", 16),
    ("SEC-K8S-PRIVILEGED", "k8s/prod/api-deployment.yaml", 21),
    ("SEC-K8S-PRIVILEGED", "k8s/prod/api-deployment.yaml", 22),
    ("SEC-K8S-HOST-ACCESS", "k8s/prod/api-deployment.yaml", 28),
    ("SEC-K8S-HOST-ACCESS", "k8s/prod/node-debug-daemonset.yaml", 15),
    ("SEC-SHELL-CURL-EXEC", "scripts/install-prod.sh", 4),
}


def load_sarif_results(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text())
    results = data.get("runs", [{}])[0].get("results", [])
    parsed = []
    for result in results:
        physical = result.get("locations", [{}])[0].get("physicalLocation", {})
        parsed.append(
            {
                "rule": result.get("ruleId"),
                "file": physical.get("artifactLocation", {}).get("uri"),
                "line": physical.get("region", {}).get("startLine"),
                "message": result.get("message", {}).get("text"),
            }
        )
    return parsed


def score(path: Path, truth: set[tuple[str, str, int]] = GROUND_TRUTH) -> dict[str, object]:
    findings = load_sarif_results(path)
    used_truth: set[tuple[str, str, int]] = set()
    true_positives = 0
    false_positives = 0

    for finding in findings:
        rule = finding["rule"]
        file = finding["file"]
        line = finding["line"]
        matched = None
        if isinstance(rule, str) and isinstance(file, str) and isinstance(line, int):
            for expected in truth:
                if expected in used_truth:
                    continue
                exp_rule, exp_file, exp_line = expected
                if rule == exp_rule and file == exp_file and abs(line - exp_line) <= 1:
                    matched = expected
                    break
        if matched:
            used_truth.add(matched)
            true_positives += 1
        else:
            false_positives += 1

    false_negatives = len(truth) - true_positives
    precision = true_positives / (true_positives + false_positives) if true_positives + false_positives else 0.0
    recall = true_positives / (true_positives + false_negatives) if true_positives + false_negatives else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "passed": f1 >= THRESHOLD and precision >= THRESHOLD and recall >= THRESHOLD,
    }
