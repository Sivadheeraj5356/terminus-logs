# The hex skirmish adjudicator under `/app/environment/skirmish` resolves battle s

Submission: `6ca8779f-d958-4709-88cf-e985b6f91cce`  
Slug: `the-hex-skirmish-adjudicator-under-app-environment-skirmish`  
Latest archive: `6ca8779f-d958-4709-88cf-e985b6f91cce_submission_2026-07-17T16_50_26.794Z.zip`  
Revisions: 1

## Task summary

The hex skirmish adjudicator under `/app/environment/skirmish` resolves battle scenarios into a deterministic transcript. Current rebuilds disagree with the rulebook on interrupt chains, vision, and armor interactions. Repair the Rust sources under `/app/environment` so `/app/bin/skirmish` regenerates reports that match the contract below. Static report writes are not enough; the verifier rebuilds from source and re-runs adjudication. Work from `/app`. Build and run only through `/app/bin/skirmish` (it rebuilds with `cargo build --release --locked` from `/app/environment/skirmish` before executing). Offline only. Key requirements: Reject as invalid (status `INVALID`) when any unit hex is out of bounds, on a blocked cell, or two units share a hex. Prefer reason `OOB`, then `BLOCKED`, then `OVERLAP` when more than one applies (check units in ascending `id`).; Initiative order: descending `speed`, ties broken by ascending `id`.; Process units in initiative order. For each living unit, emit `TURN_START`, then attempt each listed action in order. If the unit dies or morale-breaks mid-turn, drop remaining actions.; `MOVE` actions are spelled `MOVE:x,y` (example `MOVE:2,1`). The destination must be one of the six neighbors `[x+1,y], [x-1,y], [x,y+1], [x,y-1], [x+1,y-1], [x-1,y+1]` of the unit's current hex, in bounds, not blocked, and unoccupied. Emit `MOVE` with `from`/`to`. Illegal move emits `ACTION_FAIL` with `detail`=`ILLEGAL_MOVE` and skips that action only..

Required artifacts include: `/app/environment/skirmish`, `/app/environment`, `/app/bin/skirmish`.

Author anonymous tagged this **hard** games task (hex-grid, turn-resolution, rust, determinism).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `6ca8779f-d958-4709-88cf-e985b6f91cce_submission_2026-07-17T16_50_26.794Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
