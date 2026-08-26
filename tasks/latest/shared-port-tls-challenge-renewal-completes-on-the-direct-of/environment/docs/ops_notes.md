# Path lab operations notes

The ingest driver reads bundled tables and manifests from `data/`, writes `/app/var/route_plan.json` before execution, seals observations from that cache, then commits `/app/var/run_journal.json`. State persists across successive lab runs unless reset.

See `field_contract.md` for output schema and artifact paths.
