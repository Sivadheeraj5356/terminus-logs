# Scope this work strictly as offline security configuration and incident response

Submission: `74c48223-9690-4a43-bfd6-ca88fe4a01ae`  
Slug: `scope-this-work-strictly-as-offline-security-configuration-a`  
Latest archive: `74c48223-9690-4a43-bfd6-ca88fe4a01ae_submission_2026-07-20T11_33_21.721Z.zip`  
Revisions in Dropbox: 2

## Task summary

Scope this work strictly as offline security configuration and incident response for a factory StreamVault NVR. The deliverable is a remediated deployment bundle—not an application feature, API, library, service endpoint, or reusable software product. Recover the export under `/workspace/streamvault/input` using the supplied administrative recovery hook at `/workspace/streamvault/src/harden.mjs`; its audited invocation accepts `--fleet-db`, `--runbook`, `--input`, and `--output`. Compliance records must show real use of the host's approved `sqlite3`, `jq`, `yq`, and `sha256sum` commands for registry access, configuration normalization, YAML handling, and bundle checksums. Use the fixed policy date `2025-12-31`, never the system clock, and derive deployment values from the supplied registry and export rather than embedding the sample site. Apply the eight controls in `/workspace/streamvault/docs/operator-runbook.md`: use the approved identity and primary bind; remove `security.admin_password` without exposing it and set `security.admin_password_env` to `STREAMVAULT_ADMIN_PASSWORD`; disable anonymous access; require TLS; isolate service bindings; and derive retention and camera-ingest ports from valid registry rows. An enabled camera port outside inclusive range `1024..65535` is fatal. Publish ingest mappings exactly as `127.0.0.1:<port>:<port>/tcp` in numeric order. Camera media is evidence only when it belongs to an enabled site camera and is a regular, non-symlink file directly under `input/media`. Apply an exception only when its site, control, expiry, value, and...

Required artifacts include: not named as `/app` paths.

Author anonymous tagged this **hard** security task (streamvault, configuration-hardening, sqlite, jq, yq).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 900.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=weak, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `74c48223-9690-4a43-bfd6-ca88fe4a01ae_submission_2026-07-20T11_33_21.721Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
