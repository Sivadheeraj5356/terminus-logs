# The C++ thin-LTO lane under `/app/environment` links cleanly from a wiped worksp

Submission: `182c0859-2234-49a0-b664-dde068b9b37a`  
Slug: `the-c-thin-lto-lane-under-app-environment-links-cleanly-from`  
Latest archive: `182c0859-2234-49a0-b664-dde068b9b37a_submission_2026-07-10T06_53_42.565Z.zip`  
Revisions in Dropbox: 3

## Task summary

The C++ thin-LTO lane under `/app/environment` links cleanly from a wiped workspace, but incremental relinks can finish while `/app/work/bin/matrix_app` no longer matches a clean rebuild of the same profile state. Repair sources under `/app/environment` so incremental relinks keep summary sidecars, linked symbol sets, and binary probes aligned with generated headers and ABI stamps. Output-only edits are insufficient. Pass scripts under `/app/environment/ci/harness/` must not disable thin LTO or force clean wipes on every incremental step. Wrapped clang under `/app/environment/ci/fake_bin` reports thin-LTO disable attempts.

Required artifacts include: `/app/environment`, `/app/work/bin/matrix_app`, `/app/environment/ci/harness/`, `/app/environment/ci/fake_bin`, `/app/environment/ci/sequences.json`, `/app/output/lto_observation.json`, `/app/environment/docs/summary_format.md`, `/app/environment/docs/build_layout.md`.

Author anonymous tagged this **hard** build-and-dependency-management task (lto, incremental-build, clang, cmake, linker, codegen).

Time estimates: expert ~90 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `182c0859-2234-49a0-b664-dde068b9b37a_submission_2026-07-10T06_53_42.565Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
