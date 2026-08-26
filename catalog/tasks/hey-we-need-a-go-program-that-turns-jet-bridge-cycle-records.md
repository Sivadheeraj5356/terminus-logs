# Hey, we need a Go program that turns jet bridge cycle records into per cycle bil

Submission: `398ef4f2-7500-4671-845d-882590277f5e`  
Slug: `hey-we-need-a-go-program-that-turns-jet-bridge-cycle-records`  
Latest archive: `398ef4f2-7500-4671-845d-882590277f5e_submission_2026-07-09T07_20_51.638Z.zip`  
Revisions: 3

## Task summary

Hey, we need a Go program that turns jet bridge cycle records into per cycle billing lines and a per carrier summary. Records sit in ndjson under /app (or AIRBRIDGE_DATA); outputs go to /app/output (or AIRBRIDGE_OUT). feebook holds rates, caps, uplift, and the off hours window. Read every doc under codex, handbook, tower_logs; output_shapes and cycle_codex first. Write cycles.ndjson, summary.toml, digest.txt. cycles.ndjson has nine keys (cycle_id, carrier_iata, gate_zone, body_code, mtow_tons, dwell_minutes, net_fee_cents, verdict, tier_version), sorted by cycle id then gate zone. summary.toml opens with airbridge_summary_v1 and lists totals rows (carrier_iata, verdict, cycle_count, billed_cents) sorted by carrier then verdict. digest.txt is lowercase hex sha256 over each row's pipe joined fields.

Required artifacts include: `/app/output`.

Author anonymous tagged this **hard** data-processing task (jet-bridge, ramp-billing, versioned-tier, cross-cycle-cap, anchor-swap).

Time estimates: expert ~120.0 min, junior ~300.0 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `398ef4f2-7500-4671-845d-882590277f5e_submission_2026-07-09T07_20_51.638Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
