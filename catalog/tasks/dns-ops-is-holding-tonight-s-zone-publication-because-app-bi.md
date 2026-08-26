# DNS ops is holding tonight’s zone publication because `/app/bin/zone-publisher` 

Submission: `1a4146a3-efdf-491c-956e-6853644a80b8`  
Slug: `dns-ops-is-holding-tonight-s-zone-publication-because-app-bi`  
Latest archive: `1a4146a3-efdf-491c-956e-6853644a80b8_submission_2026-07-09T13_44_40.692Z.zip`  
Revisions: 2

## Task summary

DNS ops is holding tonight’s zone publication because `/app/bin/zone-publisher` is giving the wrong answer on a few reviewed change batches. The command takes `--zone`, `--journal`, `--freezes`, `--exceptions`, and `--report`; it should validate the candidate zone and write the publication report described in `/app/docs/`. Please repair the Ruby implementation under `/app` so valid batches return the right publish/block status, the report is deterministic, and fatal input problems exit cleanly without replacing an existing report. Keep stdout empty; stderr is only for fatal errors. The DNS and reporting contracts are already written in `/app/docs/`, and those docs should not be changed.

Required artifacts include: `/app/bin/zone-publisher`, `/app/docs/`.

Author anonymous tagged this **hard** system-administration task (dns, zone-publishing, freeze-windows, operations).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `1a4146a3-efdf-491c-956e-6853644a80b8_submission_2026-07-09T13_44_40.692Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
