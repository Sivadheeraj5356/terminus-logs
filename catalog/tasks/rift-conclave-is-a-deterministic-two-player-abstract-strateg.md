# Rift Conclave is a deterministic two-player abstract strategy game. For each tou

Submission: `50a665fe-73d8-43bb-bce1-9705b69a2f74`  
Slug: `rift-conclave-is-a-deterministic-two-player-abstract-strateg`  
Latest archive: `50a665fe-73d8-43bb-bce1-9705b69a2f74_submission_2026-07-17T04_29_03.342Z.zip`  
Revisions in Dropbox: 1

## Task summary

Rift Conclave is a deterministic two-player abstract strategy game. For each tournament position, the league needs the exact guaranteed score and principal variation under perfect player and rival play. Use the official game rules in `/app/task_file/arena_rules.md`; positions vary in their boards, hands, omen sets, round horizons, and resources. Complete the Go match analyst beginning at `/app/task_file/main.go` and build `/app/task_file/conclave` from the Go package in `/app/task_file`. The league runner compiles that package with `go build` before scoring, so the position analysis must remain in `main.go` or additional `.go` files there; a script or prebuilt executable is not a substitute. Go and `gofmt` are available on `PATH`.

Required artifacts include: `/app/task_file/arena_rules.md`, `/app/task_file/main.go`, `/app/task_file/conclave`, `/app/task_file`, `/app/task_file/input/public_match.json`, `/app/task_file/output/adjudication.json`.

Author Anonymous tagged this **medium** games task (abstract-strategy, perfect-play, adversarial-play, principal-variation, state-transitions).

Time estimates: expert ~240 min, junior ~540 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `50a665fe-73d8-43bb-bce1-9705b69a2f74_submission_2026-07-17T04_29_03.342Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
