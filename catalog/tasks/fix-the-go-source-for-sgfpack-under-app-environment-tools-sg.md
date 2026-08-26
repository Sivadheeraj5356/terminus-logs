# Fix the Go source for `sgfpack` under /app/environment/tools/sgfpack, then use t

Submission: `7b058460-0e5c-45d8-9110-49e077a66a8c`  
Slug: `fix-the-go-source-for-sgfpack-under-app-environment-tools-sg`  
Latest archive: `7b058460-0e5c-45d8-9110-49e077a66a8c_submission_2026-07-19T08_54_19.237Z.zip`  
Revisions in Dropbox: 1

## Task summary

Fix the Go source for `sgfpack` under /app/environment/tools/sgfpack, then use the repaired command to reconcile the Harbor House 5x5 Cup under /app/workspace. The current rounds register, current SGF records, repair state, and output pack may be stale or corrupted; the authorities are the rules document, camera move logs, referee cards, and active adjudication journal entries. A correct repair rebuilds /app/workspace/register/rounds.tsv, /app/workspace/records/current/*.sgf, and /app/workspace/register/repair_state.json from those authorities, including positional-superko forfeits and normal scored games. After the workspace is repaired, regenerate /app/output/sgf-pack with the normal CLI path. The pack contains records/*.sgf, adjudications.json, standings.tsv, and manifest.json; exported records must be byte-identical to the repaired current records. Standings sort by win points, SOS, SODOS, and then player name in ascending order. Re-running repair and export after deleting stale output or stale repair state must converge to the same bytes, and `sgfpack audit --root /app/workspace` must reject any later divergence between the durable evidence, repaired state, register, and SGF records.

Required artifacts include: `/app/environment/tools/sgfpack`, `/app/workspace`, `/app/workspace/register/rounds.tsv`, `/app/workspace/records/current/*.sgf`, `/app/workspace/register/repair_state.json`, `/app/output/sgf-pack`.

Author anonymous tagged this **hard** games task (sgf, superko, tournament, adjudication, go).

Time estimates: expert ~180 min, junior ~720 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `7b058460-0e5c-45d8-9110-49e077a66a8c_submission_2026-07-19T08_54_19.237Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
