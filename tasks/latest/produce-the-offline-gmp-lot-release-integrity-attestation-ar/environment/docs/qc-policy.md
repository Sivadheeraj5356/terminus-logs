# Control-test completion policy

Required quality-control tests for the pharmaceutical lot are listed in batch_policy.json under required_qc_tests. A test counts toward release only when its qc_records.json row has status approved. Rows with status pending, rejected, or complete do not satisfy the requirement.

Every required test id must appear with status approved. When a required test is missing or not approved, the qc gate adds blocker missing-qc: followed by the test id.

When an approved row has signed_off strictly after batch.json manufacturing_end, the qc gate adds blocker late-signoff: followed by the test id. Dates use YYYY-MM-DD and compare as calendar ordinals.

The qc gate passes only when its blockers list is empty. Blockers are sorted lexicographically.
