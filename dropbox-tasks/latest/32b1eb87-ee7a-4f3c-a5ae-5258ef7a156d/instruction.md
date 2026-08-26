Operators report a frustrating pattern in our bundled network configuration lab: declarative apply banners return success, status listings show updated rows, yet live links keep old address masks and routes. Daemon listing traces disagree with address-equivalent probes and with regenerated observation rows for the same replay sequence. Rapid apply sequences leave stale daemon cache rows visible while declarative stamps already advanced.

Repair the C source code under `/app/environment` so the normal pipeline regenerates `/app/output/n8_observations.json`. Run each batch entry documented in `/app/docs/n8_run_notes.md` through `/app/tools/n2_driver`, then run `/app/tools/w8_emit`. The observation schema, row fields, and `lane_digest` line format are defined in `/app/docs/n8_contract.md`.

Requirements:

- Cross-surface agreement: rows with `gate_code` `D` must carry zero `cfg_mask`, `sample_mask`, and `live_mask`. Accepted rows must reconcile all three mask columns with the live address probe captured for that key and generation during replay. Fixture `carrier=down` lines model a transient carrier-delay window during replay, not a permanent denial; once carrier polling completes and masks reconcile, those rows must reach `gate_code` `A` (including accepted zero masks after teardown). Equal mask columns in the JSON alone are not enough; the live probe state after replay must also be correct.
- Profile label is `concurrency_ordering`. Follow `/app/docs/n8_contract.md` for JSON shape, mask encoding, gate rules, and fnv32 digest recipe.
- Verifier deletes `/app/output/n8_observations.json` and reruns the documented batch sequence before scoring. Hand-written JSON, fixture-only edits, test changes, or wrapper-only timing sleeps are insufficient.
- Rebuild with `make -C /app/environment -j2` after source edits so `/app/tools/n2_driver` and `/app/tools/w8_emit` pick up changes. The verifier rebuilds the lab the same way before replaying batches.

Do not satisfy grading by editing replay fixtures alone or by forcing link-up without address parity across combined batches.
