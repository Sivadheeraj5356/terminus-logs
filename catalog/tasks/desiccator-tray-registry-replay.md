# # Desiccator tray registry replay

Submission: `8d619c9e-6b9a-4728-a6c0-653e45e9050e`  
Slug: `desiccator-tray-registry-replay`  
Latest archive: `8d619c9e-6b9a-4728-a6c0-653e45e9050e_submission_2026-07-08T11_27_35.859Z.zip`  
Revisions in Dropbox: 1

## Task summary

The stdlib-only Rust sources at `/app/desiccator_tray_src/` are a partial, broken tray-registry replay tool: they do not compile, and once they build the behavior still disagrees with the normative contract in `/app/task_file/schema.md` in more than one place. Repair the sources in place so they build and match that contract, then install the release binary at `/app/bin/desiccator_tray` (`/app/bin` is on `PATH`). `schema.md` is the source of truth for the field tables, per-op field profile, output shape, reject reasons, and the seed run's expected totals — read it in full and repair every deviation you find. Do not edit the schema or anything under `/app/task_file/`, and do not add `serde` or any other crate; emit the JSON by hand. Build offline: ```text cd /app/desiccator_tray_src CARGO_NET_OFFLINE=true cargo build --release install -m 755 target/release/desiccator_tray /app/bin/desiccator_tray ```

Required artifacts include: `/app/desiccator_tray_src/`, `/app/task_file/schema.md`, `/app/bin/desiccator_tray`, `/app/bin`, `/app/task_file/`, `/app/desiccator_tray_src`, `/app/task_file`, `/app/output/registry.json`.

Author anonymous tagged this **hard** data-processing task (rust, bug-fix, repair, tsv, tray-registry, jsonl-replay).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `8d619c9e-6b9a-4728-a6c0-653e45e9050e_submission_2026-07-08T11_27_35.859Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
