# Output schema

boiloff-report.json version string is boiloff-report-v1.

Top-level fields include source_hash, stage_hash, total_tanks, balanced_tanks, imbalanced_tanks, tanks array, corrective_actions array, and report_hash.

Each tanks row includes tank_id, status, heat_leak_bog_tonnes, relief_bog_tonnes, imbalance_pct, and violations.

corrective-actions.tsv is tab-separated with header tank_id, action, reason, value.

report_hash follows hash-contract.md over all report fields except report_hash itself.
