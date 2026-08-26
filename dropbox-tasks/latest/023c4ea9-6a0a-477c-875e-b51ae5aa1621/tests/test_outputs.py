"""Verifier for rutile-privilege-escalation-analyze."""

import json
import shutil
import subprocess
from pathlib import Path

APP = Path("/app")
OUT = APP / "output"
ESCALCTL = Path("/opt/rutile/bin/escalctl")

EXPECTED = json.loads('{"alpha": {"profile": "alpha", "identity_count": 4, "edges": [{"from": "cluster-admin", "to": "vault-crown", "channel": "cloud", "weight": 1}, {"from": "role-admin", "to": "cluster-admin", "channel": "cloud", "weight": 6}, {"from": "alice", "to": "grp-dev", "channel": "group", "weight": 1}, {"from": "alice", "to": "grp-ops", "channel": "group", "weight": 1}, {"from": "bob", "to": "grp-ops", "channel": "group", "weight": 1}, {"from": "contractor", "to": "grp-contractors", "channel": "group", "weight": 4}, {"from": "grp-contractors", "to": "grp-dev", "channel": "group", "weight": 1}, {"from": "grp-contractors", "to": "grp-ops", "channel": "group", "weight": 1}, {"from": "grp-dev", "to": "grp-ops", "channel": "group", "weight": 1}, {"from": "k8s-editor", "to": "cluster-admin", "channel": "k8s", "weight": 1}, {"from": "svc-worker", "to": "k8s-editor", "channel": "k8s", "weight": 9}, {"from": "bob", "to": "role-ops", "channel": "role", "weight": 1}, {"from": "contractor", "to": "role-viewer", "channel": "role", "weight": 7}, {"from": "role-viewer", "to": "role-admin", "channel": "role", "weight": 3}], "chains": [{"entry": "contractor", "target": "vault-crown", "hop_count": 4, "severity": "medium", "path": ["contractor", "role-viewer", "role-admin", "cluster-admin", "vault-crown"]}], "report_digest_hex": "07fab78eb6a65fee5657c9e0d92f9387585361f147676f7e4dec15e9618ab47b"}, "beta": {"profile": "beta", "identity_count": 3, "edges": [{"from": "role-super", "to": "crown-vault", "channel": "cloud", "weight": 8}, {"from": "auditor", "to": "grp-audit", "channel": "group", "weight": 1}, {"from": "dev", "to": "grp-eng", "channel": "group", "weight": 1}, {"from": "auditor", "to": "role-read", "channel": "role", "weight": 1}, {"from": "dev", "to": "role-read", "channel": "role", "weight": 5}, {"from": "role-read", "to": "role-write", "channel": "role", "weight": 9}, {"from": "role-write", "to": "role-super", "channel": "role", "weight": 2}, {"from": "runner", "to": "role-batch", "channel": "role", "weight": 1}], "chains": [{"entry": "dev", "target": "crown-vault", "hop_count": 4, "severity": "medium", "path": ["dev", "role-read", "role-write", "role-super", "crown-vault"]}], "report_digest_hex": "e9ae0904b832c72049d41ec4ab038688a954016f81aa9760a0cba5972da24dd1"}, "gamma": {"profile": "gamma", "identity_count": 3, "edges": [{"from": "grp-shared", "to": "k8s-agg", "channel": "cloud", "weight": 1}, {"from": "k8s-agg", "to": "crown-store", "channel": "cloud", "weight": 9}, {"from": "mesh-entry", "to": "grp-shared", "channel": "cloud", "weight": 1}, {"from": "u1", "to": "grp-alpha", "channel": "group", "weight": 3}, {"from": "k8s-bind", "to": "k8s-agg", "channel": "k8s", "weight": 1}, {"from": "sa-mesh", "to": "k8s-bind", "channel": "k8s", "weight": 9}], "chains": [{"entry": "mesh-entry", "target": "crown-store", "hop_count": 3, "severity": "high", "path": ["mesh-entry", "grp-shared", "k8s-agg", "crown-store"]}], "report_digest_hex": "6a3973e1c341b1b6ce48b079427f063feaafccd3c34f01088dcae41f325c07d8"}}')


def rebuild(profile: str) -> dict:
    """Rebuild escalctl and run analyze export for one profile."""
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(["make", "-C", "/app/environment", "all"], check=True, timeout=300)
    out_path = OUT / "escalation_report.json"
    subprocess.run(
        [
            str(ESCALCTL),
            "analyze",
            "--profile",
            profile,
            "--root",
            "/app/environment/data",
            "--out",
            str(out_path),
        ],
        check=True,
        timeout=60,
    )
    return json.loads(out_path.read_text())


class TestOutputs:
    """Privilege escalation analyzer verifier."""

    def test_alpha_edges(self):
        """Alpha edges must match active groups, role gating, and usage weights."""
        report = rebuild("alpha")
        assert report["edges"] == EXPECTED["alpha"]["edges"]

    def test_alpha_chains(self):
        """Alpha chains must connect entry contractor to crown vault."""
        report = rebuild("alpha")
        assert report["chains"] == EXPECTED["alpha"]["chains"]

    def test_alpha_digest(self):
        """Alpha report_digest_hex must match sorted edge witness."""
        report = rebuild("alpha")
        assert report["report_digest_hex"] == EXPECTED["alpha"]["report_digest_hex"]

    def test_beta_edges(self):
        """Beta edges must include transitive role assumption pairs."""
        report = rebuild("beta")
        assert report["edges"] == EXPECTED["beta"]["edges"]

    def test_beta_chains(self):
        """Beta chains must report shortest hop counts."""
        report = rebuild("beta")
        assert report["chains"] == EXPECTED["beta"]["chains"]

    def test_beta_digest(self):
        """Beta report_digest_hex must match independent witness."""
        report = rebuild("beta")
        assert report["report_digest_hex"] == EXPECTED["beta"]["report_digest_hex"]

    def test_gamma_edges(self):
        """Gamma edges must respect first-match constraints and audit weights."""
        report = rebuild("gamma")
        assert report["edges"] == EXPECTED["gamma"]["edges"]

    def test_gamma_chains(self):
        """Gamma chains must use cloud identity entry flags for entry nodes."""
        report = rebuild("gamma")
        assert report["chains"] == EXPECTED["gamma"]["chains"]

    def test_gamma_digest(self):
        """Gamma report_digest_hex must match independent witness."""
        report = rebuild("gamma")
        assert report["report_digest_hex"] == EXPECTED["gamma"]["report_digest_hex"]

    def test_regenerated_nonempty(self):
        """Regenerated alpha export must list edges and a 64-char witness."""
        report = rebuild("alpha")
        assert len(report["edges"]) > 0
        assert len(report["report_digest_hex"]) == 64
        assert report["profile"] == "alpha"
        assert report["identity_count"] == EXPECTED["alpha"]["identity_count"]

    def test_gamma_k8s_and_cloud_channels(self):
        """Gamma export must include k8s aggregation and cloud federation edges."""
        report = rebuild("gamma")
        channels = {row["channel"] for row in report["edges"]}
        assert "k8s" in channels
        assert "cloud" in channels
