"""Verifier tests for foldctl stratified cross-validation fold assembler."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import re
import shutil
import tempfile
from pathlib import Path

import fold_ref as ref


class TestFoldAssembler:
    def setup_method(self) -> None:
        """Run stock assemble before each test unless overridden."""
        ref.reset_var()
        self.proc = ref.run_assemble()
        self.stdout = ref.load_stdout_json(self.proc)
        self.manifest = ref.load_manifest()
        self.rows = ref.read_csv_rows(ref.STOCK_DATASET, ref.STOCK_LABEL)
        self.assignment = ref.reference_assign(self.rows, ref.STOCK_FOLDS)
        self.label_counts = ref.reference_label_counts(self.rows, self.assignment)

    def test_stock_exit_zero(self) -> None:
        """Stock assemble exits zero."""
        assert self.proc.returncode == 0

    def test_stock_ok_true(self) -> None:
        """Stock stdout ok flag is true."""
        assert self.stdout["ok"] is True

    def test_stock_row_count(self) -> None:
        """Stock row_count matches cohort size."""
        assert self.stdout["row_count"] == len(self.rows)

    def test_stock_fold_count(self) -> None:
        """Stock fold_count matches requested folds."""
        assert self.stdout["fold_count"] == ref.STOCK_FOLDS

    def test_stock_label_column(self) -> None:
        """Stock label_column echoes CLI flag."""
        assert self.stdout["label_column"] == ref.STOCK_LABEL

    def test_stock_staged_path_absolute(self) -> None:
        """Stdout staged_path is absolute."""
        assert Path(self.stdout["staged_path"]).is_absolute()

    def test_stock_staged_path_value(self) -> None:
        """Stdout staged_path points at fold work file."""
        assert self.stdout["staged_path"] == str(ref.STAGED_PATH.resolve())

    def test_stock_staged_file_exists(self) -> None:
        """Staged CSV exists on disk."""
        assert ref.STAGED_PATH.is_file()

    def test_stock_manifest_file_exists(self) -> None:
        """Manifest JSON exists on disk."""
        assert ref.MANIFEST_PATH.is_file()

    def test_manifest_matches_stdout_core_fields(self) -> None:
        """Manifest core fields mirror stdout."""
        for key in (
            "ok",
            "row_count",
            "fold_count",
            "label_column",
            "fold_digest",
            "balance",
            "cohort_checksum",
            "assignment_seal",
            "balance_anchor",
            "manifest_seal",
            "staged_fingerprint",
            "quorum_witness",
            "stratum_spread_digest",
            "band_anchor",
            "rotation_epoch",
            "receipt_chain",
            "epoch_seal",
            "ledger_root",
            "fold_parity_digest",
            "label_coverage_seal",
            "holdout_fold_id",
            "evaluation_seal",
            "stratum_entropy_hint",
            "assemble_attestation",
            "fold_load_skew",
            "label_cardinality",
            "cohort_span_digest",
            "balance_coupler",
            "kit_closure",
            "run_chain_digest",
            "class_prior_seal",
            "fold_split_witness",
            "holdout_epoch_coupler",
            "stratum_stability_index",
            "train_fold_mask",
            "label_pair_cooccurrence",
            "balance_drift_witness",
            "epoch_manifest_binder",
            "holdout_exclusion_seal",
            "fold_kit_seal",
            "fold_coverage_lattice",
            "holdout_train_tension",
            "skew_prior_witness",
            "epoch_receipt_binder",
            "fold_kit_outer_seal",
        ):
            assert self.manifest[key] == self.stdout[key]

    def test_stdout_includes_staged_path(self) -> None:
        """Stdout includes staged_path not required on disk manifest."""
        assert "staged_path" in self.stdout
        assert "staged_path" not in self.manifest

    def test_folds_array_length(self) -> None:
        """Fold list length equals fold_count."""
        assert len(self.stdout["folds"]) == ref.STOCK_FOLDS

    def test_fold_ids_zero_based_sequence(self) -> None:
        """Fold ids are 0..K-1."""
        assert [f["fold_id"] for f in self.stdout["folds"]] == list(
            range(ref.STOCK_FOLDS)
        )

    def test_all_rows_assigned_once(self) -> None:
        """Every cohort id appears in exactly one fold."""
        assigned = ref.all_row_ids(self.stdout)
        expected = sorted((row_id for row_id, _ in self.rows), key=int)
        assert sorted(assigned, key=int) == expected
        assert len(assigned) == len(set(assigned))

    def test_row_ids_sorted_within_folds(self) -> None:
        """Each fold row_ids list is sorted ascending by numeric id."""
        for fold in self.stdout["folds"]:
            ids = [int(row_id) for row_id in fold["row_ids"]]
            assert ids == sorted(ids)

    def test_stratified_assignment_fold_zero(self) -> None:
        """Fold zero row ids match reference stratified round-robin."""
        fold = ref.fold_map(self.stdout)[0]
        assert fold["row_ids"] == self.assignment[0]

    def test_stratified_assignment_fold_one(self) -> None:
        """Fold one row ids match reference stratified round-robin."""
        fold = ref.fold_map(self.stdout)[1]
        assert fold["row_ids"] == self.assignment[1]

    def test_stratified_assignment_fold_two(self) -> None:
        """Fold two row ids match reference stratified round-robin."""
        fold = ref.fold_map(self.stdout)[2]
        assert fold["row_ids"] == self.assignment[2]

    def test_stratified_assignment_fold_three(self) -> None:
        """Fold three row ids match reference stratified round-robin."""
        fold = ref.fold_map(self.stdout)[3]
        assert fold["row_ids"] == self.assignment[3]

    def test_stratified_assignment_fold_four(self) -> None:
        """Fold four row ids match reference stratified round-robin."""
        fold = ref.fold_map(self.stdout)[4]
        assert fold["row_ids"] == self.assignment[4]

    def test_label_counts_fold_zero(self) -> None:
        """Fold zero label_counts map matches reference."""
        fold = ref.fold_map(self.stdout)[0]
        assert fold["label_counts"] == self.label_counts[0]

    def test_label_counts_fold_two(self) -> None:
        """Fold two label_counts map matches reference."""
        fold = ref.fold_map(self.stdout)[2]
        assert fold["label_counts"] == self.label_counts[2]

    def test_fold_digest_hex_format(self) -> None:
        """fold_digest is lowercase SHA-256 hex."""
        assert re.fullmatch(r"[0-9a-f]{64}", self.stdout["fold_digest"])

    def test_fold_digest_matches_reference(self) -> None:
        """fold_digest matches reference digest algorithm."""
        expected = ref.reference_digest(self.label_counts)
        assert self.stdout["fold_digest"] == expected

    def test_balance_max_label_skew(self) -> None:
        """balance.max_label_skew matches reference computation."""
        expected = ref.reference_balance(self.rows, ref.STOCK_FOLDS)
        assert (
            abs(self.stdout["balance"]["max_label_skew"] - expected["max_label_skew"])
            < 1e-9
        )

    def test_balance_min_fold_rows(self) -> None:
        """balance.min_fold_rows matches reference computation."""
        expected = ref.reference_balance(self.rows, ref.STOCK_FOLDS)
        assert self.stdout["balance"]["min_fold_rows"] == expected["min_fold_rows"]

    def test_balance_max_fold_rows(self) -> None:
        """balance.max_fold_rows matches reference computation."""
        expected = ref.reference_balance(self.rows, ref.STOCK_FOLDS)
        assert self.stdout["balance"]["max_fold_rows"] == expected["max_fold_rows"]

    def test_balance_label_columns_sorted(self) -> None:
        """balance.label_columns is sorted unique label list."""
        labels = self.stdout["balance"]["label_columns"]
        assert labels == sorted(labels)
        assert len(labels) == len(set(labels))

    def test_balance_label_columns_content(self) -> None:
        """balance.label_columns lists all cohort labels."""
        expected = ref.reference_balance(self.rows, ref.STOCK_FOLDS)
        assert self.stdout["balance"]["label_columns"] == expected["label_columns"]

    def test_balance_min_le_max(self) -> None:
        """min_fold_rows never exceeds max_fold_rows."""
        balance = self.stdout["balance"]
        assert balance["min_fold_rows"] <= balance["max_fold_rows"]

    def test_stage_copies_bytes_unchanged(self) -> None:
        """stage_cohort.sh preserves dataset bytes."""
        assert ref.STAGED_PATH.read_bytes() == ref.STOCK_DATASET.read_bytes()

    def test_stage_missing_id_column(self) -> None:
        """stage_cohort.sh rejects headers without id."""
        ref.reset_var()
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.csv"
            bad.write_text("strata,score\nalpha,1\n", encoding="utf-8")
            proc = ref.run_stage(bad, ref.STOCK_LABEL)
            assert proc.returncode != 0

    def test_stage_missing_label_column(self) -> None:
        """stage_cohort.sh rejects headers without label column."""
        ref.reset_var()
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.csv"
            bad.write_text("id,score\n1,1\n", encoding="utf-8")
            proc = ref.run_stage(bad, ref.STOCK_LABEL)
            assert proc.returncode != 0

    def test_custom_folds_three(self) -> None:
        """assemble supports alternate fold counts."""
        ref.reset_var()
        proc = ref.run_assemble(folds=3)
        payload = ref.load_stdout_json(proc)
        assert proc.returncode == 0
        assert payload["fold_count"] == 3
        assert len(payload["folds"]) == 3

    def test_custom_folds_three_assignment(self) -> None:
        """Three-fold assignment matches reference algorithm."""
        ref.reset_var()
        proc = ref.run_assemble(folds=3)
        payload = ref.load_stdout_json(proc)
        expected = ref.reference_assign(self.rows, 3)
        for fold_id, row_ids in expected.items():
            assert ref.fold_map(payload)[fold_id]["row_ids"] == row_ids

    def test_custom_folds_three_digest(self) -> None:
        """Three-fold digest matches reference algorithm."""
        ref.reset_var()
        proc = ref.run_assemble(folds=3)
        payload = ref.load_stdout_json(proc)
        expected = ref.reference_digest_from_rows(self.rows, 3)
        assert payload["fold_digest"] == expected

    def test_each_fold_has_label_counts_object(self) -> None:
        """Every fold exposes a label_counts object."""
        for fold in self.stdout["folds"]:
            assert isinstance(fold["label_counts"], dict)
            assert sum(fold["label_counts"].values()) == len(fold["row_ids"])

    def test_manifest_folds_sorted_by_fold_id(self) -> None:
        """Manifest folds array is sorted by fold_id."""
        ids = [fold["fold_id"] for fold in self.manifest["folds"]]
        assert ids == sorted(ids)

    def test_stdout_valid_json(self) -> None:
        """Stdout body is parseable JSON."""
        parsed = json.loads(self.proc.stdout)
        assert isinstance(parsed, dict)

    def test_manifest_valid_json(self) -> None:
        """Manifest file is parseable JSON."""
        parsed = json.loads(ref.MANIFEST_PATH.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict)

    def test_stock_fold_two_row_count(self) -> None:
        """Fold two row count matches reference size."""
        assert len(ref.fold_map(self.stdout)[2]["row_ids"]) == len(self.assignment[2])

    def test_stock_fold_four_row_count(self) -> None:
        """Fold four row count matches reference size."""
        assert len(ref.fold_map(self.stdout)[4]["row_ids"]) == len(self.assignment[4])

    def test_digest_changes_with_fold_count(self) -> None:
        """Different K yields different fold_digest."""
        ref.reset_var()
        proc = ref.run_assemble(folds=3)
        digest_three = ref.load_stdout_json(proc)["fold_digest"]
        ref.reset_var()
        proc = ref.run_assemble(folds=5)
        digest_five = ref.load_stdout_json(proc)["fold_digest"]
        assert digest_three != digest_five

    def test_dynamic_bypass_check(self) -> None:
        """Novel cohort data changes assignment and digest."""
        ref.reset_var()
        random.seed(99173)
        labels = ["north", "south", "east"]
        with tempfile.TemporaryDirectory() as tmp:
            dynamic = Path(tmp) / "dynamic.csv"
            with dynamic.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 19):
                    label = labels[idx % len(labels)]
                    writer.writerow([idx, label, f"0.{idx:02d}"])
                    rows.append((str(idx), label))
            proc = ref.run_assemble(dataset=dynamic, folds=4, label="strata")
            assert proc.returncode == 0
            payload = ref.load_stdout_json(proc)
            expected = ref.reference_assign(rows, 4)
            for fold_id, row_ids in expected.items():
                assert ref.fold_map(payload)[fold_id]["row_ids"] == row_ids
            expected_digest = ref.reference_digest_from_rows(rows, 4)
            assert payload["fold_digest"] == expected_digest
            assert payload["row_count"] == len(rows)

    def test_assemble_uses_verifier_java_jar(self) -> None:
        """Primary assemble runner targets the Maven jar via Java under the guard."""
        assert ref.BIN[0] == str(ref.JAVA_BIN)
        assert ref.BIN[1] == "-jar"
        assert ref.BIN[2] == str(ref.ASSEMBLE_JAR)
        assert ref.ASSEMBLE_JAR.is_file()
        assert ref.JAVA_BIN.is_file()

    def test_public_pom_integrity(self) -> None:
        """Documented /app/pom.xml must still define the fold-assembler shade build."""
        ref.assert_public_pom_integrity()

    def test_foldctl_integrity_and_stock_run(self) -> None:
        """Public foldctl must launch the jar; one stock assemble must succeed via it."""
        ref.assert_foldctl_integrity()
        ref.reset_var()
        proc = ref.run_assemble_via_foldctl()
        assert proc.returncode == 0, proc.stderr
        payload = ref.load_stdout_json(proc)
        rows = ref.read_csv_rows(ref.STOCK_DATASET, ref.STOCK_LABEL)
        expected = ref.reference_assign(rows, ref.STOCK_FOLDS)
        for fold_id, row_ids in expected.items():
            assert ref.fold_map(payload)[fold_id]["row_ids"] == row_ids
        assert payload["fold_digest"] == ref.reference_digest_from_rows(
            rows, ref.STOCK_FOLDS
        )
        assert payload["row_count"] == len(rows)
        assert "manifest_seal" in payload
        assert payload["staged_path"] == str(ref.STAGED_PATH)
        receipt = ref.read_receipt_lines()
        assert receipt
        assert receipt[-1]["manifest_seal"] == payload["manifest_seal"]
        assert receipt[-1]["fold_digest"] == payload["fold_digest"]

    def test_public_pom_build_and_foldctl_nonstock_args(self) -> None:
        """Build with the public POM and run foldctl on a non-stock dataset/folds/label."""
        public_jar = ref.build_jar_with_public_pom()
        target = ref.ASSEMBLE_JAR
        backup = Path("/logs/verifier/fold-assembler-verifier-backup.jar")
        shutil.copy2(target, backup)
        alt_dataset = Path("/app/var/alt_cohort_public_pom.csv")
        alt_label = "class"
        alt_folds = 3
        alt_dataset.write_text(
            "id,class,score\n"
            "1,x,0.1\n2,y,0.2\n3,x,0.3\n4,y,0.4\n"
            "5,x,0.5\n6,y,0.6\n7,x,0.7\n8,y,0.8\n"
            "9,x,0.9\n10,y,1.0\n11,x,1.1\n12,y,1.2\n",
            encoding="utf-8",
        )
        os.chmod(alt_dataset, 0o644)
        try:
            shutil.copy2(public_jar, target)
            os.chmod(target, 0o644)
            ref.reset_var()
            proc = ref.run_assemble_via_foldctl(
                dataset=alt_dataset, folds=alt_folds, label=alt_label
            )
            assert proc.returncode == 0, proc.stderr
            payload = ref.load_stdout_json(proc)
            rows = ref.read_csv_rows(alt_dataset, alt_label)
            expected = ref.reference_assign(rows, alt_folds)
            assert payload["fold_count"] == alt_folds
            assert payload["label_column"] == alt_label
            assert payload["row_count"] == len(rows)
            for fold_id, row_ids in expected.items():
                assert ref.fold_map(payload)[fold_id]["row_ids"] == row_ids
            assert payload["fold_digest"] == ref.reference_digest_from_rows(
                rows, alt_folds
            )
        finally:
            if backup.is_file():
                shutil.copy2(backup, target)
                backup.unlink(missing_ok=True)
            alt_dataset.unlink(missing_ok=True)

    def test_verifier_build_uses_owned_pom_not_app_pom(self) -> None:
        """test.sh must build from verifier-pom in a sandbox, not /app/pom.xml."""
        script = Path("/tests/test.sh").read_text(encoding="utf-8")
        assert "verifier-pom.xml" in script
        assert "/logs/verifier/maven-build" in script
        assert "mvn" in script and "-f /app/pom.xml" not in script
        assert Path("/tests/verifier-pom.xml").is_file()
        pom = Path("/tests/verifier-pom.xml").read_text(encoding="utf-8")
        assert "/tests" not in pom
        assert "fold-assembler" in pom

    def test_workflow_check_requires_successful_exec_not_name_only(self) -> None:
        """Workflow match needs real executable pathname + script argv positions."""
        fake = (
            '1000 write(1, "stage_cohort.sh fold_balance.R", 30) = 30\n'
            "1000 +++ exited with 0 +++\n"
        )
        missing = ref._missing_successful_workflow_execs(fake)
        assert missing == ["stage_cohort.sh", "fold_balance.R"]
        # Script path as a decoy argument must not satisfy the R workflow.
        decoy = (
            '1500 execve("/bin/true", '
            '["true", "/app/r/fold_balance.R"], 0x7 /* 0 vars */) = 0\n'
            "1500 +++ exited with 0 +++\n"
            '1501 execve("/bin/true", '
            '["true", "/app/scripts/stage_cohort.sh"], 0x7 /* 0 vars */) = 0\n'
            "1501 +++ exited with 0 +++\n"
        )
        assert ref._missing_successful_workflow_execs(decoy) == [
            "stage_cohort.sh",
            "fold_balance.R",
        ]
        # argv[0] spoofed as Rscript/bash while another program was executed.
        spoof = (
            '1600 execve("/bin/true", '
            '["Rscript", "/app/r/fold_balance.R", '
            '"/app/var/fold_manifest.json"], 0x7 /* 0 vars */) = 0\n'
            "1600 +++ exited with 0 +++\n"
            '1601 execve("/bin/true", '
            '["bash", "/app/scripts/stage_cohort.sh", "/app/var/x.csv", '
            '"/app/var/fold_work", "strata"], 0x7 /* 0 vars */) = 0\n'
            "1601 +++ exited with 0 +++\n"
        )
        assert ref._missing_successful_workflow_execs(spoof) == [
            "stage_cohort.sh",
            "fold_balance.R",
        ]
        # Relative "Rscript" argv under a shell must not count — need absolute …/Rscript.
        relative_rscript = (
            '1700 execve("/usr/bin/bash", '
            '["bash", "Rscript", "/app/r/fold_balance.R", '
            '"/app/var/fold_manifest.json"], 0x7 /* 0 vars */) = 0\n'
            "1700 +++ exited with 0 +++\n"
            '1701 execve("/usr/bin/bash", '
            '["bash", "/app/scripts/stage_cohort.sh", "/app/var/x.csv", '
            '"/app/var/fold_work", "strata"], 0x7 /* 0 vars */) = 0\n'
            "1701 +++ exited with 0 +++\n"
        )
        assert ref._missing_successful_workflow_execs(relative_rscript) == [
            "fold_balance.R",
        ]
        # env with a bare Rscript name (not an absolute path) must not count.
        env_relative = (
            '1800 execve("/usr/bin/bash", '
            '["bash", "/app/scripts/stage_cohort.sh", "/app/var/x.csv", '
            '"/app/var/fold_work", "strata"], 0x7 /* 0 vars */) = 0\n'
            "1800 +++ exited with 0 +++\n"
            '1801 execve("/usr/bin/env", '
            '["env", "Rscript", "/app/r/fold_balance.R", '
            '"/app/var/fold_manifest.json"], 0x7 /* 0 vars */) = 0\n'
            "1801 +++ exited with 0 +++\n"
        )
        assert ref._missing_successful_workflow_execs(env_relative) == [
            "fold_balance.R",
        ]
        good = (
            '2000 execve("/usr/bin/bash", '
            '["bash", "/app/scripts/stage_cohort.sh", "/app/var/x.csv", '
            '"/app/var/fold_work", "strata"], 0x7 /* 0 vars */) = 0\n'
            "2000 +++ exited with 0 +++\n"
            '2001 execve("/usr/bin/Rscript", '
            '["Rscript", "/app/r/fold_balance.R", '
            '"/app/var/fold_manifest.json"], 0x7 /* 0 vars */) = 0\n'
            "2001 +++ exited with 0 +++\n"
        )
        assert ref._missing_successful_workflow_execs(good) == []
        failed_exit = (
            '2000 execve("/usr/bin/bash", '
            '["bash", "/app/scripts/stage_cohort.sh", "/app/var/x.csv", '
            '"/app/var/fold_work", "strata"], 0x7 /* 0 vars */) = 0\n'
            "2000 +++ exited with 1 +++\n"
            '2001 execve("/usr/bin/Rscript", '
            '["Rscript", "/app/r/fold_balance.R", '
            '"/app/var/fold_manifest.json"], 0x7 /* 0 vars */) = 0\n'
            "2001 +++ exited with 0 +++\n"
        )
        assert ref._missing_successful_workflow_execs(failed_exit) == [
            "stage_cohort.sh"
        ]

    def test_fold_balance_rscript_on_verifier_manifest(self) -> None:
        """fold_balance.R under the protected runner prints one stdout JSON object and leaves the argv manifest untouched."""
        rows = [
            ("1", "a"),
            ("2", "a"),
            ("3", "b"),
            ("4", "b"),
            ("5", "a"),
            ("6", "b"),
        ]
        fold_count = 3
        expected = ref.reference_balance(rows, fold_count)
        probe = ref.build_balance_probe_manifest(rows, fold_count)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "probe_manifest.json"
            raw = json.dumps(probe)
            path.write_text(raw, encoding="utf-8")
            proc = ref.run_fold_balance_rscript(path)
            assert proc.returncode == 0, proc.stderr
            # Stdout must be one JSON object (verifier parses process stdout only).
            stripped = proc.stdout.strip()
            body = json.loads(stripped)
            assert isinstance(body, dict)
            assert "\n" not in stripped
        assert set(body) >= {
            "max_label_skew",
            "min_fold_rows",
            "max_fold_rows",
            "label_columns",
            "skew_band",
        }
        assert body["label_columns"] == expected["label_columns"]
        assert body["min_fold_rows"] == expected["min_fold_rows"]
        assert body["max_fold_rows"] == expected["max_fold_rows"]
        assert body["skew_band"] == expected["skew_band"]
        assert abs(
            float(body["max_label_skew"]) - float(expected["max_label_skew"])
        ) < (1e-9)

    def test_forbidden_paths_include_solution(self) -> None:
        """Normalized /solution access must be treated as forbidden for assemble."""
        assert ref._is_forbidden_resolved("/solution")
        assert ref._is_forbidden_resolved("/solution/fixed/r/fold_balance.R")
        assert ref._is_forbidden_resolved("/app/../solution/fixed")
        assert not ref._is_forbidden_resolved("/app/r/fold_balance.R")

    def test_large_numeric_id_beyond_int32(self) -> None:
        """Ids above signed 32-bit max must assign and seal without crashing."""
        ref.reset_var()
        big = "2147483648"
        rows = [
            ("1", "a"),
            ("2", "a"),
            (big, "a"),
            ("3", "b"),
            ("4", "b"),
            ("5", "b"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wide_ids.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata"])
                writer.writerows(rows)
            proc = ref.run_assemble(dataset=path, folds=2, label="strata")
            assert proc.returncode == 0, proc.stderr
            payload = ref.load_stdout_json(proc)
            expected = ref.reference_assign(rows, 2)
            for fold_id, row_ids in expected.items():
                assert ref.fold_map(payload)[fold_id]["row_ids"] == row_ids
            assert big in ref.all_row_ids(payload)
            assert payload["fold_split_witness"] == ref.reference_fold_split_witness(
                expected
            )

    def test_cohort_checksum_matches_reference(self) -> None:
        """cohort_checksum must hash sorted id|label cohort rows."""
        expected = ref.reference_cohort_checksum(self.rows)
        assert self.stdout["cohort_checksum"] == expected

    def test_cohort_checksum_hex_format(self) -> None:
        """cohort_checksum is lowercase SHA-256 hex."""
        assert re.fullmatch(r"[0-9a-f]{64}", self.stdout["cohort_checksum"])

    def test_assignment_seal_matches_reference(self) -> None:
        """assignment_seal must witness per-label fold round-robin order."""
        expected = ref.reference_assignment_seal(self.rows, ref.STOCK_FOLDS)
        assert self.stdout["assignment_seal"] == expected

    def test_assignment_seal_hex_format(self) -> None:
        """assignment_seal is lowercase SHA-256 hex."""
        assert re.fullmatch(r"[0-9a-f]{64}", self.stdout["assignment_seal"])

    def test_balance_anchor_matches_reference(self) -> None:
        """balance_anchor must couple fold_digest to R max_label_skew."""
        expected = ref.reference_balance_anchor(
            self.stdout["fold_digest"],
            float(self.stdout["balance"]["max_label_skew"]),
        )
        assert self.stdout["balance_anchor"] == expected

    def test_manifest_seal_matches_reference(self) -> None:
        """manifest_seal must chain cohort, assignment, balance, and fold_count."""
        seals = ref.reference_extended_seals(
            self.rows, ref.STOCK_FOLDS, self.stdout["fold_digest"]
        )
        assert self.stdout["manifest_seal"] == seals["manifest_seal"]

    def test_cross_module_manifest_seal_recomposition(self) -> None:
        """manifest_seal must match recomputation from upstream seal fields."""
        seals = ref.reference_extended_seals(
            self.rows, ref.STOCK_FOLDS, self.stdout["fold_digest"]
        )
        assert self.stdout["cohort_checksum"] == seals["cohort_checksum"]
        assert self.stdout["assignment_seal"] == seals["assignment_seal"]
        assert self.stdout["balance_anchor"] == seals["balance_anchor"]
        assert self.stdout["manifest_seal"] == ref.reference_manifest_seal(
            seals["cohort_checksum"],
            seals["assignment_seal"],
            seals["balance_anchor"],
            ref.STOCK_FOLDS,
        )

    def test_fold_receipt_jsonl_created(self) -> None:
        """Successful assemble must append a receipt line on disk."""
        assert ref.RECEIPT_PATH.is_file()
        lines = ref.read_receipt_lines()
        assert len(lines) >= 1
        record = lines[-1]
        assert record["row_count"] == self.stdout["row_count"]
        assert record["fold_count"] == self.stdout["fold_count"]
        assert record["label_column"] == self.stdout["label_column"]
        assert record["manifest_seal"] == self.stdout["manifest_seal"]
        assert record["fold_digest"] == self.stdout["fold_digest"]
        assert record["receipt_chain"] == self.stdout["receipt_chain"]
        assert record["rotation_epoch"] == self.stdout["rotation_epoch"]
        assert record["ledger_root"] == self.stdout["ledger_root"]

    def test_staged_fingerprint_matches_staged_bytes(self) -> None:
        """staged_fingerprint must hash the staged CSV bytes."""
        expected = ref.reference_staged_fingerprint()
        assert self.stdout["staged_fingerprint"] == expected

    def test_staged_fingerprint_hex_format(self) -> None:
        """staged_fingerprint is lowercase SHA-256 hex."""
        assert re.fullmatch(r"[0-9a-f]{64}", self.stdout["staged_fingerprint"])

    def test_quorum_witness_matches_reference(self) -> None:
        """quorum_witness must record earliest fold per label."""
        expected = ref.reference_quorum_witness(self.rows, ref.STOCK_FOLDS)
        assert self.stdout["quorum_witness"] == expected

    def test_stratum_spread_digest_matches_reference(self) -> None:
        """stratum_spread_digest must capture per-label spread across folds."""
        expected = ref.reference_stratum_spread_digest(self.rows, ref.STOCK_FOLDS)
        assert self.stdout["stratum_spread_digest"] == expected

    def test_balance_skew_band_present(self) -> None:
        """balance.skew_band must be emitted by R."""
        assert self.stdout["balance"]["skew_band"] in {"tight", "moderate", "loose"}

    def test_balance_skew_band_matches_reference(self) -> None:
        """balance.skew_band must follow documented band thresholds."""
        expected = ref.reference_balance(self.rows, ref.STOCK_FOLDS)
        assert self.stdout["balance"]["skew_band"] == expected["skew_band"]

    def test_band_anchor_matches_reference(self) -> None:
        """band_anchor must couple skew_band to fold_digest."""
        expected = ref.reference_band_anchor(
            self.stdout["balance"]["skew_band"], self.stdout["fold_digest"]
        )
        assert self.stdout["band_anchor"] == expected

    def test_rotation_epoch_starts_at_one(self) -> None:
        """First assemble after reset must use rotation_epoch 1."""
        assert self.stdout["rotation_epoch"] == 1

    def test_receipt_chain_genesis_on_first_run(self) -> None:
        """First receipt chain must anchor from GENESIS."""
        expected = ref.reference_receipt_chain(self.stdout["manifest_seal"])
        assert self.stdout["receipt_chain"] == expected

    def test_epoch_seal_matches_reference(self) -> None:
        """epoch_seal must bind rotation_epoch to manifest_seal."""
        expected = ref.reference_epoch_seal(
            self.stdout["rotation_epoch"], self.stdout["manifest_seal"]
        )
        assert self.stdout["epoch_seal"] == expected

    def test_ledger_root_matches_reference(self) -> None:
        """ledger_root must chain staged bytes, cohort checksum, and epoch seal."""
        expected = ref.reference_ledger_root(
            self.stdout["staged_fingerprint"],
            self.stdout["cohort_checksum"],
            self.stdout["epoch_seal"],
        )
        assert self.stdout["ledger_root"] == expected

    def test_cross_module_ledger_root_recomposition(self) -> None:
        """ledger_root must recompose from upstream coupling fields."""
        coupling = ref.reference_extended_coupling(
            self.rows,
            ref.STOCK_FOLDS,
            self.stdout["fold_digest"],
            self.stdout["staged_fingerprint"],
            self.stdout["rotation_epoch"],
        )
        assert self.stdout["ledger_root"] == coupling["ledger_root"]
        assert self.stdout["epoch_seal"] == coupling["epoch_seal"]
        assert self.stdout["band_anchor"] == coupling["band_anchor"]

    def test_rotation_epoch_increments_without_reset(self) -> None:
        """Second assemble in the same session must bump rotation_epoch."""
        proc = ref.run_assemble()
        payload = ref.load_stdout_json(proc)
        assert payload["rotation_epoch"] == self.stdout["rotation_epoch"] + 1

    def test_receipt_chain_links_prior_receipt(self) -> None:
        """Second assemble must chain from the prior receipt_chain value."""
        prior = self.stdout["receipt_chain"]
        proc = ref.run_assemble()
        payload = ref.load_stdout_json(proc)
        expected = ref.reference_receipt_chain(payload["manifest_seal"], prior)
        assert payload["receipt_chain"] == expected
        assert payload["receipt_chain"] != prior

    def test_multi_step_rotation_and_chain_flow(self) -> None:
        """Three sequential assembles must advance epoch and chain seals."""
        epoch = self.stdout["rotation_epoch"]
        chain = self.stdout["receipt_chain"]
        for _step in range(2):
            proc = ref.run_assemble()
            payload = ref.load_stdout_json(proc)
            epoch += 1
            chain = ref.reference_receipt_chain(payload["manifest_seal"], chain)
            assert payload["rotation_epoch"] == epoch
            assert payload["receipt_chain"] == chain

    def test_dynamic_quorum_witness_tracks_labels(self) -> None:
        """Novel labels must change quorum_witness."""
        ref.reset_var()
        random.seed(31415)
        with tempfile.TemporaryDirectory() as tmp:
            dynamic = Path(tmp) / "quorum.csv"
            with dynamic.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 13):
                    label = ["red", "blue", "green"][idx % 3]
                    writer.writerow([idx, label, "0.2"])
                    rows.append((str(idx), label))
            proc = ref.run_assemble(dataset=dynamic, folds=4, label="strata")
            payload = ref.load_stdout_json(proc)
            assert payload["quorum_witness"] == ref.reference_quorum_witness(rows, 4)

    def test_dynamic_stratum_spread_tracks_distribution(self) -> None:
        """Imbalanced cohorts must shift stratum_spread_digest."""
        ref.reset_var()
        with tempfile.TemporaryDirectory() as tmp:
            dynamic = Path(tmp) / "spread.csv"
            with dynamic.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 10):
                    label = "heavy" if idx <= 6 else "light"
                    writer.writerow([idx, label, "0.3"])
                    rows.append((str(idx), label))
            proc = ref.run_assemble(dataset=dynamic, folds=3, label="strata")
            payload = ref.load_stdout_json(proc)
            assert payload[
                "stratum_spread_digest"
            ] == ref.reference_stratum_spread_digest(rows, 3)

    def test_dynamic_band_anchor_tracks_skew_band(self) -> None:
        """Alternate fold counts must recompute band_anchor through skew_band."""
        ref.reset_var()
        proc = ref.run_assemble(folds=3)
        payload = ref.load_stdout_json(proc)
        expected = ref.reference_band_anchor(
            payload["balance"]["skew_band"], payload["fold_digest"]
        )
        assert payload["band_anchor"] == expected
        assert payload["band_anchor"] != self.stdout["band_anchor"]

    def test_dynamic_ledger_root_bypass(self) -> None:
        """Novel staged bytes must change ledger_root end-to-end."""
        ref.reset_var()
        random.seed(556677)
        with tempfile.TemporaryDirectory() as tmp:
            dynamic = Path(tmp) / "ledger.csv"
            with dynamic.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 11):
                    label = ["x", "y"][idx % 2]
                    writer.writerow([idx, label, "0.4"])
                    rows.append((str(idx), label))
            proc = ref.run_assemble(dataset=dynamic, folds=2, label="strata")
            payload = ref.load_stdout_json(proc)
            staged_fp = ref.reference_staged_fingerprint(ref.STAGED_PATH)
            coupling = ref.reference_extended_coupling(
                rows, 2, payload["fold_digest"], staged_fp, 1
            )
            assert payload["ledger_root"] == coupling["ledger_root"]

    def test_dynamic_receipt_chain_bypass(self) -> None:
        """Random cohort data must produce a distinct receipt_chain."""
        ref.reset_var()
        random.seed(889900)
        with tempfile.TemporaryDirectory() as tmp:
            dynamic = Path(tmp) / "chain.csv"
            with dynamic.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 14):
                    label = ["p", "q", "r"][idx % 3]
                    writer.writerow([idx, label, "0.6"])
                    rows.append((str(idx), label))
            proc = ref.run_assemble(dataset=dynamic, folds=5, label="strata")
            payload = ref.load_stdout_json(proc)
            expected = ref.reference_receipt_chain(payload["manifest_seal"])
            assert payload["receipt_chain"] == expected
            assert payload["receipt_chain"] != self.stdout["receipt_chain"]

    def test_multi_step_extended_seal_coupling_flow(self) -> None:
        """Extended seal fields must stay mutually consistent on stock data."""
        seals = ref.reference_extended_seals(
            self.rows, ref.STOCK_FOLDS, self.stdout["fold_digest"]
        )
        for key, value in seals.items():
            assert self.stdout[key] == value
            assert self.manifest[key] == value

    def test_dynamic_cohort_checksum_tracks_rows(self) -> None:
        """Mutating cohort rows must shift cohort_checksum."""
        ref.reset_var()
        random.seed(445566)
        with tempfile.TemporaryDirectory() as tmp:
            dynamic = Path(tmp) / "dynamic.csv"
            with dynamic.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 13):
                    label = ["alpha", "beta", "gamma"][idx % 3]
                    writer.writerow([idx, label, "0.5"])
                    rows.append((str(idx), label))
            proc = ref.run_assemble(dataset=dynamic, folds=4, label="strata")
            payload = ref.load_stdout_json(proc)
            assert payload["cohort_checksum"] == ref.reference_cohort_checksum(rows)

    def test_dynamic_assignment_seal_tracks_fold_count(self) -> None:
        """Different fold counts must change assignment_seal."""
        ref.reset_var()
        proc_three = ref.run_assemble(folds=3)
        seal_three = ref.load_stdout_json(proc_three)["assignment_seal"]
        ref.reset_var()
        proc_five = ref.run_assemble(folds=5)
        seal_five = ref.load_stdout_json(proc_five)["assignment_seal"]
        assert seal_three != seal_five

    def test_dynamic_balance_anchor_tracks_skew(self) -> None:
        """Alternate fold counts must shift balance_anchor through skew changes."""
        ref.reset_var()
        proc = ref.run_assemble(folds=3)
        payload = ref.load_stdout_json(proc)
        stock_anchor = self.stdout["balance_anchor"]
        alt_anchor = ref.reference_balance_anchor(
            payload["fold_digest"], float(payload["balance"]["max_label_skew"])
        )
        assert payload["balance_anchor"] == alt_anchor
        assert alt_anchor != stock_anchor

    def test_dynamic_manifest_seal_bypass(self) -> None:
        """Novel cohort data must change manifest_seal end-to-end."""
        ref.reset_var()
        random.seed(778899)
        with tempfile.TemporaryDirectory() as tmp:
            dynamic = Path(tmp) / "seal.csv"
            with dynamic.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 16):
                    label = ["north", "south"][idx % 2]
                    writer.writerow([idx, label, "0.1"])
                    rows.append((str(idx), label))
            proc = ref.run_assemble(dataset=dynamic, folds=3, label="strata")
            payload = ref.load_stdout_json(proc)
            digest = ref.reference_digest_from_rows(rows, 3)
            seals = ref.reference_extended_seals(rows, 3, digest)
            assert payload["manifest_seal"] == seals["manifest_seal"]

    def test_receipt_appends_on_second_assemble(self) -> None:
        """A second assemble without reset must append another receipt line."""
        before = len(ref.read_receipt_lines())
        proc = ref.run_assemble()
        assert proc.returncode == 0
        lines = ref.read_receipt_lines()
        assert len(lines) == before + 1
        assert lines[-1]["manifest_seal"] == ref.load_stdout_json(proc)["manifest_seal"]

    def test_fold_parity_digest_stock(self) -> None:
        """Stock fold_parity_digest must hash even/odd fold lines."""
        expected = ref.reference_fold_parity_digest(ref.STOCK_FOLDS)
        assert self.stdout["fold_parity_digest"] == expected
        assert self.manifest["fold_parity_digest"] == expected

    def test_label_coverage_seal_stock(self) -> None:
        """Stock label_coverage_seal must hash per-label fold coverage."""
        expected = ref.reference_label_coverage_seal(self.rows, ref.STOCK_FOLDS)
        assert self.stdout["label_coverage_seal"] == expected

    def test_holdout_fold_id_first_epoch(self) -> None:
        """First assemble holdout_fold_id must be (1-1) % K."""
        assert self.stdout["holdout_fold_id"] == ref.reference_holdout_fold_id(
            1, ref.STOCK_FOLDS
        )

    def test_stratum_entropy_hint_stock(self) -> None:
        """Stock stratum_entropy_hint must mark dense/sparse label buckets."""
        expected = ref.reference_stratum_entropy_hint(self.rows, ref.STOCK_FOLDS)
        assert self.stdout["stratum_entropy_hint"] == expected

    def test_evaluation_seal_couples_parity_coverage_holdout(self) -> None:
        """evaluation_seal must bind parity, coverage, holdout, and manifest_seal."""
        expected = ref.reference_evaluation_seal(
            self.stdout["fold_parity_digest"],
            self.stdout["label_coverage_seal"],
            int(self.stdout["holdout_fold_id"]),
            self.stdout["manifest_seal"],
        )
        assert self.stdout["evaluation_seal"] == expected

    def test_assemble_attestation_couples_eval_ledger_entropy(self) -> None:
        """assemble_attestation must bind evaluation_seal, ledger_root, and entropy."""
        expected = ref.reference_assemble_attestation(
            self.stdout["evaluation_seal"],
            self.stdout["ledger_root"],
            self.stdout["stratum_entropy_hint"],
        )
        assert self.stdout["assemble_attestation"] == expected

    def test_receipt_includes_evaluation_fields(self) -> None:
        """Receipt JSONL must carry evaluation_seal, attestation, and holdout."""
        lines = ref.read_receipt_lines()
        assert lines
        last = lines[-1]
        assert last["evaluation_seal"] == self.stdout["evaluation_seal"]
        assert last["assemble_attestation"] == self.stdout["assemble_attestation"]
        assert last["holdout_fold_id"] == self.stdout["holdout_fold_id"]

    def test_multi_step_holdout_advances_with_epoch(self) -> None:
        """Second assemble must advance holdout_fold_id with rotation_epoch."""
        first_holdout = self.stdout["holdout_fold_id"]
        proc = ref.run_assemble()
        assert proc.returncode == 0
        second = ref.load_stdout_json(proc)
        assert second["rotation_epoch"] == 2
        assert second["holdout_fold_id"] == ref.reference_holdout_fold_id(
            2, ref.STOCK_FOLDS
        )
        assert second["holdout_fold_id"] != first_holdout

    def test_multi_step_evaluation_seal_changes_on_second_assemble(self) -> None:
        """Second assemble must change evaluation_seal via holdout and manifest."""
        first_eval = self.stdout["evaluation_seal"]
        proc = ref.run_assemble()
        second = ref.load_stdout_json(proc)
        assert second["evaluation_seal"] != first_eval
        expected = ref.reference_evaluation_seal(
            second["fold_parity_digest"],
            second["label_coverage_seal"],
            int(second["holdout_fold_id"]),
            second["manifest_seal"],
        )
        assert second["evaluation_seal"] == expected

    def test_multi_step_attestation_tracks_ledger_and_eval(self) -> None:
        """Attestation after a second assemble must recompute from coupled fields."""
        proc = ref.run_assemble()
        second = ref.load_stdout_json(proc)
        expected = ref.reference_assemble_attestation(
            second["evaluation_seal"],
            second["ledger_root"],
            second["stratum_entropy_hint"],
        )
        assert second["assemble_attestation"] == expected

    def test_edge_holdout_with_single_fold(self) -> None:
        """With K=1, holdout_fold_id must stay 0 across epochs."""
        ref.reset_var()
        first = ref.load_stdout_json(ref.run_assemble(folds=1))
        assert first["holdout_fold_id"] == 0
        second = ref.load_stdout_json(ref.run_assemble(folds=1))
        assert second["rotation_epoch"] == 2
        assert second["holdout_fold_id"] == 0

    def test_edge_sparse_entropy_for_rare_label(self) -> None:
        """A label with fewer rows than K must contribute a sparse entropy bucket."""
        ref.reset_var()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sparse.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 6):
                    writer.writerow([idx, "common", "0.1"])
                    rows.append((str(idx), "common"))
                writer.writerow([6, "rare", "0.2"])
                rows.append(("6", "rare"))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=5, label="strata")
            )
            expected = ref.reference_stratum_entropy_hint(rows, 5)
            assert payload["stratum_entropy_hint"] == expected
            assert "rare|sparse" in "\n".join(
                f"{label}|{'sparse' if sum(1 for _i, lab in rows if lab == label) < 5 else 'dense'}"
                for label in sorted({lab for _i, lab in rows})
            )

    def test_dynamic_fold_parity_changes_with_fold_count(self) -> None:
        """Different K values must change fold_parity_digest."""
        ref.reset_var()
        three = ref.load_stdout_json(ref.run_assemble(folds=3))["fold_parity_digest"]
        ref.reset_var()
        five = ref.load_stdout_json(ref.run_assemble(folds=5))["fold_parity_digest"]
        assert three != five
        assert three == ref.reference_fold_parity_digest(3)

    def test_dynamic_label_coverage_seal_bypass(self) -> None:
        """Novel cohort labels must change label_coverage_seal."""
        ref.reset_var()
        random.seed(112233)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cover.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 12):
                    label = ["u", "v", "w"][idx % 3]
                    writer.writerow([idx, label, "0.3"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=4, label="strata")
            )
            assert payload["label_coverage_seal"] == ref.reference_label_coverage_seal(
                rows, 4
            )
            assert payload["label_coverage_seal"] != self.stdout["label_coverage_seal"]

    def test_dynamic_evaluation_seal_bypass(self) -> None:
        """Random cohort data must recompute evaluation_seal end-to-end."""
        ref.reset_var()
        random.seed(334455)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "eval.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 15):
                    label = ["a", "b"][idx % 2]
                    writer.writerow([idx, label, "0.7"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=3, label="strata")
            )
            staged_fp = ref.reference_staged_fingerprint(ref.STAGED_PATH)
            coupling = ref.reference_extended_coupling(
                rows, 3, payload["fold_digest"], staged_fp, 1
            )
            assert payload["evaluation_seal"] == coupling["evaluation_seal"]

    def test_dynamic_assemble_attestation_bypass(self) -> None:
        """Novel rows must change assemble_attestation through coupled seals."""
        ref.reset_var()
        random.seed(667788)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attest.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 10):
                    label = ["m", "n", "o"][idx % 3]
                    writer.writerow([idx, label, "0.9"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=2, label="strata")
            )
            staged_fp = ref.reference_staged_fingerprint(ref.STAGED_PATH)
            coupling = ref.reference_extended_coupling(
                rows, 2, payload["fold_digest"], staged_fp, 1
            )
            assert payload["assemble_attestation"] == coupling["assemble_attestation"]
            assert (
                payload["assemble_attestation"] != self.stdout["assemble_attestation"]
            )

    def test_dynamic_entropy_hint_tracks_label_density(self) -> None:
        """Changing label frequencies must shift stratum_entropy_hint."""
        ref.reset_var()
        random.seed(990011)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "entropy.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 8):
                    label = "bulk" if idx < 7 else "tiny"
                    writer.writerow([idx, label, "0.2"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=4, label="strata")
            )
            assert payload[
                "stratum_entropy_hint"
            ] == ref.reference_stratum_entropy_hint(rows, 4)

    def test_cross_module_extended_coupling_includes_eval_fields(self) -> None:
        """Stock extended coupling helper must match all new evaluation fields."""
        staged_fp = ref.reference_staged_fingerprint(ref.STAGED_PATH)
        coupling = ref.reference_extended_coupling(
            self.rows,
            ref.STOCK_FOLDS,
            self.stdout["fold_digest"],
            staged_fp,
            int(self.stdout["rotation_epoch"]),
        )
        for key in (
            "fold_parity_digest",
            "label_coverage_seal",
            "holdout_fold_id",
            "evaluation_seal",
            "stratum_entropy_hint",
            "assemble_attestation",
            "fold_load_skew",
            "label_cardinality",
            "cohort_span_digest",
            "balance_coupler",
            "kit_closure",
            "run_chain_digest",
        ):
            assert self.stdout[key] == coupling[key]

    def test_fold_load_skew_stock(self) -> None:
        """Stock fold_load_skew must be max fold size minus min fold size."""
        expected = ref.reference_fold_load_skew(self.rows, ref.STOCK_FOLDS)
        assert self.stdout["fold_load_skew"] == expected
        assert self.manifest["fold_load_skew"] == expected

    def test_label_cardinality_stock(self) -> None:
        """Stock label_cardinality must count distinct cohort labels."""
        expected = ref.reference_label_cardinality(self.rows)
        assert self.stdout["label_cardinality"] == expected
        assert expected == 4

    def test_cohort_span_digest_stock(self) -> None:
        """Stock cohort_span_digest must hash sorted unique labels."""
        expected = ref.reference_cohort_span_digest(self.rows)
        assert self.stdout["cohort_span_digest"] == expected
        assert self.manifest["cohort_span_digest"] == expected

    def test_balance_coupler_stock(self) -> None:
        """Stock balance_coupler must bind balance_anchor, band_anchor, skew_band."""
        expected = ref.reference_balance_coupler(
            self.stdout["balance_anchor"],
            self.stdout["band_anchor"],
            self.stdout["balance"]["skew_band"],
        )
        assert self.stdout["balance_coupler"] == expected

    def test_kit_closure_stock(self) -> None:
        """Stock kit_closure must couple attestation with load and balance fields."""
        expected = ref.reference_kit_closure(
            self.stdout["assemble_attestation"],
            int(self.stdout["fold_load_skew"]),
            int(self.stdout["label_cardinality"]),
            self.stdout["cohort_span_digest"],
            self.stdout["balance_coupler"],
        )
        assert self.stdout["kit_closure"] == expected

    def test_run_chain_digest_genesis_first(self) -> None:
        """First assemble run_chain_digest must chain from GENESIS."""
        expected = ref.reference_run_chain_digest(self.stdout["kit_closure"], "GENESIS")
        assert self.stdout["run_chain_digest"] == expected

    def test_label_cardinality_matches_span_digest_body(self) -> None:
        """label_cardinality must equal the number of labels hashed into span digest."""
        labels = sorted({label for _row_id, label in self.rows})
        assert self.stdout["label_cardinality"] == len(labels)
        assert self.stdout["cohort_span_digest"] == ref.reference_cohort_span_digest(
            self.rows
        )

    def test_edge_empty_label_cardinality_helper(self) -> None:
        """Empty row list must yield zero cardinality and empty-string span digest."""
        assert ref.reference_label_cardinality([]) == 0
        assert ref.reference_fold_load_skew([], 5) == 0
        empty_digest = ref.reference_cohort_span_digest([])
        assert empty_digest == hashlib.sha256(b"").hexdigest()

    def test_edge_single_label_cardinality(self) -> None:
        """A single-label cohort must report label_cardinality of 1."""
        ref.reset_var()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "one_label.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 7):
                    writer.writerow([idx, "solo", "0.1"])
                    rows.append((str(idx), "solo"))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=3, label="strata")
            )
            assert payload["label_cardinality"] == 1
            assert payload["cohort_span_digest"] == ref.reference_cohort_span_digest(
                rows
            )
            assert payload["fold_load_skew"] == ref.reference_fold_load_skew(rows, 3)

    def test_multi_step_run_chain_digest_advances(self) -> None:
        """Second assemble must chain run_chain_digest from the prior kit_closure."""
        first_kit = self.stdout["kit_closure"]
        first_chain = self.stdout["run_chain_digest"]
        proc = ref.run_assemble()
        assert proc.returncode == 0
        second = ref.load_stdout_json(proc)
        expected = ref.reference_run_chain_digest(second["kit_closure"], first_chain)
        assert second["run_chain_digest"] == expected
        assert second["run_chain_digest"] != first_chain
        assert second["kit_closure"] != first_kit

    def test_multi_step_kit_closure_tracks_epoch_attestation(self) -> None:
        """kit_closure must change when epoch-driven assemble_attestation changes."""
        first_closure = self.stdout["kit_closure"]
        first_attest = self.stdout["assemble_attestation"]
        proc = ref.run_assemble()
        second = ref.load_stdout_json(proc)
        assert second["assemble_attestation"] != first_attest
        expected = ref.reference_kit_closure(
            second["assemble_attestation"],
            int(second["fold_load_skew"]),
            int(second["label_cardinality"]),
            second["cohort_span_digest"],
            second["balance_coupler"],
        )
        assert second["kit_closure"] == expected
        assert second["kit_closure"] != first_closure

    def test_cross_module_kit_closure_from_stdout_fields(self) -> None:
        """kit_closure must recompute from the other stdout coupling fields."""
        expected = ref.reference_kit_closure(
            self.stdout["assemble_attestation"],
            int(self.stdout["fold_load_skew"]),
            int(self.stdout["label_cardinality"]),
            self.stdout["cohort_span_digest"],
            self.stdout["balance_coupler"],
        )
        assert self.stdout["kit_closure"] == expected

    def test_receipt_includes_kit_closure_fields(self) -> None:
        """Receipt JSONL must carry kit closure, run chain, and load metrics."""
        lines = ref.read_receipt_lines()
        assert lines
        last = lines[-1]
        assert last["kit_closure"] == self.stdout["kit_closure"]
        assert last["run_chain_digest"] == self.stdout["run_chain_digest"]
        assert last["fold_load_skew"] == self.stdout["fold_load_skew"]
        assert last["label_cardinality"] == self.stdout["label_cardinality"]
        assert last["balance_coupler"] == self.stdout["balance_coupler"]
        assert last["cohort_span_digest"] == self.stdout["cohort_span_digest"]

    def test_dynamic_fold_load_skew_bypass(self) -> None:
        """Uneven label sizes must change fold_load_skew versus stock."""
        ref.reset_var()
        random.seed(121212)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "skew.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 20):
                    label = "big" if idx < 15 else "small"
                    writer.writerow([idx, label, "0.4"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=4, label="strata")
            )
            expected = ref.reference_fold_load_skew(rows, 4)
            assert payload["fold_load_skew"] == expected
            assert payload["fold_load_skew"] != self.stdout["fold_load_skew"]

    def test_dynamic_label_cardinality_bypass(self) -> None:
        """Novel label sets must change label_cardinality."""
        ref.reset_var()
        random.seed(343434)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "card.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                labels = ["p", "q", "r", "s", "t"]
                for idx in range(1, 16):
                    label = labels[idx % 5]
                    writer.writerow([idx, label, "0.5"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=3, label="strata")
            )
            assert payload["label_cardinality"] == ref.reference_label_cardinality(rows)
            assert payload["label_cardinality"] == 5
            assert payload["label_cardinality"] != self.stdout["label_cardinality"]

    def test_dynamic_cohort_span_digest_bypass(self) -> None:
        """Random labels must recompute cohort_span_digest."""
        ref.reset_var()
        random.seed(565656)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "span.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 11):
                    label = ["x", "y", "z"][idx % 3]
                    writer.writerow([idx, label, "0.6"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=2, label="strata")
            )
            assert payload["cohort_span_digest"] == ref.reference_cohort_span_digest(
                rows
            )
            assert payload["cohort_span_digest"] != self.stdout["cohort_span_digest"]

    def test_dynamic_balance_coupler_bypass(self) -> None:
        """Novel cohorts must recompute balance_coupler from anchors and band."""
        ref.reset_var()
        random.seed(787878)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "coupler.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 13):
                    label = ["aa", "bb"][idx % 2]
                    writer.writerow([idx, label, "0.8"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=3, label="strata")
            )
            expected = ref.reference_balance_coupler(
                payload["balance_anchor"],
                payload["band_anchor"],
                payload["balance"]["skew_band"],
            )
            assert payload["balance_coupler"] == expected
            assert payload["balance_coupler"] != self.stdout["balance_coupler"]

    def test_dynamic_kit_closure_bypass(self) -> None:
        """Random data must recompute kit_closure end-to-end via extended coupling."""
        ref.reset_var()
        random.seed(909090)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kit.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 14):
                    label = ["c1", "c2", "c3"][idx % 3]
                    writer.writerow([idx, label, "0.2"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=4, label="strata")
            )
            staged_fp = ref.reference_staged_fingerprint(ref.STAGED_PATH)
            coupling = ref.reference_extended_coupling(
                rows, 4, payload["fold_digest"], staged_fp, 1
            )
            assert payload["kit_closure"] == coupling["kit_closure"]
            assert payload["kit_closure"] != self.stdout["kit_closure"]

    def test_dynamic_run_chain_digest_bypass(self) -> None:
        """A second assemble on novel data must chain run_chain_digest from the first."""
        ref.reset_var()
        random.seed(101010)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chain.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 9):
                    label = ["d", "e"][idx % 2]
                    writer.writerow([idx, label, "0.3"])
                    rows.append((str(idx), label))
            first = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=2, label="strata")
            )
            staged_fp = ref.reference_staged_fingerprint(ref.STAGED_PATH)
            first_coupling = ref.reference_extended_coupling(
                rows, 2, first["fold_digest"], staged_fp, 1
            )
            assert first["run_chain_digest"] == first_coupling["run_chain_digest"]
            second = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=2, label="strata")
            )
            second_coupling = ref.reference_extended_coupling(
                rows,
                2,
                second["fold_digest"],
                staged_fp,
                2,
                prior_receipt_chain=first["receipt_chain"],
                prior_run_chain=first["run_chain_digest"],
            )
            assert second["run_chain_digest"] == second_coupling["run_chain_digest"]
            assert second["run_chain_digest"] != first["run_chain_digest"]

    def test_class_prior_seal_stock(self) -> None:
        """Stock class_prior_seal must hash label priors built from fold label totals."""
        expected = ref.reference_class_prior_seal(self.label_counts, len(self.rows))
        assert self.stdout["class_prior_seal"] == expected
        assert self.manifest["class_prior_seal"] == expected

    def test_class_prior_seal_hex_format(self) -> None:
        """class_prior_seal is lowercase SHA-256 hex."""
        assert re.fullmatch(r"[0-9a-f]{64}", self.stdout["class_prior_seal"])

    def test_fold_split_witness_stock(self) -> None:
        """Stock fold_split_witness must hash fold_id|first_id|last_id|size lines."""
        expected = ref.reference_fold_split_witness(self.assignment)
        assert self.stdout["fold_split_witness"] == expected
        assert self.manifest["fold_split_witness"] == expected

    def test_holdout_epoch_coupler_stock(self) -> None:
        """Stock holdout_epoch_coupler must couple holdout id, epoch, fold count, and eval seal."""
        expected = ref.reference_holdout_epoch_coupler(
            int(self.stdout["holdout_fold_id"]),
            int(self.stdout["rotation_epoch"]),
            self.stdout["fold_count"],
            self.stdout["evaluation_seal"],
        )
        assert self.stdout["holdout_epoch_coupler"] == expected

    def test_stratum_stability_index_stock(self) -> None:
        """Stock stratum_stability_index must hash per-label max/min share across folds."""
        expected = ref.reference_stratum_stability_index(
            self.assignment, self.label_counts
        )
        assert self.stdout["stratum_stability_index"] == expected

    def test_fold_kit_seal_stock(self) -> None:
        """Stock fold_kit_seal must couple kit_closure with the seal fields through holdout_exclusion_seal."""
        expected = ref.reference_fold_kit_seal(
            self.stdout["kit_closure"],
            self.stdout["class_prior_seal"],
            self.stdout["fold_split_witness"],
            self.stdout["holdout_epoch_coupler"],
            self.stdout["stratum_stability_index"],
            self.stdout["train_fold_mask"],
            self.stdout["label_pair_cooccurrence"],
            self.stdout["balance_drift_witness"],
            self.stdout["epoch_manifest_binder"],
            self.stdout["holdout_exclusion_seal"],
        )
        assert self.stdout["fold_kit_seal"] == expected

    def test_cross_module_fold_kit_seal_from_stdout_components(self) -> None:
        """fold_kit_seal must recompute purely from the other stdout coupling fields."""
        expected = ref.reference_fold_kit_seal(
            self.stdout["kit_closure"],
            self.stdout["class_prior_seal"],
            self.stdout["fold_split_witness"],
            self.stdout["holdout_epoch_coupler"],
            self.stdout["stratum_stability_index"],
            self.stdout["train_fold_mask"],
            self.stdout["label_pair_cooccurrence"],
            self.stdout["balance_drift_witness"],
            self.stdout["epoch_manifest_binder"],
            self.stdout["holdout_exclusion_seal"],
        )
        assert self.stdout["fold_kit_seal"] == expected
        assert self.manifest["fold_kit_seal"] == expected

    def test_receipt_includes_new_seal_fields(self) -> None:
        """Receipt JSONL must carry the seal and witness fields including the five additive seals."""
        lines = ref.read_receipt_lines()
        assert lines
        last = lines[-1]
        assert last["class_prior_seal"] == self.stdout["class_prior_seal"]
        assert last["fold_split_witness"] == self.stdout["fold_split_witness"]
        assert last["holdout_epoch_coupler"] == self.stdout["holdout_epoch_coupler"]
        assert last["stratum_stability_index"] == self.stdout["stratum_stability_index"]
        assert last["train_fold_mask"] == self.stdout["train_fold_mask"]
        assert last["label_pair_cooccurrence"] == self.stdout["label_pair_cooccurrence"]
        assert last["balance_drift_witness"] == self.stdout["balance_drift_witness"]
        assert last["epoch_manifest_binder"] == self.stdout["epoch_manifest_binder"]
        assert last["holdout_exclusion_seal"] == self.stdout["holdout_exclusion_seal"]
        assert last["fold_kit_seal"] == self.stdout["fold_kit_seal"]
        assert last["fold_coverage_lattice"] == self.stdout["fold_coverage_lattice"]
        assert last["holdout_train_tension"] == self.stdout["holdout_train_tension"]
        assert last["skew_prior_witness"] == self.stdout["skew_prior_witness"]
        assert last["epoch_receipt_binder"] == self.stdout["epoch_receipt_binder"]
        assert last["fold_kit_outer_seal"] == self.stdout["fold_kit_outer_seal"]

    def test_new_seal_fields_hex_format(self) -> None:
        """Additive seal fields and fold_kit_seal are lowercase SHA-256 hex."""
        for key in (
            "fold_split_witness",
            "holdout_epoch_coupler",
            "stratum_stability_index",
            "train_fold_mask",
            "label_pair_cooccurrence",
            "balance_drift_witness",
            "epoch_manifest_binder",
            "holdout_exclusion_seal",
            "fold_kit_seal",
            "fold_coverage_lattice",
            "holdout_train_tension",
            "skew_prior_witness",
            "epoch_receipt_binder",
            "fold_kit_outer_seal",
        ):
            assert re.fullmatch(r"[0-9a-f]{64}", self.stdout[key])

    def test_class_prior_seal_labels_match_cardinality(self) -> None:
        """class_prior_seal must be built from exactly label_cardinality distinct labels."""
        totals: dict[str, int] = {}
        for counts in self.label_counts.values():
            for label, count in counts.items():
                totals[label] = totals.get(label, 0) + count
        assert len(totals) == self.stdout["label_cardinality"]
        expected_labels = ref.reference_balance(self.rows, ref.STOCK_FOLDS)[
            "label_columns"
        ]
        assert set(totals) == set(expected_labels)

    def test_holdout_epoch_coupler_tracks_live_evaluation_seal(self) -> None:
        """holdout_epoch_coupler must recompute from the current run's own evaluation_seal."""
        proc = ref.run_assemble()
        second = ref.load_stdout_json(proc)
        expected = ref.reference_holdout_epoch_coupler(
            int(second["holdout_fold_id"]),
            int(second["rotation_epoch"]),
            second["fold_count"],
            second["evaluation_seal"],
        )
        assert second["holdout_epoch_coupler"] == expected
        stale = ref.reference_holdout_epoch_coupler(
            int(second["holdout_fold_id"]),
            int(second["rotation_epoch"]),
            second["fold_count"],
            self.stdout["evaluation_seal"],
        )
        assert second["holdout_epoch_coupler"] != stale

    def test_multi_step_holdout_epoch_coupler_and_kit_seal_change_with_epoch(
        self,
    ) -> None:
        """Three sequential assembles must change holdout_epoch_coupler and fold_kit_seal each time."""
        seen_couplers = {self.stdout["holdout_epoch_coupler"]}
        seen_kit_seals = {self.stdout["fold_kit_seal"]}
        for _step in range(3):
            proc = ref.run_assemble()
            payload = ref.load_stdout_json(proc)
            assert payload["holdout_epoch_coupler"] not in seen_couplers
            assert payload["fold_kit_seal"] not in seen_kit_seals
            seen_couplers.add(payload["holdout_epoch_coupler"])
            seen_kit_seals.add(payload["fold_kit_seal"])
            expected_coupler = ref.reference_holdout_epoch_coupler(
                int(payload["holdout_fold_id"]),
                int(payload["rotation_epoch"]),
                payload["fold_count"],
                payload["evaluation_seal"],
            )
            assert payload["holdout_epoch_coupler"] == expected_coupler
            expected_kit_seal = ref.reference_fold_kit_seal(
                payload["kit_closure"],
                payload["class_prior_seal"],
                payload["fold_split_witness"],
                payload["holdout_epoch_coupler"],
                payload["stratum_stability_index"],
                payload["train_fold_mask"],
                payload["label_pair_cooccurrence"],
                payload["balance_drift_witness"],
                payload["epoch_manifest_binder"],
                payload["holdout_exclusion_seal"],
            )
            assert payload["fold_kit_seal"] == expected_kit_seal

    def test_edge_single_fold_stratum_stability_max_equals_min(self) -> None:
        """With K=1 every label's max_share and min_share must coincide in stratum_stability_index."""
        ref.reset_var()
        payload = ref.load_stdout_json(ref.run_assemble(folds=1))
        assignment = ref.reference_assign(self.rows, 1)
        label_counts = ref.reference_label_counts(self.rows, assignment)
        lines = []
        for label in sorted(label_counts[0]):
            share = label_counts[0][label] / len(assignment[0])
            lines.append(f"{label}|{share:.6f}|{share:.6f}")
        expected = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
        assert payload["stratum_stability_index"] == expected
        assert expected == ref.reference_stratum_stability_index(
            assignment, label_counts
        )

    def test_edge_empty_fold_split_witness_marker(self) -> None:
        """An empty fold must contribute fold_id|-|-|0 to fold_split_witness."""
        ref.reset_var()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tiny.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                writer.writerow([1, "only", "0.1"])
                writer.writerow([2, "only", "0.2"])
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=5, label="strata")
            )
            rows = [("1", "only"), ("2", "only")]
            assignment = ref.reference_assign(rows, 5)
            assert any(not ids for ids in assignment.values())
            expected = ref.reference_fold_split_witness(assignment)
            assert payload["fold_split_witness"] == expected
            lines = []
            for fold_id in sorted(assignment):
                ids = assignment[fold_id]
                if not ids:
                    lines.append(f"{fold_id}|-|-|0")
                else:
                    nums = [int(i) for i in ids]
                    lines.append(f"{fold_id}|{min(nums)}|{max(nums)}|{len(ids)}")
            assert any(line.endswith("|-|-|0") for line in lines)

    def test_dynamic_class_prior_seal_bypass(self) -> None:
        """Novel cohort composition must change class_prior_seal."""
        ref.reset_var()
        random.seed(246810)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prior.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 17):
                    label = ["red", "blue", "green", "gold"][idx % 4]
                    writer.writerow([idx, label, "0.4"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=4, label="strata")
            )
            assignment = ref.reference_assign(rows, 4)
            label_counts = ref.reference_label_counts(rows, assignment)
            expected = ref.reference_class_prior_seal(label_counts, len(rows))
            assert payload["class_prior_seal"] == expected
            assert payload["class_prior_seal"] != self.stdout["class_prior_seal"]

    def test_dynamic_fold_split_witness_bypass(self) -> None:
        """Novel row id spans must change fold_split_witness."""
        ref.reset_var()
        random.seed(135791)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "witness.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 21):
                    label = ["a1", "a2"][idx % 2]
                    writer.writerow([idx, label, "0.5"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=6, label="strata")
            )
            assignment = ref.reference_assign(rows, 6)
            expected = ref.reference_fold_split_witness(assignment)
            assert payload["fold_split_witness"] == expected
            assert payload["fold_split_witness"] != self.stdout["fold_split_witness"]

    def test_dynamic_stratum_stability_index_bypass(self) -> None:
        """Skewed label distributions must change stratum_stability_index."""
        ref.reset_var()
        random.seed(864209)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stability.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 15):
                    label = "heavy" if idx <= 10 else "light"
                    writer.writerow([idx, label, "0.6"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=3, label="strata")
            )
            assignment = ref.reference_assign(rows, 3)
            label_counts = ref.reference_label_counts(rows, assignment)
            expected = ref.reference_stratum_stability_index(assignment, label_counts)
            assert payload["stratum_stability_index"] == expected
            assert (
                payload["stratum_stability_index"]
                != self.stdout["stratum_stability_index"]
            )

    def test_dynamic_fold_kit_seal_bypass(self) -> None:
        """Random cohort data must recompute fold_kit_seal end-to-end via extended coupling."""
        ref.reset_var()
        random.seed(975318)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kitseal.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 13):
                    label = ["k1", "k2", "k3"][idx % 3]
                    writer.writerow([idx, label, "0.7"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=4, label="strata")
            )
            staged_fp = ref.reference_staged_fingerprint(ref.STAGED_PATH)
            coupling = ref.reference_extended_coupling(
                rows, 4, payload["fold_digest"], staged_fp, 1
            )
            assert payload["fold_kit_seal"] == coupling["fold_kit_seal"]
            assert payload["fold_kit_seal"] != self.stdout["fold_kit_seal"]

    def test_train_fold_mask_stock(self) -> None:
        """Stock train_fold_mask must hash comma-joined sorted train fold ids excluding holdout."""
        expected = ref.reference_train_fold_mask(
            self.assignment, int(self.stdout["holdout_fold_id"])
        )
        assert self.stdout["train_fold_mask"] == expected
        assert self.manifest["train_fold_mask"] == expected

    def test_label_pair_cooccurrence_stock(self) -> None:
        """Stock label_pair_cooccurrence must hash unordered positive label pairs per fold."""
        expected = ref.reference_label_pair_cooccurrence(
            self.assignment, self.label_counts
        )
        assert self.stdout["label_pair_cooccurrence"] == expected
        assert self.manifest["label_pair_cooccurrence"] == expected

    def test_balance_drift_witness_stock(self) -> None:
        """Stock balance_drift_witness must bind Java and R six-decimal skew with skew_band."""
        balance = ref.reference_balance(self.rows, ref.STOCK_FOLDS)
        expected = ref.reference_balance_drift_witness(
            self.rows,
            ref.STOCK_FOLDS,
            float(self.stdout["balance"]["max_label_skew"]),
            self.stdout["balance"]["skew_band"],
        )
        assert self.stdout["balance_drift_witness"] == expected
        assert expected == ref.reference_balance_drift_witness(
            self.rows,
            ref.STOCK_FOLDS,
            float(balance["max_label_skew"]),
            str(balance["skew_band"]),
        )

    def test_epoch_manifest_binder_stock(self) -> None:
        """Stock epoch_manifest_binder must hash rotation_epoch|fold_digest|class_prior_seal."""
        expected = ref.reference_epoch_manifest_binder(
            int(self.stdout["rotation_epoch"]),
            self.stdout["fold_digest"],
            self.stdout["class_prior_seal"],
        )
        assert self.stdout["epoch_manifest_binder"] == expected

    def test_holdout_exclusion_seal_stock(self) -> None:
        """Stock holdout_exclusion_seal must hash train_fold_mask|holdout|fold_load_skew."""
        expected = ref.reference_holdout_exclusion_seal(
            self.stdout["train_fold_mask"],
            int(self.stdout["holdout_fold_id"]),
            int(self.stdout["fold_load_skew"]),
        )
        assert self.stdout["holdout_exclusion_seal"] == expected

    def test_cross_module_fold_kit_seal_includes_additive_fields(self) -> None:
        """fold_kit_seal must change if any of the five additive seal fields is swapped out."""
        base = ref.reference_fold_kit_seal(
            self.stdout["kit_closure"],
            self.stdout["class_prior_seal"],
            self.stdout["fold_split_witness"],
            self.stdout["holdout_epoch_coupler"],
            self.stdout["stratum_stability_index"],
            self.stdout["train_fold_mask"],
            self.stdout["label_pair_cooccurrence"],
            self.stdout["balance_drift_witness"],
            self.stdout["epoch_manifest_binder"],
            self.stdout["holdout_exclusion_seal"],
        )
        assert self.stdout["fold_kit_seal"] == base
        tampered = ref.reference_fold_kit_seal(
            self.stdout["kit_closure"],
            self.stdout["class_prior_seal"],
            self.stdout["fold_split_witness"],
            self.stdout["holdout_epoch_coupler"],
            self.stdout["stratum_stability_index"],
            self.stdout["train_fold_mask"],
            self.stdout["label_pair_cooccurrence"],
            self.stdout["balance_drift_witness"],
            self.stdout["epoch_manifest_binder"],
            "0" * 64,
        )
        assert tampered != base

    def test_receipt_includes_additive_seal_fields(self) -> None:
        """Receipt must include the five additive seal fields matching stdout."""
        last = ref.read_receipt_lines()[-1]
        for key in (
            "train_fold_mask",
            "label_pair_cooccurrence",
            "balance_drift_witness",
            "epoch_manifest_binder",
            "holdout_exclusion_seal",
        ):
            assert last[key] == self.stdout[key]

    def test_multi_step_epoch_shifts_binder_exclusion_and_kit_seal(self) -> None:
        """Epoch advance must shift epoch_manifest_binder, holdout_exclusion_seal, and fold_kit_seal."""
        seen_binder = {self.stdout["epoch_manifest_binder"]}
        seen_exclusion = {self.stdout["holdout_exclusion_seal"]}
        seen_kit = {self.stdout["fold_kit_seal"]}
        for _step in range(3):
            payload = ref.load_stdout_json(ref.run_assemble())
            assert payload["epoch_manifest_binder"] not in seen_binder
            assert payload["holdout_exclusion_seal"] not in seen_exclusion
            assert payload["fold_kit_seal"] not in seen_kit
            seen_binder.add(payload["epoch_manifest_binder"])
            seen_exclusion.add(payload["holdout_exclusion_seal"])
            seen_kit.add(payload["fold_kit_seal"])
            assert payload[
                "epoch_manifest_binder"
            ] == ref.reference_epoch_manifest_binder(
                int(payload["rotation_epoch"]),
                payload["fold_digest"],
                payload["class_prior_seal"],
            )
            assert payload[
                "holdout_exclusion_seal"
            ] == ref.reference_holdout_exclusion_seal(
                payload["train_fold_mask"],
                int(payload["holdout_fold_id"]),
                int(payload["fold_load_skew"]),
            )

    def test_edge_single_fold_train_fold_mask_hashes_empty(self) -> None:
        """With K=1 the only fold is holdout, so train_fold_mask hashes the empty string."""
        ref.reset_var()
        payload = ref.load_stdout_json(ref.run_assemble(folds=1))
        assert int(payload["holdout_fold_id"]) == 0
        assert payload["train_fold_mask"] == hashlib.sha256(b"").hexdigest()
        assignment = ref.reference_assign(self.rows, 1)
        assert payload["train_fold_mask"] == ref.reference_train_fold_mask(
            assignment, int(payload["holdout_fold_id"])
        )

    def test_dynamic_label_pair_cooccurrence_bypass(self) -> None:
        """Random cohort label layout must change label_pair_cooccurrence and fold_kit_seal."""
        ref.reset_var()
        random.seed(424242)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pairs.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 19):
                    label = ["alpha", "beta", "gamma", "delta"][idx % 4]
                    writer.writerow([idx, label, "0.3"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=3, label="strata")
            )
            assignment = ref.reference_assign(rows, 3)
            label_counts = ref.reference_label_counts(rows, assignment)
            expected = ref.reference_label_pair_cooccurrence(assignment, label_counts)
            assert payload["label_pair_cooccurrence"] == expected
            assert (
                payload["label_pair_cooccurrence"]
                != self.stdout["label_pair_cooccurrence"]
            )
            staged_fp = ref.reference_staged_fingerprint(ref.STAGED_PATH)
            coupling = ref.reference_extended_coupling(
                rows, 3, payload["fold_digest"], staged_fp, 1
            )
            assert payload["fold_kit_seal"] == coupling["fold_kit_seal"]
            assert payload["fold_kit_seal"] != self.stdout["fold_kit_seal"]

    def test_dynamic_balance_drift_witness_tracks_skew_band(self) -> None:
        """Skewed cohort must recompute balance_drift_witness from live skew_band."""
        ref.reset_var()
        random.seed(515151)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "drift.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 21):
                    label = "dom" if idx <= 16 else "rare"
                    writer.writerow([idx, label, "0.2"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=4, label="strata")
            )
            expected = ref.reference_balance_drift_witness(
                rows,
                4,
                float(payload["balance"]["max_label_skew"]),
                payload["balance"]["skew_band"],
            )
            assert payload["balance_drift_witness"] == expected
            assert (
                payload["balance_drift_witness"] != self.stdout["balance_drift_witness"]
            )

    def test_cross_module_holdout_exclusion_seal_recomputes(self) -> None:
        """holdout_exclusion_seal must recompute from train_fold_mask, holdout, and fold_load_skew."""
        expected = ref.reference_holdout_exclusion_seal(
            self.stdout["train_fold_mask"],
            int(self.stdout["holdout_fold_id"]),
            int(self.stdout["fold_load_skew"]),
        )
        assert self.stdout["holdout_exclusion_seal"] == expected
        stale = ref.reference_holdout_exclusion_seal(
            self.stdout["train_fold_mask"],
            (int(self.stdout["holdout_fold_id"]) + 1) % ref.STOCK_FOLDS,
            int(self.stdout["fold_load_skew"]),
        )
        assert self.stdout["holdout_exclusion_seal"] != stale

    def test_consistency_train_fold_mask_excludes_holdout(self) -> None:
        """train_fold_mask body must exclude holdout_fold_id from the sorted train id list."""
        holdout = int(self.stdout["holdout_fold_id"])
        train_ids = sorted(fold_id for fold_id in self.assignment if fold_id != holdout)
        body = ",".join(str(fold_id) for fold_id in train_ids)
        assert holdout not in train_ids
        assert (
            self.stdout["train_fold_mask"]
            == hashlib.sha256(body.encode("utf-8")).hexdigest()
        )

    def test_dynamic_train_fold_mask_and_exclusion_bypass(self) -> None:
        """Changing fold count must change train_fold_mask and holdout_exclusion_seal."""
        ref.reset_var()
        random.seed(606060)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mask.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 16):
                    label = ["x", "y", "z"][idx % 3]
                    writer.writerow([idx, label, "0.8"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=7, label="strata")
            )
            assignment = ref.reference_assign(rows, 7)
            expected_mask = ref.reference_train_fold_mask(
                assignment, int(payload["holdout_fold_id"])
            )
            assert payload["train_fold_mask"] == expected_mask
            assert payload["train_fold_mask"] != self.stdout["train_fold_mask"]
            expected_excl = ref.reference_holdout_exclusion_seal(
                payload["train_fold_mask"],
                int(payload["holdout_fold_id"]),
                int(payload["fold_load_skew"]),
            )
            assert payload["holdout_exclusion_seal"] == expected_excl
            assert (
                payload["holdout_exclusion_seal"]
                != self.stdout["holdout_exclusion_seal"]
            )

    def test_dynamic_epoch_manifest_binder_bypass(self) -> None:
        """Novel cohort plus second epoch must recompute epoch_manifest_binder from live digests."""
        ref.reset_var()
        random.seed(707070)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "binder.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 14):
                    label = ["p", "q"][idx % 2]
                    writer.writerow([idx, label, "0.9"])
                    rows.append((str(idx), label))
            first = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=3, label="strata")
            )
            second = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=3, label="strata")
            )
            assert second[
                "epoch_manifest_binder"
            ] == ref.reference_epoch_manifest_binder(
                int(second["rotation_epoch"]),
                second["fold_digest"],
                second["class_prior_seal"],
            )
            assert second["epoch_manifest_binder"] != first["epoch_manifest_binder"]
            assert (
                second["epoch_manifest_binder"] != self.stdout["epoch_manifest_binder"]
            )

    def test_fold_coverage_lattice_stock(self) -> None:
        """Stock fold_coverage_lattice must couple coverage, parity, stability, and cardinality."""
        expected = ref.reference_fold_coverage_lattice(
            self.stdout["label_coverage_seal"],
            self.stdout["fold_parity_digest"],
            self.stdout["stratum_stability_index"],
            int(self.stdout["label_cardinality"]),
        )
        assert self.stdout["fold_coverage_lattice"] == expected
        assert self.manifest["fold_coverage_lattice"] == expected

    def test_holdout_train_tension_stock(self) -> None:
        """Stock holdout_train_tension must bind train mask, exclusion, epoch coupler, and load skew."""
        expected = ref.reference_holdout_train_tension(
            self.stdout["train_fold_mask"],
            self.stdout["holdout_exclusion_seal"],
            self.stdout["holdout_epoch_coupler"],
            int(self.stdout["fold_load_skew"]),
        )
        assert self.stdout["holdout_train_tension"] == expected

    def test_skew_prior_witness_stock(self) -> None:
        """Stock skew_prior_witness must couple drift, priors, coupler, and R max_label_skew."""
        expected = ref.reference_skew_prior_witness(
            self.stdout["balance_drift_witness"],
            self.stdout["class_prior_seal"],
            self.stdout["balance_coupler"],
            float(self.stdout["balance"]["max_label_skew"]),
        )
        assert self.stdout["skew_prior_witness"] == expected

    def test_epoch_receipt_binder_stock(self) -> None:
        """Stock epoch_receipt_binder must couple binder, run chain, receipt chain, and epoch."""
        expected = ref.reference_epoch_receipt_binder(
            self.stdout["epoch_manifest_binder"],
            self.stdout["run_chain_digest"],
            self.stdout["receipt_chain"],
            int(self.stdout["rotation_epoch"]),
        )
        assert self.stdout["epoch_receipt_binder"] == expected

    def test_fold_kit_outer_seal_stock(self) -> None:
        """Stock fold_kit_outer_seal must pipe fold_kit_seal with the four outer lattice fields."""
        expected = ref.reference_fold_kit_outer_seal(
            self.stdout["fold_kit_seal"],
            self.stdout["fold_coverage_lattice"],
            self.stdout["holdout_train_tension"],
            self.stdout["skew_prior_witness"],
            self.stdout["epoch_receipt_binder"],
        )
        assert self.stdout["fold_kit_outer_seal"] == expected
        assert self.manifest["fold_kit_outer_seal"] == expected

    def test_cross_module_outer_seal_from_stdout_components(self) -> None:
        """fold_kit_outer_seal must recompute purely from the five stdout coupling fields."""
        expected = ref.reference_fold_kit_outer_seal(
            self.stdout["fold_kit_seal"],
            self.stdout["fold_coverage_lattice"],
            self.stdout["holdout_train_tension"],
            self.stdout["skew_prior_witness"],
            self.stdout["epoch_receipt_binder"],
        )
        assert self.stdout["fold_kit_outer_seal"] == expected

    def test_cross_module_outer_seal_tamper_detection(self) -> None:
        """Swapping any outer lattice input must change fold_kit_outer_seal."""
        base = ref.reference_fold_kit_outer_seal(
            self.stdout["fold_kit_seal"],
            self.stdout["fold_coverage_lattice"],
            self.stdout["holdout_train_tension"],
            self.stdout["skew_prior_witness"],
            self.stdout["epoch_receipt_binder"],
        )
        assert self.stdout["fold_kit_outer_seal"] == base
        tampered = ref.reference_fold_kit_outer_seal(
            self.stdout["fold_kit_seal"],
            "0" * 64,
            self.stdout["holdout_train_tension"],
            self.stdout["skew_prior_witness"],
            self.stdout["epoch_receipt_binder"],
        )
        assert tampered != base

    def test_multi_step_outer_seal_epoch_sequence(self) -> None:
        """Three sequential assembles must change epoch_receipt_binder and fold_kit_outer_seal each time."""
        seen_binders = {self.stdout["epoch_receipt_binder"]}
        seen_outer = {self.stdout["fold_kit_outer_seal"]}
        for _ in range(2):
            payload = ref.load_stdout_json(ref.run_assemble())
            assert payload["epoch_receipt_binder"] not in seen_binders
            assert payload["fold_kit_outer_seal"] not in seen_outer
            seen_binders.add(payload["epoch_receipt_binder"])
            seen_outer.add(payload["fold_kit_outer_seal"])
            expected = ref.reference_fold_kit_outer_seal(
                payload["fold_kit_seal"],
                payload["fold_coverage_lattice"],
                payload["holdout_train_tension"],
                payload["skew_prior_witness"],
                payload["epoch_receipt_binder"],
            )
            assert payload["fold_kit_outer_seal"] == expected

    def test_dynamic_fold_coverage_lattice_bypass(self) -> None:
        """Novel cohort must recompute fold_coverage_lattice via extended coupling."""
        ref.reset_var()
        random.seed(808080)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lattice.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 18):
                    label = ["a", "b", "c", "d"][idx % 4]
                    writer.writerow([idx, label, "0.5"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=4, label="strata")
            )
            staged_fp = payload["staged_fingerprint"]
            coupling = ref.reference_extended_coupling(
                rows,
                4,
                payload["fold_digest"],
                staged_fp,
                int(payload["rotation_epoch"]),
            )
            assert payload["fold_coverage_lattice"] == coupling["fold_coverage_lattice"]
            assert (
                payload["fold_coverage_lattice"] != self.stdout["fold_coverage_lattice"]
            )

    def test_dynamic_holdout_train_tension_bypass(self) -> None:
        """Changing fold count must shift holdout_train_tension through mask and exclusion."""
        ref.reset_var()
        random.seed(909090)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tension.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 20):
                    label = ["m", "n"][idx % 2]
                    writer.writerow([idx, label, "0.7"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=6, label="strata")
            )
            expected = ref.reference_holdout_train_tension(
                payload["train_fold_mask"],
                payload["holdout_exclusion_seal"],
                payload["holdout_epoch_coupler"],
                int(payload["fold_load_skew"]),
            )
            assert payload["holdout_train_tension"] == expected
            assert (
                payload["holdout_train_tension"] != self.stdout["holdout_train_tension"]
            )

    def test_dynamic_skew_prior_witness_bypass(self) -> None:
        """Imbalanced novel labels must change skew_prior_witness and outer seal together."""
        ref.reset_var()
        random.seed(101010)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "skewprior.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 25):
                    label = "rare" if idx <= 2 else "common"
                    writer.writerow([idx, label, "0.3"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=5, label="strata")
            )
            staged_fp = payload["staged_fingerprint"]
            coupling = ref.reference_extended_coupling(
                rows,
                5,
                payload["fold_digest"],
                staged_fp,
                int(payload["rotation_epoch"]),
            )
            assert payload["skew_prior_witness"] == coupling["skew_prior_witness"]
            assert payload["fold_kit_outer_seal"] == coupling["fold_kit_outer_seal"]
            assert payload["skew_prior_witness"] != self.stdout["skew_prior_witness"]

    def test_dynamic_fold_kit_outer_seal_bypass(self) -> None:
        """Random cohort must recompute fold_kit_outer_seal end-to-end via extended coupling."""
        ref.reset_var()
        random.seed(111222)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "outer.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 16):
                    label = ["u", "v", "w"][idx % 3]
                    writer.writerow([idx, label, "0.4"])
                    rows.append((str(idx), label))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=3, label="strata")
            )
            staged_fp = payload["staged_fingerprint"]
            coupling = ref.reference_extended_coupling(
                rows,
                3,
                payload["fold_digest"],
                staged_fp,
                int(payload["rotation_epoch"]),
            )
            assert payload["fold_kit_outer_seal"] == coupling["fold_kit_outer_seal"]
            assert payload["fold_kit_outer_seal"] != self.stdout["fold_kit_outer_seal"]

    def test_cross_module_coverage_lattice_depends_on_stability(self) -> None:
        """fold_coverage_lattice must change when stratum_stability_index is swapped."""
        base = ref.reference_fold_coverage_lattice(
            self.stdout["label_coverage_seal"],
            self.stdout["fold_parity_digest"],
            self.stdout["stratum_stability_index"],
            int(self.stdout["label_cardinality"]),
        )
        assert self.stdout["fold_coverage_lattice"] == base
        tampered = ref.reference_fold_coverage_lattice(
            self.stdout["label_coverage_seal"],
            self.stdout["fold_parity_digest"],
            "f" * 64,
            int(self.stdout["label_cardinality"]),
        )
        assert tampered != base

    def test_edge_case_single_label_outer_chain(self) -> None:
        """Single-label cohort must still produce a consistent outer seal chain."""
        ref.reset_var()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "single.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "strata", "score"])
                rows: list[tuple[str, str]] = []
                for idx in range(1, 11):
                    writer.writerow([idx, "only", "1.0"])
                    rows.append((str(idx), "only"))
            payload = ref.load_stdout_json(
                ref.run_assemble(dataset=path, folds=5, label="strata")
            )
            assert payload["label_cardinality"] == 1
            expected = ref.reference_fold_kit_outer_seal(
                payload["fold_kit_seal"],
                payload["fold_coverage_lattice"],
                payload["holdout_train_tension"],
                payload["skew_prior_witness"],
                payload["epoch_receipt_binder"],
            )
            assert payload["fold_kit_outer_seal"] == expected

    def test_multi_step_receipt_outer_fields(self) -> None:
        """Second assemble receipt must carry outer seal fields matching stdout."""
        first = self.stdout
        second = ref.load_stdout_json(ref.run_assemble())
        lines = ref.read_receipt_lines()
        assert len(lines) >= 2
        last = lines[-1]
        assert last["fold_kit_outer_seal"] == second["fold_kit_outer_seal"]
        assert last["epoch_receipt_binder"] == second["epoch_receipt_binder"]
        assert last["fold_kit_outer_seal"] != first["fold_kit_outer_seal"]

    def test_submitted_sources_do_not_read_tests_tree(self) -> None:
        """Submitted /app sources must not reference /tests, /solution, or fold_ref."""
        root = Path("/app")
        skip_dirs = {
            "target",
            "vendor",
            ".git",
            "node_modules",
            "__pycache__",
            ".m2",
            "var",
        }
        extensions = {
            ".java",
            ".R",
            ".r",
            ".sh",
            ".properties",
            ".xml",
            ".md",
            ".json",
        }
        banned = re.compile(
            r"(?:/tests(?:/|\b)|/solution(?:/|\b)|fold_ref|verifier_tests_hidden|"
            r"PYTHONPATH\s*=\s*/tests)",
            re.IGNORECASE,
        )
        # Schema and contracts under /app/schema are agent-visible contracts, not cheats.
        allowed_prefix = root / "schema"
        violations: list[str] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in skip_dirs for part in path.parts):
                continue
            if allowed_prefix in path.parents or path.parent == allowed_prefix:
                continue
            if path.suffix not in extensions and path.name not in {
                "foldctl",
                "Dockerfile",
            }:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if banned.search(text):
                violations.append(str(path))
        assert violations == [], (
            f"submitted sources reference verifier tests: {violations}"
        )
