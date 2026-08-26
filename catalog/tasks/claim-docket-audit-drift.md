# # Claim docket audit drift

Submission: `c94f137c-ac7b-4039-8a7e-4baeaa4467ca`  
Slug: `claim-docket-audit-drift`  
Latest archive: `c94f137c-ac7b-4039-8a7e-4baeaa4467ca_submission_2026-07-08T16_07_22.140Z.zip`  
Revisions in Dropbox: 1

## Task summary

Replication QA reports the Go claim docket seal auditor under `/app/environment` no longer matches independent recomputation from fixture bytes on practice and regression trees. Repair sources under `/app/environment` so the normal pipeline regenerates `/app/out/claim_docket_audit.json`. The verifier rebuilds `/app/bin/claimdocketaudit` from sources and reruns audits across fixture directories; hand-written JSON without that pipeline is insufficient. Do not edit `/tests`.

Required artifacts include: `/app/environment`, `/app/out/claim_docket_audit.json`, `/app/bin/claimdocketaudit`, `/app/environment/docs/tally_rules.md`, `/app/environment/docs/checkpoint_contract.md`, `/app/environment/docs/ledger_contract.md`, `/app/environment/docs/wire_layout.md`, `/app/environment/docs/operators.md`.

Author anonymous tagged this **hard** data-processing task (go, claims, docket, checkpoint, audit, settlement).

Time estimates: expert ~240 min, junior ~720 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `c94f137c-ac7b-4039-8a7e-4baeaa4467ca_submission_2026-07-08T16_07_22.140Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
