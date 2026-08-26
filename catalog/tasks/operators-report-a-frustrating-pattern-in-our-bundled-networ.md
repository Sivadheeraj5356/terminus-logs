# Operators report a frustrating pattern in our bundled network configuration lab:

Submission: `32b1eb87-ee7a-4f3c-a5ae-5258ef7a156d`  
Slug: `operators-report-a-frustrating-pattern-in-our-bundled-networ`  
Latest archive: `32b1eb87-ee7a-4f3c-a5ae-5258ef7a156d_submission_2026-07-09T13_24_57.230Z.zip`  
Revisions: 1

## Task summary

Operators report a frustrating pattern in our bundled network configuration lab: declarative apply banners return success, status listings show updated rows, yet live links keep old address masks and routes. Daemon listing traces disagree with address-equivalent probes and with regenerated observation rows for the same replay sequence. Rapid apply sequences leave stale daemon cache rows visible while declarative stamps already advanced. Repair the C source code under `/app/environment` so the normal pipeline regenerates `/app/output/n8_observations.json`. Run each batch entry documented in `/app/docs/n8_run_notes.md` through `/app/tools/n2_driver`, then run `/app/tools/w8_emit`. The observation schema, row fields, and `lane_digest` line format are defined in `/app/docs/n8_contract.md`.

Required artifacts include: `/app/environment`, `/app/output/n8_observations.json`, `/app/docs/n8_run_notes.md`, `/app/tools/n2_driver`, `/app/tools/w8_emit`, `/app/docs/n8_contract.md`.

Author anonymous tagged this **hard** system-administration task (netplan, networkd, networkctl, networking, concurrency).

Time estimates: expert ~45 min, junior ~180 min.

Harbor timeouts: agent 1200s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `32b1eb87-ee7a-4f3c-a5ae-5258ef7a156d_submission_2026-07-09T13_24_57.230Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
