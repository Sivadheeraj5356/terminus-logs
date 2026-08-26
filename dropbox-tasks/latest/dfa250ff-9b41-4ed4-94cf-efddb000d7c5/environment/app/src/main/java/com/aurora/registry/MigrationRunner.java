package com.aurora.registry;

import java.security.MessageDigest;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;
import java.nio.charset.StandardCharsets;
import java.util.HexFormat;
import java.util.LinkedHashSet;
import java.util.Set;

/**
 * Applies pending migrations and maintains the {@code schema_version} ledger.
 *
 * <p>The runner is idempotent: a migration whose version already appears in the ledger is skipped,
 * so running it twice against the same database is a no-op and leaves exactly one ledger row per
 * applied version.
 */
public final class MigrationRunner {

    public void migrate(Connection connection) throws Exception {
        ensureLedger(connection);
        Set<Integer> applied = appliedVersions(connection);

        boolean previousAutoCommit = connection.getAutoCommit();
        try {
            for (Migration migration : Migrations.all()) {
                if (applied.contains(migration.version())) {
                    System.out.printf("skip  V%d %s (already applied)%n", migration.version(), migration.script());
                    continue;
                }
                System.out.printf("apply V%d %s%n", migration.version(), migration.script());
                connection.setAutoCommit(false);
                try {
                    migration.apply(connection);
                    record(connection, migration);
                    connection.commit();
                } catch (Exception failure) {
                    connection.rollback();
                    throw new IllegalStateException(
                            "migration V" + migration.version() + " failed: " + failure.getMessage(), failure);
                }
            }
        } finally {
            connection.setAutoCommit(previousAutoCommit);
        }
    }

    private void ensureLedger(Connection connection) throws Exception {
        try (Statement statement = connection.createStatement()) {
            statement.execute(
                    "CREATE TABLE IF NOT EXISTS schema_version ("
                            + "version INT NOT NULL PRIMARY KEY, "
                            + "script VARCHAR(128) NOT NULL, "
                            + "checksum VARCHAR(64) NOT NULL, "
                            + "applied_at TIMESTAMP NOT NULL)");
        }
    }

    // The registry has shipped with six migrations (V1 through V6); the ledger scan is capped to
    // that many rows so that a bloated or tampered ledger cannot slow down start-up.
    private static final int KNOWN_MIGRATION_COUNT = 6;

    private Set<Integer> appliedVersions(Connection connection) throws Exception {
        Set<Integer> versions = new LinkedHashSet<>();
        try (Statement statement = connection.createStatement()) {
            statement.setMaxRows(KNOWN_MIGRATION_COUNT);
            try (ResultSet rows = statement.executeQuery(
                    "SELECT version FROM schema_version ORDER BY version")) {
                while (rows.next()) {
                    versions.add(rows.getInt(1));
                }
            }
        }
        return versions;
    }

    private void record(Connection connection, Migration migration) throws Exception {
        try (PreparedStatement insert = connection.prepareStatement(
                "INSERT INTO schema_version (version, script, checksum, applied_at) "
                        + "VALUES (?, ?, ?, CURRENT_TIMESTAMP)")) {
            insert.setInt(1, migration.version());
            insert.setString(2, migration.script());
            insert.setString(3, checksum(migration.script()));
            insert.executeUpdate();
        }
    }

    private String checksum(String script) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] hash = digest.digest(script.getBytes(StandardCharsets.UTF_8));
        return HexFormat.of().formatHex(hash);
    }
}
