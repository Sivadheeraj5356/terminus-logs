A sccache release guard must close a reproducible build attestation from dependency lock pins, define-order lockfile traces, and compiler-wrapper SBOM hash segments before publish clears.

Produce `/app/output/kq_report.json` through `/app/environment/tools/kq_run`. The lockfile reload rules, supply-chain pin blend, release-guard witness, and reproducibility digest are specified in `/app/environment/docs/kq_contract.md`, `/app/environment/docs/kq_notes.md`, and `/app/environment/docs/build-cache-sbom-lockfile.md`.

The build-cache pipeline materializes `/app/output/kq_frames.ndjson` from the deck, then exports the SBOM-style attestation. Offline rebuilds on the same dependency deck must yield an identical `cache_digest`.

Release clearance depends on coupled ingest and export lanes: dependency-tier scope resolution, argv and wrapper authority reconciliation, define-order pin traces, optional denylist width gates, and auth-lane closure recorded during frame ingest.

Intermediate artifacts include the frame stream, auth-lane seal, staging ledger, and final report. Export must consume the auth lane and respect staging-only control rows that shift the reproducibility digest without appearing in report rows.

Verifier scenarios exercise reload precedence, define-order pin variants, pin-mismatch release gates, native compiler witness bands, denylist width behavior, and non-nominal argv status suppression.

All behavioral contracts live in the cited `/app/environment/docs/` files.
