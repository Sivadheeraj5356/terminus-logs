# Harden `/app/bin/kev-ledger`, the offline KEV remediation ledger CLI. It must ac

- **UUID:** `df1fc458-6c9f-422a-83f3-c3704bd586bc`
- **Slug:** `harden-app-bin-kev-ledger-the-offline-kev-remediation-ledger`
- **Category:** security
- **Difficulty:** hard

## Summary

Harden `/app/bin/kev-ledger`, the offline KEV remediation ledger CLI. It must accept the contract flags `--index`, `--config`, `--actions`, `--actions-signature`, `--actions-signer`, `--trust-store`, `--profile`, `--state-dir`, `--out-dir`, and `--resume-from`; authenticate every signed catalog fragment and signed action overlay with the configured Ed25519 trust store before parsing bytes; and then publish the deterministic audit bundle described in `/app/environment/docs/ledger_contract.md`.

On a successful run, the bundle under the requested output directory must contain `kev-ledger.json`, `entries.tsv`, `actions.tsv`, `vendor-summary.tsv`, `rebuild-ledger.json`, `manifest.sha256`, and `state/kev-ledger.state.json`, with the same checkpoint also written to `--state-dir/kev-ledger.state.json` when that state directory differs. A resumed run must rebuild byte-stable artifacts from current authenticated inputs and reject stale checkpoints when config, fragment, action, or profile fingerprints change.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
