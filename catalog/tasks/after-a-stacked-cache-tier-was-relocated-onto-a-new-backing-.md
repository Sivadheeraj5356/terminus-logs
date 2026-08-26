# After a stacked cache tier was relocated onto a new backing origin, operators ma

Submission: `773fb6bc-dffe-4ba5-a68f-bdb780bcee46`  
Slug: `after-a-stacked-cache-tier-was-relocated-onto-a-new-backing-`  
Latest archive: `773fb6bc-dffe-4ba5-a68f-bdb780bcee46_submission_2026-07-21T05_04_57.400Z.zip`  
Revisions in Dropbox: 7

## Task summary

After a stacked cache tier was relocated onto a new backing origin, operators materialize scratch workspaces with the `cvctl` tree under `/app/environment`. Mapped-slot rereads may still serve older fast-lane payloads while authority surfaces converge. Tap tallies can advance during an open relocation window. Operator artifacts may report a settled posture while origin alias, active ref, promotion seal, or quorum witnesses still lag the post-move origin. Rebuild `cvctl` from `/app/environment` so the operator workflow in `/app/environment/docs/toolchain.md` converges on fresh scratch trees copied from `/app/environment/samples/`. Hand-written artifact edits alone are insufficient. The verifier rebuilds `/tmp/cvctl`, materializes workspaces with `cvctl copy`, and exercises `status`, `invariant`, `recover`, and `read-replay` across sample event logs under `/app/environment/samples/run_*/events.jsonl`. Normal commands regenerate the operator artifacts documented in `/app/environment/docs/toolchain.md`. `/app/environment/docs/digest_ref.py` must agree with `hash_view.fprint`.

Required artifacts include: `/app/environment`, `/app/environment/docs/toolchain.md`, `/app/environment/samples/`, `/app/environment/samples/run_*/events.jsonl`, `/app/environment/docs/digest_ref.py`.

Author anonymous tagged this **hard** system-administration task (lvm, cache, pvmove, authority, go, system-administration).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `773fb6bc-dffe-4ba5-a68f-bdb780bcee46_submission_2026-07-21T05_04_57.400Z.zip` is a task submission, not a Harbor job. 7 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
