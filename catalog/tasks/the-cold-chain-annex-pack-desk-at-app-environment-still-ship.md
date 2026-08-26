# The cold-chain annex pack desk at `/app/environment` still ships broken hardened

Submission: `3200b371-1bb2-4bf4-ad97-3b3b97cf68f1`  
Slug: `the-cold-chain-annex-pack-desk-at-app-environment-still-ship`  
Latest archive: `3200b371-1bb2-4bf4-ad97-3b3b97cf68f1_submission_2026-07-18T12_01_10.787Z.zip`  
Revisions in Dropbox: 1

## Task summary

The cold-chain annex pack desk at `/app/environment` still ships broken hardened packs. Fix the local toolchain sources under `/app/environment` so rebuilds stay correct; module-level helpers used by that pipeline must behave correctly, not only the driver exit status. Hand-written static pack files are not enough; the verifier regenerates packs through the normal rebuild path and rejects output-only edits. `/app/h7p/pp_run rebuild` (same binary as `/app/environment/h7p/pp_run rebuild`) finishes and the aggregate ledger totals still match the fixture sums, but per-row dependency pins and ABI slots disagree with the held-out rotations in `/app/environment/data/rot_tbl.toml`. `/app/h7p/pp_run health` can look green on smoke totals alone; that is not closure. Operator argv patterns are in `/app/environment/docs/operator_cmds.txt`. Closed-row obligations, band contraction algebra (`band_lo`, `band_hi`, rotation `step`), preamble mux PEER rules, rotation `pin_seed` coupling into tok (not asv), tok/asv dual-key formulas, and the provenance seal digest live in `/app/environment/docs/ctr_rules.md` with schema `/app/environment/schemas/row_v3.schema.json`. Smoke CI shortcuts that keep ledger totals green are in `/app/environment/docs/operator_notes.md`; when those shortcuts conflict with `ctr_rules.md`, the closed-row rules win.

Required artifacts include: `/app/environment`, `/app/h7p/pp_run`, `/app/environment/h7p/pp_run`, `/app/environment/data/rot_tbl.toml`, `/app/environment/docs/operator_cmds.txt`, `/app/environment/docs/ctr_rules.md`, `/app/environment/schemas/row_v3.schema.json`, `/app/environment/docs/operator_notes.md`.

Author anonymous tagged this **hard** build-and-dependency-management task (bash, awk, lockfile, provenance, offline-build, annex).

Time estimates: expert ~180 min, junior ~600 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `3200b371-1bb2-4bf4-ad97-3b3b97cf68f1_submission_2026-07-18T12_01_10.787Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
