# Asterism Color offline release pack

Submission: `00370df0-ef0e-4c44-aa72-dce65f4d38db`  
Slug: `asterism-color-offline-release-pack`  
Latest archive: `00370df0-ef0e-4c44-aa72-dce65f4d38db_submission_2026-07-20T13_21_26.917Z.zip`  
Revisions: 1

## Task summary

Asterism Color offline release pack The foundry masters under `/app/foundry-sources` are sealed. Do not rewrite them, the FEA sources, color UFOs, or `/app/asterism-ledger` inputs. Commission the offline release pack entrypoint named in `/app/asterism-spec/RELEASE_CONTRACT.md` so a default pack materializes `/app/out/colr-crate` from those masters using the pinned font toolchain already on PATH. Dropping finished fonts by hand is not enough: that pack command regenerates the crate, and checks re-run it before auditing the finished inventory. Do not fetch packages from the network.

Required artifacts include: `/app/foundry-sources`, `/app/asterism-ledger`, `/app/asterism-spec/RELEASE_CONTRACT.md`, `/app/out/colr-crate`, `/app/asterism-ledger/release.toml`, `/app/proof-strings`, `/app/out/colr-crate/AsterismColor-VF.ttf`, `/app/out/colr-crate/AsterismColor-VF.woff2`.

Author anonymous tagged this **hard** build-and-dependency-management task (colrv1, variable-font, woff2, reproducible-builds, release-packaging).

Time estimates: expert ~300 min, junior ~720 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `00370df0-ef0e-4c44-aa72-dce65f4d38db_submission_2026-07-20T13_21_26.917Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
