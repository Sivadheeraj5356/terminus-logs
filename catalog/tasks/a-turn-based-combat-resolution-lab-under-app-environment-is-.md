# A turn-based combat resolution lab under `/app/environment` is due for matrix ce

Submission: `37f78793-f79b-4906-9389-cf758425343a`  
Slug: `a-turn-based-combat-resolution-lab-under-app-environment-is-`  
Latest archive: `37f78793-f79b-4906-9389-cf758425343a_submission_2026-07-19T16_16_32.008Z.zip`  
Revisions in Dropbox: 1

## Task summary

A turn-based combat resolution lab under `/app/environment` is due for matrix certification across manifests `sc_m1` through `sc_m5` under profiles `strict_tick` and `loose_tick`, with activation sweeps up to depth 5. Text tails under `/app/environment/fixtures/log_txt/` and the interim tally at `/app/environment/fixtures/tmp/interim_tally.json` are local smoke only; certification is judged solely on the graded matrix artifact. The certified deliverable is `/app/output/cmb_out.json` with `matrix_tag` `cmb_v2`, `violation_total` of `0`, and contract-correct `depth_limit`, `runs`, `cross_digest`, and `repeat_stamp`. Emit it through the lab's published pipeline: `bash /app/environment/scripts/build_lab.sh`, then `/app/bin/mdl_lab` (mirrored at `/app/environment/tools/mdl_lab/mdl_lab`) using the matrix invocation in `/app/environment/docs/lab_contract.md`. That document is authoritative for the stamped row schema, journal/settle recovery, and each run's `codename`, `profile`, `digest_hex`, `violation_rows`, `band_lo`, `band_hi`, `row_count`, `depth_limit`, and `event_bytes_len`.

Required artifacts include: `/app/environment`, `/app/environment/fixtures/log_txt/`, `/app/environment/fixtures/tmp/interim_tally.json`, `/app/output/cmb_out.json`, `/app/environment/scripts/build_lab.sh`, `/app/bin/mdl_lab`, `/app/environment/tools/mdl_lab/mdl_lab`, `/app/environment/docs/lab_contract.md`.

Author anonymous tagged this **hard** games task (games, combat, go, invariants, model-checking, state-recovery).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `37f78793-f79b-4906-9389-cf758425343a_submission_2026-07-19T16_16_32.008Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
