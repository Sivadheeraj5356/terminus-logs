# After an aborted write wave, lane A nat_key 10 still emits row_kind live on the 

Submission: `3a528f89-6e97-4907-a1ba-bf24238cfc77`  
Slug: `after-an-aborted-write-wave-lane-a-nat-key-10-still-emits-ro`  
Latest archive: `3a528f89-6e97-4907-a1ba-bf24238cfc77_submission_2026-07-09T14_25_32.845Z.zip`  
Revisions in Dropbox: 3

## Task summary

After an aborted write wave, lane A nat_key 10 still emits row_kind live on the first H6 dual cred chain even though seg_lane_a_seed.jsonl already holds a void row for that key with sweep_gen five and a lower evt_stamp than the live row. Void entries remain in the seg and book fixture streams while a stale live row still wins pick. A later dual chain without H6_RESET settles nat_key 10 to void. For that key the lane A checkpoint wit_fp disagrees with the emitted row wit_fp. With H6_RESET=1 cold pass span_hi values disagree with snap_v2.dat lane spans even though grid_v2.dat reports grid_rev 2. Repair Go sources under /app/environment so /app/tooling/run_h6.sh regenerates /app/output/out_h6.json through the normal dual cred chain. H6_RESET=1 clears var state; H6_WARM_ONLY=1 reruns warm cred b on prior output. Deleting output and rerunning must rebuild a non empty observation set. Hand written JSON and wrapper only changes are not enough. Digest formulas, fixture bindings, and cred phase rules are in /app/environment/cfg/out_h6_contract.md.

Required artifacts include: `/app/environment`, `/app/tooling/run_h6.sh`, `/app/output/out_h6.json`, `/app/environment/cfg/out_h6_contract.md`.

Author anonymous tagged this **hard** data-processing task (go, log-compaction, data-processing, debugging).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `3a528f89-6e97-4907-a1ba-bf24238cfc77_submission_2026-07-09T14_25_32.845Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
