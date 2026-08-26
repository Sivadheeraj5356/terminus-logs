The chamber escape desk under /app/environment is a terminal puzzle simulation: a Rust pathfinding planner, a local topology HTTP service, graph fixtures under vault, and a public route-manifest contract.

Operators at the escape desk run bash /app/environment/scripts/run_escape.sh to rebuild desk_k, start the hidden-port topology service, recover live chamber evidence, compute an egress walk through the vault graph, and write /app/output/route_manifest.json.

The entrypoint compiles the Rust crate, stops any prior listener, launches the chamberd-backed HTTP service on an ephemeral TCP port that is not published in static config, then runs desk_k with runner.toml to assemble the manifest from live listener and topology data.

Stage ordering and listener lifecycle rules are documented in /app/docs/escape_pipeline.md.

Field definitions, checksum formulas, and api_evidence requirements live in /app/docs/manifest_contract.md and /app/docs/api_notes.md.

Success means the output validates against /app/environment/schemas/route_manifest.schema.json and every rule in those contract documents.

Today's broken run still exits zero but the manifest fails contract checks.

Observed symptoms include a wrong schema_tag, room sequences that do not follow legal edges from start to exit, move tokens that disagree with the graph, checksum fields that do not recompute from the manifest body, and api_evidence that does not describe the listener and graph file the live service actually holds open.

Static or hand-written output files are insufficient because the verifier deletes the manifest and reruns the pipeline.

The modules under /app/environment must assemble a contract-valid manifest with valid rooms, moves, and api_evidence whenever the escape entrypoint runs.
