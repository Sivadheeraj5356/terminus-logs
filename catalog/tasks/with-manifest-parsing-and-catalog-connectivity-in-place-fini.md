# With manifest parsing and catalog connectivity in place, finish the lock pipelin

Submission: `7ec1ef7a-7aa1-4b24-bb20-65a14b190356`  
Slug: `with-manifest-parsing-and-catalog-connectivity-in-place-fini`  
Latest archive: `7ec1ef7a-7aa1-4b24-bb20-65a14b190356_submission_2026-07-04T15_56_24.382Z.zip`  
Revisions: 1

## Task summary

With manifest parsing and catalog connectivity in place, finish the lock pipeline. Join the approval and platform constraint tables, resolve versions from the catalog, and emit a deterministic lock file that passes schema validation. Requirements: - Implement `HelixPipeline.Catalog.Queries.fetch_enriched/4` to join `dependency_approvals` with `platform_constraints` for the requested package names and platform (`os`, `arch`). Omit packages with no approval row. Return a map keyed by package name, not a flat list: `%{"phoenix" => %{"approval" => %{"package_name" => ..., "approved_version" => ..., "approval_status" => ...}, "constraints" => [%{"os" => ..., "arch" => ..., "min_version" => ..., "max_version" => ...}, ...]}}`. `HelixPipeline.Catalog.fetch_enriched!/3` is provided and delegates to your `/4` implementation. - Implement `HelixPipeline.Lock.Builder.build/2` to render TOML lock contents. Manifest dependency maps use `"name"` and `"pin"` keys. Sort dependencies alphabetically by name. When `approval_status` is `"approved"`, use the catalog `approved_version` and set `source` to `"catalog"`; for `"pending"` or `"rejected"`, keep the manifest pin and set `source` to `"pin"`. - `Builder.build/2` must only render dependencies present in the catalog result; manifest dependencies with no catalog entry must be silently dropped. - Render dependency table keys as bare TOML identifiers (e.g. `[dependencies.phoenix]`, `[[dependencies.ecto_sql.constraints]]`). Interpolate package names directly — do not JSON-encode or quote key segments. - Include platform constraints under...

Required artifacts include: `/app/build/helix.lock.toml`, `/app/priv/schemas/lock.schema.json`.

Author anonymous tagged this **medium** build-and-dependency-management task (elixir, mysql, yaml, toml, mix, build-pipeline).

Time estimates: expert ~90 min, junior ~180 min.

Harbor timeouts: agent Nones, verifier Nones.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `7ec1ef7a-7aa1-4b24-bb20-65a14b190356_submission_2026-07-04T15_56_24.382Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
