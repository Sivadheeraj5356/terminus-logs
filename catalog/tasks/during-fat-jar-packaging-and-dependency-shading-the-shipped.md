# During fat-jar packaging and dependency shading the shipped package relocation c

Submission: `d2365ecd-5d1c-4f4d-af67-da77d7b3d062`  
Slug: `during-fat-jar-packaging-and-dependency-shading-the-shipped`  
Latest archive: `d2365ecd-5d1c-4f4d-af67-da77d7b3d062_submission_2026-07-20T15_12_53.045Z.zip`  
Revisions: 8

## Task summary

During fat-jar packaging and dependency shading the shipped package relocation consistency validator must analyze twenty bundled packaging relocation batches under /app/reloc-batches that model Maven-shade style dependency namespace remaps across jar artifacts and write one packaging CI report to /app/artifacts/relocation_consistency_report.json. Implement EvaluateBatch in /app/reloclogic/evaluate.go using /app/RELOCATION_SPEC.md, /app/REPORT_LAYOUT.md, and /app/reloc-canon/rules.yaml.

Required artifacts include: `/app/reloc-batches`, `/app/artifacts/relocation_consistency_report.json`, `/app/reloclogic/evaluate.go`, `/app/RELOCATION_SPEC.md`, `/app/REPORT_LAYOUT.md`, `/app/reloc-canon/rules.yaml`, `/app/relocbin/main.go`, `/app/bin/reloccheck`.

Author anonymous tagged this **hard** build-and-dependency-management task (packaging, dependency-management, maven-shade, jar-relocation, fat-jar, package-relocation, go).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `d2365ecd-5d1c-4f4d-af67-da77d7b3d062_submission_2026-07-20T15_12_53.045Z.zip` is a task submission, not a Harbor job. 8 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
