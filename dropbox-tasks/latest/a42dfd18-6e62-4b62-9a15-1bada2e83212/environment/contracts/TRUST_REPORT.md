# Backup trust report contract

Write exactly one file: /app/verdicts/backup_trust_report.json
UTF-8 JSON with a trailing newline. Repeated runs on the same inputs must be byte identical.

## Top level

Keys are exactly summary then archives. No other top level keys.

### JSON key order (normative)

Top level: summary, archives.

summary: archives_analyzed, archives_at_risk, clean_archives, total_findings, critical_archives, trustworthiness_mean, archives_abs_path.

Each archives[] element: archive_id, trust_tier, risk_score, trustworthiness, findings, coverage_gaps, unauthorized_mutations, escrow_breaks, recovery_weaknesses, retention_tampers, recovery_guarantee_fails, stale_dependencies, restore_forgeries, silent_corruptions, resilience_fails, evidence.

Each findings[] element: kind, subject, detail.

Each coverage_gaps[] element: object_id, cipher, reason.

Each unauthorized_mutations[] element: object_id, content_digest, declared_digest, reason.

Each escrow_breaks[] element: key_id, valid_shares, required_quorum, reason.

Each recovery_weaknesses[] element: reason.

Each retention_tampers[] element: declared_days, enforced_days, reason.

Each recovery_guarantee_fails[] element: key_id, object_id, reason.

Each stale_dependencies[] element: subject, kind, value.

Each restore_forgeries[] element: signer, reason.

Each silent_corruptions[] element: shard_id, reason.

Each resilience_fails[] element: test_id, reason.

Each evidence[] element: kind, ref.

## summary

archives_analyzed equals the number of loaded archive_01 through archive_20 files.
archives_at_risk counts rows with risk_score greater than 0.
clean_archives counts rows with risk_score equal to 0.
total_findings is the sum of len(findings) across rows.
critical_archives counts rows whose trust_tier is critical.
trustworthiness_mean is the integer floor of the sum of trustworthiness values divided by archives_analyzed.
archives_abs_path is the absolute resolved archives directory path used for the run.

## Empty collections

When a list has no items emit [] never null.

## Sorting

archives sorted by archive_id ascending.
findings sorted by kind then subject then detail ascending.
Typed finding lists sorted by their primary identifier fields ascending.
evidence sorted by kind then ref ascending.

## Scoring

risk_score is the sum of policy weights for each emitted finding kind, capped at scoring.cap.
trustworthiness is scoring.cap minus risk_score.
trust_tier comes from policy tiers ranges inclusive.

## Assessment rules

Apply rules from /app/rules/escrow_matrix.yaml and /app/contracts/ARCHIVE_FORMAT.md.
Derive every finding from archive payloads. Do not embed answer tables.

## Bundled verifier expectations

Ignore any JSON file in the archives directory that is not named archive_01.json through archive_20.json.
Honor EBTA_ARCHIVES_DIR when set.
