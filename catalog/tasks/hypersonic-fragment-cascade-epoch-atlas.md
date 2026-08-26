# # Hypersonic fragment cascade epoch atlas

Submission: `e55547a7-d339-42b6-9aff-6b6df8f29cc0`  
Slug: `hypersonic-fragment-cascade-epoch-atlas`  
Latest archive: `e55547a7-d339-42b6-9aff-6b6df8f29cc0_submission_2026-07-17T14_13_21.503Z.zip`  
Revisions in Dropbox: 7

## Task summary

Build a Kessler-style orbital debris cascade forecasting system on the working TypeScript simulation library at /app. The system must ingest debris body catalogs, propagate Keplerian orbits with atmospheric drag under solar-flare density modulation, detect sphere-sphere collisions, spawn momentum-and-energy-conserving fragment clouds, and export a cascade fragment atlas with a collision epoch ledger. All behavior, JSON field schemas, integrator constants, collision rules, drag model, hash conventions, and export contracts are defined in /app/docs/cli.md, /app/docs/staging-schema.md, /app/docs/kepler-integrator.md, /app/docs/collision-spawn.md, /app/docs/drag-flare.md, /app/docs/atlas-ledger-schema.md, /app/docs/export-sequence.md, and /app/docs/canonical-json-hash.md. Those documents govern every field name, array order, hash seal, and cross-artifact binding tested by the verifier. Key requirements: Read the catalog directory (default /app/catalogs/leo-alpha; honor CASCADE_CATALOG_DIR when set to an absolute path).; Load bodies from bodies.jsonl in feed order (line by line, preserving the sequence they appear in the file). Do not sort by id or any other field.; Honor the per-body cd field from the catalog; if absent default to 2.2.; Load flare events from flares.jsonl sorted by t_sec ascending..

Required artifacts include: `/app/docs/cli.md`, `/app/docs/staging-schema.md`, `/app/docs/kepler-integrator.md`, `/app/docs/collision-spawn.md`, `/app/docs/drag-flare.md`, `/app/docs/atlas-ledger-schema.md`, `/app/docs/export-sequence.md`, `/app/docs/canonical-json-hash.md`.

Author anonymous tagged this **hard** scientific-computing task (kessler-cascade, fragment-atlas, epoch-ledger, solar-flare-drag, kepler-integration, collision-spawn).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `e55547a7-d339-42b6-9aff-6b6df8f29cc0_submission_2026-07-17T14_13_21.503Z.zip` is a task submission, not a Harbor job. 7 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
