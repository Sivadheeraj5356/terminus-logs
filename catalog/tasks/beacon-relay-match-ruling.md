# # Beacon Relay match ruling

Submission: `87a94d43-3e05-425b-8361-c8139cb3f2ce`  
Slug: `beacon-relay-match-ruling`  
Latest archive: `87a94d43-3e05-425b-8361-c8139cb3f2ce_submission_2026-07-18T13_15_36.042Z.zip`  
Revisions in Dropbox: 1

## Task summary

Determine the best valid ruling package for the completed Beacon Relay match in `/app/match.json`. Re-read the file on every run and write `/app/output/result.json`. The input has two unique lowercase `players`, a `claimant` among them, a nonnegative integer `budget`, `relay_requirements`, `coordination_costs`, `cells`, `units`, baseline `rounds`, `rulings`, and `dockets`. Cells are `{id:string,neighbors:[cell IDs...],move_cost:positive integer,beacon:nonnegative integer,recharge:nonnegative integer}`. Units are `{id:string,player:string,cell:string,health:positive integer,energy:nonnegative integer,max_energy:nonnegative integer,strength:positive integer}`, initially on distinct cells with energy at most `max_energy`. Actions are `{unit,type:"move",to}`, `{unit,type:"strike",target}`, `{unit,type:"guard"}`, or `{unit,type:"wait"}`; a round has at most one baseline action per unit. A ruling is `{id,cost,requires_all,requires_any,conflicts,round,unit,action}` with nonnegative integer cost, and its nested action names that same unit. `requires_any` is an array of nonempty ID arrays. Each docket is a nonempty ID array. IDs and references are valid; cell neighbors are symmetric, but conflicts need not be listed symmetrically. Dockets partition the rulings.

Required artifacts include: `/app/match.json`, `/app/output/result.json`, `/app/main.go`, `/app/adjudicate`.

Author Anonymous tagged this **hard** games task (go, games, replay, simultaneous-movement).

Time estimates: expert ~300.0 min, junior ~720.0 min.

Harbor timeouts: agent 1800.0s, verifier 300.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `87a94d43-3e05-425b-8361-c8139cb3f2ce_submission_2026-07-18T13_15_36.042Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
