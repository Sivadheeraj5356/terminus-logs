# Path lab field contract

Report path: `/app/output/lab_observations.json`

Top-level fields:
- observation_digest — digest over the sealed observation body
- plan_hash — fingerprint of the compiled route plan
- journal_generation — integer run counter
- prior_digest — previous run observation_digest; empty on first run
- journal_chain_digest — digest binding generation, prior_digest, observation_digest, plan_hash, and lane stamps
- path_report — array of row objects in compiled plan order

Each path_report row includes: host_id, lane_id, cohort_label, plan_index, alpn_code, material_fingerprint, local_sink_epoch, remote_sink_epoch, rewrite_count.

Bundled tables under `data/`:
- layout_t9.toml — probe layout rows
- cohort_policy.toml — policy meta and per-row compile fields
- arm_dispatch.toml — dispatch identifiers to material arms
- plan_manifest.toml — plan_hash field list and bind_sequence
- seal_manifest.toml — observation seal body_layout and prefix_fields
- alpn_rules.toml — ALPN selection rules for remote vantage material
- alpn_codes.toml — numeric ALPN identifiers for path_report rows
- epoch_map.toml — local and remote sink epoch slot values
- wal_manifest.toml — journal scrape, recovery, reconcile, and journal_chain binding
- strip_rules.toml — proxy strip lane semantics
- epoch_bind.toml — remote sink epoch binding rules
- mux_layout.toml — shared port context records
- lane_layout.toml — direct vs proxy simulation kinds
- pem_w8/ — primary, secondary, tertiary PEM fixtures (immutable)

Run artifacts under `/app/var/`:
- route_plan.json — plan_hash and compile_generation written before execution
- run_journal.json — generation, digests, plan_hash, lane_stamps, recovered flag

Requirements:
- Observations must be produced by the Rust pipeline; hand-written JSON will not pass.
- PEM fixtures under `pem_w8/` must not be modified.
- Bundled data tables and manifests define behavior; do not edit table rows to satisfy outputs.
- Truncated journal files must be reconciled before commit according to `wal_manifest.toml`.
- ALPN selection follows `alpn_rules.toml`: rewritten remote material that retains the challenge marker keeps the challenge ALPN code; rewritten material without the marker uses the stripped code.
- Observation sealing follows `seal_manifest.toml`: rows are in compiled plan order and `compact_json_array` means compact JSON objects with sorted keys and no whitespace, comma-joined inside the configured body layout.

The verifier resets `/app/var/` and `/app/output/` before grading; each pytest case starts from an empty journal and route plan cache unless the test itself performs multiple runs.
