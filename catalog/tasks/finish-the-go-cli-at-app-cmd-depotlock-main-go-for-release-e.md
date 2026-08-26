# Finish the Go CLI at `/app/cmd/depotlock/main.go` for release engineers who need

Submission: `c6bfce8d-e3a0-4e92-b579-e06768d28f3d`  
Slug: `finish-the-go-cli-at-app-cmd-depotlock-main-go-for-release-e`  
Latest archive: `c6bfce8d-e3a0-4e92-b579-e06768d28f3d_submission_2026-07-18T09_55_21.093Z.zip`  
Revisions in Dropbox: 1

## Task summary

Finish the Go CLI at `/app/cmd/depotlock/main.go` for release engineers who need reproducible lock plans from an offline package index. From `/app`, invoke it as `go run /app/cmd/depotlock --index /app/fixtures/public/index.json --project /app/fixtures/public/project.json --out /app/lock-report.json`; all three flag values are replaceable absolute paths, not fixed inputs. The contract at `/app/docs/resolver_contract.md` is authoritative for the input schema and declarative resolution rules. Implement every documented interaction among semantic-version constraints, default and requested features, optional and guarded dependencies, targets, patches, yanked releases, incompatibilities, cycles, repeated roots, and canonical assignment preference. Input object-key and array order must not change the result, unknown fields must be ignored, and all applicable terminal conflict reasons must accumulate exactly as specified.

Required artifacts include: `/app/cmd/depotlock/main.go`, `/app/cmd/depotlock`, `/app/fixtures/public/index.json`, `/app/fixtures/public/project.json`, `/app/lock-report.json`, `/app/docs/resolver_contract.md`.

Author Anonymous tagged this **hard** build-and-dependency-management task (dependency-resolution, constraint-solving, backtracking, lockfiles, semver, features).

Time estimates: expert ~240 min, junior ~600 min.

Harbor timeouts: agent 1200.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `c6bfce8d-e3a0-4e92-b579-e06768d28f3d_submission_2026-07-18T09_55_21.093Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
