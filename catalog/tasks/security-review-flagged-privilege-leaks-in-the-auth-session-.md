# Security review flagged privilege leaks in the auth session authority model unde

Submission: `41e66a22-b1ed-4eef-bfd9-45555130451e`  
Slug: `security-review-flagged-privilege-leaks-in-the-auth-session-`  
Latest archive: `41e66a22-b1ed-4eef-bfd9-45555130451e_submission_2026-07-18T18_51_11.968Z.zip`  
Revisions in Dropbox: 1

## Task summary

Security review flagged privilege leaks in the auth session authority model under `/app/environment`. Prior session generations can stay admit-capable after rotation (including skipped-generation seal chains), idle soft-refresh can stretch absolute lifetime past the issued privilege window across a long refresh sequence, concurrent session occupancy can slip the principal RBAC budget under login surge, and terminal journals can omit integrity fields while stage reports look fine. The authority model must satisfy `/app/environment/docs/verify_contract.md` for both `tight` and `loose`: dual-valid windows stay closed across the full rotation peak, `abs_deadline` stays issued-plus-lifetime under soft refresh, surge occupancy seats at the principal budget, and `/app/output/epoch.ledger` stays coherent across repeated matrix runs and corruption recovery (exactly 8 ledger rows). Acceptance is the terminal `/app/output/witness.json` from `/app/environment/tools/sf_verify/sf_verify --matrix all --profiles tight,loose --witness-out /app/output/witness.json` after a successful `/app/environment/scripts/build_all.sh`; `/app/output/stage` and `/app/output/logs` alone are not enough. Status tokens `FRESH_OK`, `REUSE_HIT`, and `CAP_HOLD` live in `/app/environment/docs/status_glossary.md`. Migration recovery must use `/app/environment/migrations/v2_hold.sh --recover` so samples under `/app/environment/samples/raw_bytes` and `/app/output/recovery.marker` stay consistent. Digest helpers used during scoring live in `/app/environment/tools/digest_hex.py`. Checker-only patches, static...

Required artifacts include: `/app/environment`, `/app/environment/docs/verify_contract.md`, `/app/output/epoch.ledger`, `/app/output/witness.json`, `/app/environment/tools/sf_verify/sf_verify`, `/app/environment/scripts/build_all.sh`, `/app/output/stage`, `/app/output/logs`.

Author anonymous tagged this **hard** security task (authentication, authorization, session-token, privilege-boundary, rbac, token-reuse).

Time estimates: expert ~210 min, junior ~540 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `41e66a22-b1ed-4eef-bfd9-45555130451e_submission_2026-07-18T18_51_11.968Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
