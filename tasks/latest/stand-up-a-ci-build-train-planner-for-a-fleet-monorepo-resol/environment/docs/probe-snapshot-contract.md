# Probe snapshot contract

Before writing /app/output/fleet-build-compliance.json, the build-train driver must materialize a probe snapshot at FLEET_STAGE_ROOT/build-train-probe.json (default FLEET_STAGE_ROOT=/app/var/fleet-stage). FLEET_STAGE_ROOT may be overridden by the environment for alternate staging roots.

Snapshot top-level keys (alphabetical): api_base, plan_digest, plan_seal, probes, release_pin, version.

- version is integer 1
- api_base is the probed base URL string
- release_pin is the pin value read from /app/fixtures/fleet-release.pin (or FLEET_PIN_PATH when set)
- plan_digest and plan_seal come from a live POST /v1/build-attest probe after policy rewrite
- probes is an object with boolean keys: build_attest_valid, build_plan_valid, debug_endpoint_blocked, openapi_valid, release_pin_valid (alphabetical)

release_pin_valid is true when the pin file yields a non-empty trimmed pin string.

The compliance export must be derived from the on-disk probe snapshot (read it after write). Compact JSON, sorted keys, no trailing newline.

After a successful export, append one compact JSON line to FLEET_STAGE_ROOT/run-journal.jsonl with keys (alphabetical): run_index, seal_root. seal_root equals the staged plan_seal. run_index starts at 1 and increments by one per successful driver run.

Across two successful driver runs with unchanged fixtures and secure policy already applied, snapshot bytes must be identical aside from journal growth.
