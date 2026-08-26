# After a workload tier move, cgroup totals look healthy while policy traces still

Submission: `d64d2df4-2da6-484d-9f3d-bd6ede26e425`  
Slug: `after-a-workload-tier-move-cgroup-totals-look-healthy-while`  
Latest archive: `d64d2df4-2da6-484d-9f3d-bd6ede26e425_submission_2026-07-17T11_33_27.641Z.zip`  
Revisions: 4

## Task summary

After a workload tier move, cgroup totals look healthy while policy traces still attribute events to the old boundary. Fix sources under `/app/environment` and build with `make -C /app/environment all`. Run `/app/environment/tools/j4_round --round`, tail recovery with `--tail`, and emit with `/app/environment/tools/p7_emit --out /app/output/observ_trace.json`. Tick uses tick_apply `--site`. u4.state rows are site, link_cap, pin_epoch; pin_epoch comes from NS_HANDLE so ns_gen_b yields three and ns_gen_a yields one on paired tier. epoch.chain rebind_scope copies pin_epoch per site, never link_cap. replay.witness XORs rebind_scope, publish_a, publish_b, handoff_ord mod 256 and blocks emit. epoch.chain rows are site, rebind_scope, publish_a, publish_b, handoff_ord; window.tick for site_j4 is their sum mod 16, zero maps to one. INHERIT_ARR drives handoff: zero arr1, else arr2 until rebind_scope three then arr3. Work probes read handoff from epoch.chain handoff_ord when present; stale p5.state must not override chain handoff for work admit_code.

Required artifacts include: `/app/environment`, `/app/environment/tools/j4_round`, `/app/environment/tools/p7_emit`, `/app/output/observ_trace.json`.

Author anonymous tagged this **hard** system-administration task (c, cgroup, observability, attach, system-administration).

Time estimates: expert ~60 min, junior ~180 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `d64d2df4-2da6-484d-9f3d-bd6ede26e425_submission_2026-07-17T11_33_27.641Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
