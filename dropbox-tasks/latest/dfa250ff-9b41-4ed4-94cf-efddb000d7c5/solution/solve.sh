#!/bin/bash
# Oracle solution: implement the V7 bundle-load migration and the canonical export,
# then apply the migration and produce the export.
set -euo pipefail

# Resolve the toolchain explicitly: the oracle must run from any shell, including one that
# rebuilt PATH from /etc/profile and dropped the image's environment.
export JAVA_HOME="${JAVA_HOME:-/opt/java/openjdk}"
export PATH="${JAVA_HOME}/bin:/opt/venv/bin:${PATH}"
export MAVEN_OPTS="${MAVEN_OPTS:--Dmaven.repo.local=/root/.m2/repository}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC=/app/src/main/java/com/aurora/registry

for f in V7LoadFeatureAudit.java Migrations.java ExportCommand.java MigrationRunner.java; do
    if [ ! -f "$SCRIPT_DIR/$f" ]; then
        echo "oracle asset missing: $SCRIPT_DIR/$f" >&2
        exit 1
    fi
done

# 1. The V7 migration: reads the sealed bundle, applies the dossier's scoping and threshold
#    rules, and loads feature_audit + promotion_audit through JDBC.
cp "$SCRIPT_DIR/V7LoadFeatureAudit.java" "$SRC/V7LoadFeatureAudit.java"

# 2. Register V7 with the runner so it is picked up as a pending migration.
cp "$SCRIPT_DIR/Migrations.java" "$SRC/Migrations.java"

# 3. The canonical export (Appendix D of the review dossier).
cp "$SCRIPT_DIR/ExportCommand.java" "$SRC/ExportCommand.java"

# 4. Fix the migration runner: its ledger scan was capped at six rows, so once V7 is recorded the
#    runner no longer sees it as applied and re-applies it on every subsequent run. Remove the cap
#    so the runner is genuinely idempotent.
cp "$SCRIPT_DIR/MigrationRunner.java" "$SRC/MigrationRunner.java"

# 5. Apply the migration and write the export.
/app/registry migrate --db /app/data/registry
/app/registry export --db /app/data/registry --out /app/out/promotion_audit.csv

echo "--- schema_version ---"
/app/registry status --db /app/data/registry
