# Match transcripts under /app/data/tapes/ came from an internal ladder client, bu

Submission: `113eaf41-5192-4eb9-a08e-de8b4d19d701`  
Slug: `match-transcripts-under-app-data-tapes-came-from-an-internal`  
Latest archive: `113eaf41-5192-4eb9-a08e-de8b4d19d701_submission_2026-07-18T08_40_29.448Z.zip`  
Revisions: 1

## Task summary

Match transcripts under /app/data/tapes/ came from an internal ladder client, but the published rule card is gone. Repair the Rust sources under /app/environment, rebuild with /app/environment/scripts/bake_rs.sh, then run the full grid checker at /app/environment/bin/grti_matrix_k9 as described in /app/environment/docs/operators.md so every arm and grid pair passes. Hand-writing or manually editing the witness artifact is insufficient; the normal pipeline must regenerate /app/output/rule_witness.json from repaired sources. Success means exit code 0 for all four arms (cedar, maple, birch, willow) under both band profiles (dawn, dusk). The graded artifact is /app/output/rule_witness.json. It must contain rows, journal_tail, and spread_ladder. Each row binds replay_hex to move_digest per /app/environment/docs/pact_k7.md. Fork scope agreement compares the first 24 characters of replay_hex across arms.

Required artifacts include: `/app/data/tapes/`, `/app/environment`, `/app/environment/scripts/bake_rs.sh`, `/app/environment/bin/grti_matrix_k9`, `/app/environment/docs/operators.md`, `/app/output/rule_witness.json`, `/app/environment/docs/pact_k7.md`, `/app/output/logs`.

Author anonymous tagged this **hard** games task (reverse-engineering, rust, games, go-rules, trace-inference, serialization).

Time estimates: expert ~90 min, junior ~180 min.

Harbor timeouts: agent 900s, verifier 450s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `113eaf41-5192-4eb9-a08e-de8b4d19d701_submission_2026-07-18T08_40_29.448Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
