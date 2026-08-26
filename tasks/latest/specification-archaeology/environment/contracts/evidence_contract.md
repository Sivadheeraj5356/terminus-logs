# Evidence and profile input contract

`evidence/incident.json` contains `incident_id`, `assessment_at`, `policy_revision`, `severity`, `evidence_root`, and arrays named `objects`, `paths`, `services`, `witnesses`, `revocations`, `exceptions`, and `conflicts`.

Objects use `id`, `kind`, `disableable`, and when relevant `issued_at` or `compromised_at`. Paths use `id`, `service`, and ordered `objects`. Services use `id`, `critical`, `mandatory_emergency`, and integer `disruption_weight`. Witnesses use `id`, `authority`, `independence_parent`, `signed_at`, `valid_from`, `valid_until`, `incident`, and `root`. Revocations use `id`, `object`, `published_at`, `effective_at`, `retroactive`, and `evidence`. Exceptions use `id`, `service`, `path`, `incident`, `approved_at`, `valid_from`, `valid_until`, `retrospective`, and `evidence`. Conflicts use `id`, `left`, `right`, `evidence`, and optional `affects`; each side has `source`, `scope`, and `time`.

Each file under `cases` is an object with `profile`, `remove_witnesses`, `revocation_overrides`, `exception_overrides`, and `severity`. Apply the removal list, then shallow-merge overrides into matching record IDs. The supplied cases include evidence identifiers `CF-4`, `P_PAY_BLUE`, `P_PAY_RED`, and `P_SETTLE`, and service IDs `payments_ingress`, `settlement_api`, and `emergency_capture`; these identify records, not derived verdicts.

`run.sh` supplies `--environment /app/environment --output /app/out` to the answer program. `--ctrf` belongs only to verifier reporting and is not an answer-program input. All times are UTC RFC 3339 strings and compare chronologically in this corpus. The digest algorithm token `sha256` means SHA-256.
