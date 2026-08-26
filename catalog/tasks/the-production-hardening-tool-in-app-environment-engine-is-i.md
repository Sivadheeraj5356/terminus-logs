# The production hardening tool in `/app/environment/engine` is incomplete. Implem

Submission: `f3c99fb2-3111-4ea4-b3c6-01306ddfebf1`  
Slug: `the-production-hardening-tool-in-app-environment-engine-is-i`  
Latest archive: `f3c99fb2-3111-4ea4-b3c6-01306ddfebf1_submission_2026-07-18T15_42_22.229Z.zip`  
Revisions: 1

## Task summary

The production hardening tool in `/app/environment/engine` is incomplete. Implement the exported asynchronous function `hardenMediaInferenceDefaults(repoRoot, dossierPath, fixtureDir, outDir)` and keep `/app/environment/engine/cli/harden.js` working. For any dossier that follows the included decision-record format, resolve the unique currently ratified production policy, update both `/app/environment/engine/config/inference.js` and `/app/environment/engine/terraform/production.tfvars`, then evaluate every fixture listed by `/app/environment/fixtures/manifest.json` through the bundled local model. Repeated calls in the same process must use the newly supplied dossier and repository state. Repeating a successful call with the same inputs must not change the resulting files. If the dossier has no unique ratified production policy, fail without partially changing the repository or `outDir`. Do not modify `/app/environment/dossier/incident-dossier.md`, `/app/environment/fixtures/manifest.json`, fixture binaries, model files or `/app/environment/engine/terraform/variables.tf`. Write deterministic JSON under `outDir`: `deployment-policy.json` with `debugInferenceEnabled` as a boolean, `corsAllowedOrigins` as a string array in policy order, `maxUploadBytes` as an integer, `telemetryRedactionEnabled` as a boolean, `telemetryRedactedFields` as a string array in policy order and `moderationThresholds` as an object containing numeric `safe`, `suggestive` and `explicit` values; `terraform-defaults.json` with the corresponding snake_case Terraform keys; and `fixture-decisions.json`...

Required artifacts include: `/app/environment/engine`, `/app/environment/engine/cli/harden.js`, `/app/environment/engine/config/inference.js`, `/app/environment/engine/terraform/production.tfvars`, `/app/environment/fixtures/manifest.json`, `/app/environment/dossier/incident-dossier.md`, `/app/environment/engine/terraform/variables.tf`, `/app/out/deployment-policy.json`.

Author anonymous tagged this **hard** security task (terraform, tensorflow-js, configuration-precedence, incident-recovery, content-moderation, long-context).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `f3c99fb2-3111-4ea4-b3c6-01306ddfebf1_submission_2026-07-18T15_42_22.229Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
