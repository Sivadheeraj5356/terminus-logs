# offline workspace layout

driver rebuild entry is `bash /app/environment/driver/exec_w0.sh` with profile warm or cold.
incremental delta adds the merge flag so wave_b applies on top of wave_a.
second-tier delta uses `--merge-tier 2` so wave_c applies on the wave_a plus wave_b snapshot.
worker wrapper is `bash /app/environment/work/run_w5.sh` with profile warm or cold.
pipeline stages use embedded python3 helpers in the environment tree; jq is not installed in the image.

outputs land under `/app/output/` as staging_manifest.json, phase_journal.json, and loader_trace.json.

contract rules and experiment list are in environment/docs/k4_contract.md.
case drills are in environment/cases/.
do not edit json under `/app/output/` by hand or mutate environment/bundles/k6preserve/.
