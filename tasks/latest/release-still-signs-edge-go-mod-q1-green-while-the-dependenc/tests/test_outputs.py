#!/usr/bin/env python3
"""Behavioral verifier for the Go module proxy integrity gate."""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from protected_integrity import assert_protected_integrity
from proxy_helper import CONFLICT_IDS, compute_chain_digest, primary_expected
from reference_audit import expected_integrity

APP = Path("/app")
OUT = APP / "output"
REPORT = OUT / "integrity_report.json"
CERT = OUT / "integrity_certificate.json"
REPRO = OUT / "repro_digest_export.json"
MANIFEST = APP / "data/manifest.json"
CONFLICT_REPORT = APP / "data/conflict_report.json"
HOLDOUT_MANIFEST = Path("/tests/holdout/data/manifest.json")
RETRACTMATCH = APP / "bin/retractmatch"
GOFLOOR = APP / "bin/gofloor"
MODGATE = APP / "bin/modgate"


def run_modgate(manifest: Path, out_dir: Path) -> subprocess.CompletedProcess[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        ["modgate", "--manifest", str(manifest), "--out", str(out_dir)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )


def _is_elf(path: Path) -> bool:
    return path.read_bytes()[:4] == b"\x7fELF"


class TestCorpusAndSetup(unittest.TestCase):
    def test_protected_integrity(self):
        assert_protected_integrity()

    def test_conflict_report_lists_escalated_modules(self):
        payload = json.loads(CONFLICT_REPORT.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(payload["conflicts"]), 6)
        reported = {row["mod_id"] for row in payload["conflicts"]}
        for mid in CONFLICT_IDS:
            self.assertIn(mid, reported)

    def test_binaries_are_elf(self):
        for path in (MODGATE, RETRACTMATCH, GOFLOOR):
            self.assertTrue(path.exists(), f"missing {path}")
            self.assertTrue(_is_elf(path), f"not elf: {path}")
        exact = subprocess.run(
            [str(RETRACTMATCH), "v1.18.1", "v1.18.1"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(exact.returncode, 0)
        self.assertEqual(exact.stdout.strip(), "match")
        interval = subprocess.run(
            [str(RETRACTMATCH), "v0.4.36", "[v0.4.36, v0.4.37]"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(interval.returncode, 0)
        floor_ok = subprocess.run(
            [str(GOFLOOR), "1.21.0", "1.18.0"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(floor_ok.returncode, 0)
        floor_bad = subprocess.run(
            [str(GOFLOOR), "1.21.0", "1.22.0"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertNotEqual(floor_bad.returncode, 0)


class TestModgateExecution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected_rows, cls.expected_cert, cls.expected_repro = primary_expected()
        cls.proc = run_modgate(MANIFEST, OUT)
        cls.report = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else []
        cls.cert = json.loads(CERT.read_text(encoding="utf-8")) if CERT.exists() else {}
        cls.repro = json.loads(REPRO.read_text(encoding="utf-8")) if REPRO.exists() else {}

    def test_cli_success(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)
        self.assertIn("MODGATE_OK", self.proc.stdout)

    def test_certificate_status(self):
        self.assertEqual(self.cert.get("status"), "MODGATE_OK")

    def test_record_count(self):
        self.assertEqual(self.cert.get("record_count"), self.expected_cert["record_count"])
        self.assertEqual(len(self.report), len(self.expected_rows))

    def test_report_sorted(self):
        ids = [row["mod_id"] for row in self.report]
        self.assertEqual(ids, sorted(ids))

    def test_gate_status(self):
        self.assertEqual(self.cert.get("gate_status"), self.expected_cert["gate_status"])

    def test_counters(self):
        for key in (
            "live_refreshes",
            "waiver_hits",
            "stale_overrides",
            "retract_hits",
            "checksum_failures",
            "toolchain_blocks",
            "exclude_skips",
            "transitive_warns",
        ):
            self.assertEqual(self.cert.get(key), self.expected_cert[key], key)

    def test_chain_digest_matches_report(self):
        self.assertRegex(self.cert.get("chain_digest", ""), r"^[0-9a-f]{64}$")
        self.assertEqual(self.cert.get("chain_digest"), compute_chain_digest(self.report))

    def test_export_digest_inv6(self):
        self.assertEqual(self.cert.get("export_digest"), self.repro.get("export_digest"))
        self.assertEqual(self.repro.get("export_digest"), self.expected_repro["export_digest"])


class TestLiveProxyIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected_rows, cls.expected_cert, cls.expected_repro = primary_expected()
        run_modgate(MANIFEST, OUT)
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))
        cls.cert = json.loads(CERT.read_text(encoding="utf-8"))
        cls.repro = json.loads(REPRO.read_text(encoding="utf-8"))
        cls.by_id = {row["mod_id"]: row for row in cls.report}
        cls.res_by_id = {row["mod_id"]: row for row in cls.cert.get("resolutions", [])}

    def test_conflict_live_source(self):
        for mid in CONFLICT_IDS:
            self.assertEqual(self.by_id[mid]["resolve_source"], "proxy_live")

    def test_dual_refresh_predicates(self):
        self.assertTrue(self.by_id["MOD-010"]["refresh_retract"])
        self.assertFalse(self.by_id["MOD-010"]["refresh_sum"])
        self.assertTrue(self.by_id["MOD-015"]["refresh_retract"])
        self.assertTrue(self.by_id["MOD-015"]["refresh_sum"])

    def test_full_oracle_match(self):
        for exp in self.expected_rows:
            got = self.by_id[exp["mod_id"]]
            for key in (
                "module_path",
                "version",
                "member",
                "linkage",
                "retracted",
                "checksum_ok",
                "go_floor_ok",
                "excluded",
                "effective_violation",
                "gate_action",
                "policy_basis",
                "resolve_source",
                "block_reason",
                "declared_hash",
                "live_hash",
                "refresh_retract",
                "refresh_sum",
            ):
                self.assertEqual(got[key], exp[key], f"{exp['mod_id']}.{key}")

    def test_certificate_counters_match_oracle(self):
        for key in (
            "gate_status",
            "live_refreshes",
            "waiver_hits",
            "stale_overrides",
            "retract_hits",
            "checksum_failures",
            "toolchain_blocks",
            "exclude_skips",
            "transitive_warns",
            "chain_digest",
            "export_digest",
            "module_batch_id",
            "policy_track",
            "toolchain_declared",
        ):
            self.assertEqual(self.cert.get(key), self.expected_cert[key], key)
        self.assertEqual(self.cert.get("member_rollups"), self.expected_cert["member_rollups"])

    def test_inv3_resolutions_mirror(self):
        for row in self.report:
            res = self.res_by_id[row["mod_id"]]
            self.assertEqual(res["policy_basis"], row["policy_basis"])
            self.assertEqual(res["resolve_source"], row["resolve_source"])
            self.assertEqual(res["gate_action"], row["gate_action"])

    def test_direct_retract_blocks(self):
        for mid in ("MOD-010",):
            self.assertEqual(self.by_id[mid]["linkage"], "direct")
            self.assertTrue(self.by_id[mid]["retracted"])
            self.assertEqual(self.by_id[mid]["gate_action"], "block")
            self.assertEqual(self.by_id[mid]["policy_basis"], "retract_block")

    def test_checksum_only_conflict_not_retract_live(self):
        """checksumdb_drift-only pin must not inherit live retract posture."""
        row = self.by_id["MOD-013"]
        self.assertFalse(row["refresh_retract"])
        self.assertTrue(row["refresh_sum"])
        self.assertFalse(row["retracted"])
        self.assertTrue(row["checksum_ok"])
        self.assertEqual(row["policy_basis"], "live_refresh")
        self.assertEqual(row["gate_action"], "pass")

    def test_member_rollups(self):
        rollups = {r["member"]: r for r in self.cert.get("member_rollups", [])}
        self.assertEqual(set(rollups), {"edge-api", "edge-worker", "edge-admin"})
        for member, rollup in rollups.items():
            count = sum(1 for row in self.report if row["member"] == member)
            self.assertEqual(rollup["pin_count"], count)
            status = "pass"
            for row in self.report:
                if row["member"] != member:
                    continue
                if row["gate_action"] == "block":
                    status = "block"
                    break
                if row["gate_action"] == "warn" and status == "pass":
                    status = "warn"
            self.assertEqual(rollup["gate_status"], status)

    def test_transitive_retract_warns(self):
        row = self.by_id["MOD-011"]
        self.assertEqual(row["linkage"], "transitive")
        self.assertTrue(row["retracted"])
        self.assertEqual(row["gate_action"], "warn")
        self.assertEqual(row["policy_basis"], "retract_warn_transitive")

    def test_waived_retracted_warns(self):
        for mid in ("MOD-012", "MOD-014"):
            row = self.by_id[mid]
            self.assertTrue(row["retracted"])
            self.assertEqual(row["gate_action"], "warn")
            self.assertEqual(row["policy_basis"], "waiver_digest")
            self.assertEqual(row["block_reason"], "retract_notice")

    def test_checksum_and_retract_dual(self):
        row = self.by_id["MOD-015"]
        self.assertTrue(row["retracted"])
        self.assertFalse(row["checksum_ok"])
        self.assertEqual(row["block_reason"], "retract_notice")
        self.assertEqual(row["gate_action"], "block")

    def test_exclude_skips_toolchain(self):
        row = self.by_id["MOD-003"]
        self.assertTrue(row["excluded"])
        self.assertFalse(row["go_floor_ok"])
        self.assertEqual(row["policy_basis"], "exclude_skip")
        self.assertEqual(row["gate_action"], "pass")
        self.assertFalse(row["effective_violation"])

    def test_toolchain_block(self):
        row = self.by_id["MOD-005"]
        self.assertFalse(row["excluded"])
        self.assertFalse(row["go_floor_ok"])
        self.assertEqual(row["policy_basis"], "toolchain_block")
        self.assertEqual(row["gate_action"], "block")
        self.assertEqual(row["block_reason"], "toolchain_floor")

    def test_repro_export_matches(self):
        self.assertEqual(self.repro.get("module_batch_id"), self.expected_repro["module_batch_id"])
        self.assertEqual(len(self.repro.get("pin_digests", [])), len(self.expected_repro["pin_digests"]))
        got = {p["mod_id"]: p["row_digest"] for p in self.repro["pin_digests"]}
        exp = {p["mod_id"]: p["row_digest"] for p in self.expected_repro["pin_digests"]}
        self.assertEqual(got, exp)


class TestHoldoutGeneralization(unittest.TestCase):
    def test_holdout_manifest(self):
        self.assertTrue(HOLDOUT_MANIFEST.exists())
        out = Path("/tmp/modgate_holdout_out")
        if out.exists():
            shutil.rmtree(out)
        proc = run_modgate(HOLDOUT_MANIFEST, out)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("MODGATE_OK", proc.stdout)
        report = json.loads((out / "integrity_report.json").read_text(encoding="utf-8"))
        cert = json.loads((out / "integrity_certificate.json").read_text(encoding="utf-8"))
        repro = json.loads((out / "repro_digest_export.json").read_text(encoding="utf-8"))
        expected_rows, expected_cert, expected_repro = expected_integrity(HOLDOUT_MANIFEST)
        by_id = {r["mod_id"]: r for r in report}
        for exp in expected_rows:
            got = by_id[exp["mod_id"]]
            for key in (
                "retracted",
                "checksum_ok",
                "go_floor_ok",
                "excluded",
                "gate_action",
                "policy_basis",
                "resolve_source",
                "block_reason",
            ):
                self.assertEqual(got[key], exp[key], f"holdout {exp['mod_id']}.{key}")
        for key in (
            "gate_status",
            "live_refreshes",
            "waiver_hits",
            "stale_overrides",
            "toolchain_blocks",
            "exclude_skips",
            "transitive_warns",
            "chain_digest",
            "export_digest",
        ):
            self.assertEqual(cert.get(key), expected_cert[key], f"holdout cert.{key}")
        self.assertEqual(repro.get("export_digest"), expected_repro["export_digest"])


if __name__ == "__main__":
    unittest.main()
