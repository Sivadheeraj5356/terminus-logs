We need the offline artifact release quorum gate finished before custody can sign off on binary promotions. The Zig tree under `/app` already compiles to `/app/bin/quorumgate`, but evaluation is still stubbed — nothing checks the Ed25519 counter-signatures or weighted quorum math from the contracts.

Read `/app/docs/format.md`, `/app/docs/sign_contract.md`, and `/app/docs/digest_contract.md`. Bundled packs are under `/app/data/bundles/`.

Zig is installed at `/usr/local/zig/zig`. Build offline from `/app`:

```
/usr/local/zig/zig build -Doptimize=ReleaseSafe
/app/bin/quorumgate --bundle /app/data/bundles/<bundle_id>/bundle.json --output /app/output/release_audit.json
```

Write `/app/output/release_audit.json` with `bundle_id`, `eval_profile` (`artifact-quorum-v1`), `results` sorted by `query_id`, `stats`, and `state_digest`. Each result row carries `query_id`, `decision`, `reason`, `quorum_weight`, `signatures_verified`, and `unique_custodians` as defined in the docs. Same bundle on unchanged inputs must produce byte-identical JSON. Runtime has no network — do not apt or fetch anything at run time. Do not hand-edit the audit JSON or touch verifier files.
