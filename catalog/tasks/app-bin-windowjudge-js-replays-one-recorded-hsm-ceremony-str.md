# `/app/bin/windowjudge.js` replays one recorded HSM ceremony stream. It reads one

Submission: `ea62cbb7-280a-4ca6-9758-7f3620245a6a`  
Slug: `app-bin-windowjudge-js-replays-one-recorded-hsm-ceremony-str`  
Latest archive: `ea62cbb7-280a-4ca6-9758-7f3620245a6a_submission_2026-07-20T03_19_45.161Z.zip`  
Revisions: 5

## Task summary

`/app/bin/windowjudge.js` replays one recorded HSM ceremony stream. It reads one JSON document on stdin and writes exactly `{"intervals":[...]}` on stdout. Each interval has `start`, `end`, `reason`, and exactly one actor field, `key`, `package`, `sensor`, or `player`; if no windows are confirmed, `intervals` is an empty array. The input has `until`, `events`, and exactly one top-level mode array: `keys`, `packages`, `sensors`, or `players`. Rows are half-open, open rows close at `until`, and output rows are sorted by actor value and then numeric `start`.

Required artifacts include: `/app/bin/windowjudge.js`, `/app/docs/ceremony-windows.md`.

Author anonymous tagged this **hard** security task (hsm-ceremony, state-machine, interval-reconstruction).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `ea62cbb7-280a-4ca6-9758-7f3620245a6a_submission_2026-07-20T03_19_45.161Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
