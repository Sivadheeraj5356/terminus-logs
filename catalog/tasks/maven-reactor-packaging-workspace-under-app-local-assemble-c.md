# Maven reactor packaging workspace under /app. Local assemble-check stays green, 

Submission: `2cd5db6c-dfb6-4b38-abc7-7433d24199e4`  
Slug: `maven-reactor-packaging-workspace-under-app-local-assemble-c`  
Latest archive: `2cd5db6c-dfb6-4b38-abc7-7433d24199e4_submission_2026-07-15T14_42_58.840Z.zip`  
Revisions in Dropbox: 5

## Task summary

Maven reactor packaging workspace under /app. Local assemble-check stays green, yet /app/output/ffm_ledger.json still shows per-classifier native jar bindings and module-path lane assignments disagreeing with the toolchain pin table once scenario packs vary host architecture, secondary toolchain, and classpath versus module-path jar presence. The reactor is offline and processes every pack under /app/data/scenarios. Drive /app/bin/reactor across the scenario packs so every ledger row is coherent. Each row carries case_id, path_mode, classifier_pick, path_lane, stamp_bind, soname_mark, stub_gate, bind_ok, and row_token for both classpath and module-path. The ledger top level is a single object with key cases whose value is an object keyed by case_id. Each case object carries case_id, entries, assemble_ok, and state_hash. Also write /app/output/reactor_claim.json with assemble_ok and checked. Replay must reproduce the same tokens. Green /app/output/reactor_claim.json alone is not acceptance.

Required artifacts include: `/app/output/ffm_ledger.json`, `/app/data/scenarios`, `/app/bin/reactor`, `/app/output/reactor_claim.json`, `/app/data/catalog`, `/app/modules`.

Author anonymous tagged this **hard** build-and-dependency-management task (java, jextract, ffm, classifier, module-path).

Time estimates: expert ~120 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `2cd5db6c-dfb6-4b38-abc7-7433d24199e4_submission_2026-07-15T14_42_58.840Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
