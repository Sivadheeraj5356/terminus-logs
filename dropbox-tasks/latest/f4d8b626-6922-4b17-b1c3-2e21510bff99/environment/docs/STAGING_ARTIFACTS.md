# Staging artifacts

ingest-dive-log writes staging JSON:
- expedition_id
- report_count
- observation_count
- reports (verbatim from bundle)
- observations (verbatim from bundle)
- staging_bind

staging_bind follows BIND_CRC.md staging_bind section.

Also mirrors to /app/state/{expedition_id}-dives.json
