# The Iris gateway cutover needs the Composer package at /workspace/iris-provenanc

Submission: `5b1a670c-a989-4f9d-ae60-eeff3a2a466f`  
Slug: `the-iris-gateway-cutover-needs-the-composer-package-at-works`  
Latest archive: `5b1a670c-a989-4f9d-ae60-eeff3a2a466f_submission_2026-07-17T02_25_37.560Z.zip`  
Revisions in Dropbox: 6

## Task summary

The Iris gateway cutover needs the Composer package at /workspace/iris-provenance to resolve Go module conflict policy for require vs replace, retract, excludes, and scaffolding flags. The package already contains a draft walker and digest exporter — repair them so Composer/Phinx can publish a build-ready module graph, land it into the dependency database named by the active paths file, and pin a checksummed lock digest the release gate can verify. Path bindings live in /workspace/config/paths.json. Use proxy_export and cutover_register from that file (other path keys are historical or smoke mirrors). Start from /workspace/docs/handover-index.md for the cutover memo and register legend.

Required artifacts include: `/output/normalized-graph.json`.

Author bhavy tagged this **hard** build-and-dependency-management task (composer, phinx, go-modules, replace-directive, retract).

Time estimates: expert ~150 min, junior ~300 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `5b1a670c-a989-4f9d-ae60-eeff3a2a466f_submission_2026-07-17T02_25_37.560Z.zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
