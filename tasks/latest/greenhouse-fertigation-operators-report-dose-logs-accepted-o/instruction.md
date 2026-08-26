Greenhouse fertigation operators report dose logs accepted out of file order, EC drift checks that ignore the lead-in window after batch open, compliance exports missing or wrong integrity hashes, and daily volume totals that drift when batches replay on the same SQLite file.

Repair and recompile the Go fert-ingest and fert-export binaries from /app using /app/scripts/build.sh with CGO_ENABLED and go.mod dependencies. Behavior must match /app/docs/event-format.md, /app/docs/fertigation-rules.md, /app/docs/db-schema.md, /app/docs/audit-report-schema.md, /app/docs/cli-contract.md, and /app/config/greenhouse-profile.json. Write compliance export to /app/output/fertigation-compliance.json.

Verifier cases use isolated or shared databases and derive zone ids from VERIFY_RUN_ID when set.
