# Your team maintains an offline userspace tunnel-rotation simulator under `/app/e

Submission: `2d42987a-a66e-46f2-90d1-36e33d4b6f6e`  
Slug: `your-team-maintains-an-offline-userspace-tunnel-rotation-sim`  
Latest archive: `2d42987a-a66e-46f2-90d1-36e33d4b6f6e_submission_2026-07-12T16_03_45.784Z.zip`  
Revisions: 12

## Task summary

Your team maintains an offline userspace tunnel-rotation simulator under `/app/environment`. After the documented stage pass, peers lose mux coherence during apply replay while a local status view can still read healthy, and sparse run logs can look settled while the terminal reconcile report disagrees across primary peer ids. Repair the C++ sources so the workflow in `/app/environment/docs/operator_cmds.txt` regenerates `/app/output/psk_rotate_report.json`, sparse phase rows under `/app/output/run_traces/`, and witness bytes at `/app/environment/w8g/staged/w8_chain.bin`. Coherence rules, formulas, schema, and profile sequencing are in `/app/environment/docs/public_contract.md`; data index in `/app/environment/docs/formal_rules.md`; report shape in `/app/environment/schemas/row_wg.schema.json`; sparse trace subset in `/app/environment/docs/trace_subset.txt`.

Required artifacts include: `/app/environment`, `/app/environment/docs/operator_cmds.txt`, `/app/output/psk_rotate_report.json`, `/app/output/run_traces/`, `/app/environment/w8g/staged/w8_chain.bin`, `/app/environment/docs/public_contract.md`, `/app/environment/docs/formal_rules.md`, `/app/environment/schemas/row_wg.schema.json`.

Author anonymous tagged this **hard** security task (wireguard, vpn, psk, security, authority-split, cpp).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `2d42987a-a66e-46f2-90d1-36e33d4b6f6e_submission_2026-07-12T16_03_45.784Z.zip` is a task submission, not a Harbor job. 12 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
