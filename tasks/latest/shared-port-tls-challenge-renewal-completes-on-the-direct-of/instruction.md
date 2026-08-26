Shared-port TLS challenge renewal completes on the direct office path while the proxied vantage still reports mismatched ALPN negotiation and certificate material for the same hostname. Authoritative DNS validation and HTTP-01 remain disabled by policy; only the remaining challenge type may be used.

Fix sources under `/app/environment` so `/app/bin/run_lab` regenerates `/app/output/lab_observations.json` through the normal Rust pathlab driver. Static or hand-written observation JSON will not pass. Table-driven rules and manifests under `/app/environment/data/` govern compile preimage, route-plan caching, lane simulation, remote epoch binding, ALPN selection, seal encoding, and journal commit. Output schema and artifact paths are in `/app/environment/docs/field_contract.md`.

The report exposes observation_digest, plan_hash, journal_generation, prior_digest, journal_chain_digest, and path_report rows with plan_index, alpn_code, material_fingerprint, local_sink_epoch, remote_sink_epoch, cohort_label, and rewrite_count. Run journal state and route plan cache under `/app/var/` persist across successive lab runs unless reset.

At steady state, bundled cohort rows must agree across compile preimage, cached plan_hash sealing, lane simulation, remote epoch binding, and journal commit. Truncated journal files must be reconciled before commit according to `wal_manifest.toml`.
