# Harden `/app/bin/kev-ledger`, the offline KEV remediation ledger CLI. It must ac

Submission: `df1fc458-6c9f-422a-83f3-c3704bd586bc`  
Slug: `harden-app-bin-kev-ledger-the-offline-kev-remediation-ledger`  
Latest archive: `df1fc458-6c9f-422a-83f3-c3704bd586bc_submission_2026-07-19T14_44_25.954Z.zip`  
Revisions in Dropbox: 4

## Task summary

Harden `/app/bin/kev-ledger`, the offline KEV remediation ledger CLI. It must accept the contract flags `--index`, `--config`, `--actions`, `--actions-signature`, `--actions-signer`, `--trust-store`, `--profile`, `--state-dir`, `--out-dir`, and `--resume-from`; authenticate every signed catalog fragment and signed action overlay with the configured Ed25519 trust store before parsing bytes; and then publish the deterministic audit bundle described in `/app/environment/docs/ledger_contract.md`. On a successful run, the bundle under the requested output directory must contain `kev-ledger.json`, `entries.tsv`, `actions.tsv`, `vendor-summary.tsv`, `rebuild-ledger.json`, `manifest.sha256`, and `state/kev-ledger.state.json`, with the same checkpoint also written to `--state-dir/kev-ledger.state.json` when that state directory differs. A resumed run must rebuild byte-stable artifacts from current authenticated inputs and reject stale checkpoints when config, fragment, action, or profile fingerprints change.

Required artifacts include: `/app/bin/kev-ledger`, `/app/environment/docs/ledger_contract.md`.

Author anonymous tagged this **hard** security task (ed25519, detached-signatures, artifact-integrity, cisa-kev, security-audit).

Time estimates: expert ~180 min, junior ~300 min.

Harbor timeouts: agent 1200.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `df1fc458-6c9f-422a-83f3-c3704bd586bc_submission_2026-07-19T14_44_25.954Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
