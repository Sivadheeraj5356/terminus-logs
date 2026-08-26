# Aurora Claims Risk — model registry

The registry that records model runs, the features they were scored on, and the promotion
decision each run received. It is an H2 database on disk plus a small migration runner.

## Layout

    pom.xml                                  Maven build (H2 + Jackson, both offline in the image)
    registry                                 build-and-run wrapper for the CLI
    data/registry.mv.db                      the registry database, seeded through V6
    out/                                     generated artefacts
    src/main/java/com/aurora/registry/       runner, JDBC wiring, CLI
    src/main/resources/db/migration/         V1..V6 SQL scripts
    archive/fa_2027q1/                       the sealed 2027Q1 feature-audit bundle
    docs/model_review_dossier.md             the 2027Q1 review dossier

## Running it

    /app/registry status  --db /app/data/registry
    /app/registry migrate --db /app/data/registry
    /app/registry export  --db /app/data/registry --out /app/out/promotion_audit.csv

The wrapper compiles the project (offline, against the pre-populated Maven repository) and then
runs `com.aurora.registry.Main`, so there is no separate build step to remember.

## Migrations

`Migrations.all()` is the registered set, applied in ascending version order and recorded in the
`schema_version` ledger. Anything already in the ledger is skipped, so the runner is safe to
re-run. A migration is either a SQL script on the classpath (`SqlMigration`) or an implementation
of `Migration` — the latter is how migrations that have to read something outside the database
are written.

## The bundle

`archive/fa_2027q1/` is delivered by the Polars feature-audit pipeline and sealed. `manifest.json`
is its index; the observation members are CSV, the pre-migration extract is TSV, and the run
lifecycle is JSONL. The rules governing how it is read, scoped, and turned into a promotion
decision are in the review dossier, not in this README.
