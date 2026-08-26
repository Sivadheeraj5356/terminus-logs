# Build a reusable Rust 1.85 solver for the dynamic eigenmodes of a three-layer co

Submission: `191831ec-7a1c-499e-afeb-2d567fe8fa69`  
Slug: `build-a-reusable-rust-1-85-solver-for-the-dynamic-eigenmodes`  
Latest archive: `191831ec-7a1c-499e-afeb-2d567fe8fa69_submission_2026-07-17T04_22_34.461Z.zip`  
Revisions in Dropbox: 6

## Task summary

Build a reusable Rust 1.85 solver for the dynamic eigenmodes of a three-layer composite thermal rod. Write Rust 2021 source to `/app/thermal_modes.rs`, compile it with the standard library only to `/app/thermal_modes`, and expose exactly `/app/thermal_modes --input-dir DIR --output-dir DIR`. The program processes every immutable `*.case` file in the input directory and creates one `<name>.json` report per case. Run it on `/app/thermal_problem/cases` so `/app/thermal_mode_results` contains exactly `alloy.json`, `basalt.json`, `ceramic.json`, `glass.json`, and `graphite.json`; never modify an input file. Validate the invocation, paths, all cases, and all numerical results before changing the output path. On any CLI, path, parsing, validation, numerical, or insufficient-root failure, exit non-zero and preserve the pre-existing output path exactly; if it did not exist, leave it absent. Input and output must remain disjoint after resolving existing components and symlinks: neither may equal, contain, or be contained by the other. On success, remove the output path itself without following an output symlink, then create a fresh real directory including missing parents; no stale entry may survive. Repeated runs must be byte-deterministic, and separate concurrent output directories must not interfere. A valid case is UTF-8 text using LF or CRLF and contains exactly one nonblank `key=value` line for each unique key in this set, with no other content: `name`, `modes`, `mu_max`, `mu_step`, `L1`, `k1`, `alpha1`, `c1`, `L2`, `k2`, `alpha2`, `c2`, `L3`, `k3`, `alpha3`, `c3`, `R12`,...

Required artifacts include: `/app/thermal_modes.rs`, `/app/thermal_modes`, `/app/thermal_problem/cases`, `/app/thermal_mode_results`.

Author anonymous tagged this **hard** scientific-computing task (rust, numerical-methods, sturm-liouville, heat-transfer, eigenvalue-sensitivity).

Time estimates: expert ~150 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `191831ec-7a1c-499e-afeb-2d567fe8fa69_submission_2026-07-17T04_22_34.461Z.zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
