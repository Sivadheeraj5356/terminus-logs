package com.aurora.registry;

import java.sql.Connection;

/**
 * A single, versioned change to the registry schema or its contents.
 *
 * <p>Implementations may be plain SQL scripts ({@link SqlMigration}) or Java code, which is how
 * migrations that have to reach outside the database — parsing an archive, calling a service —
 * are written. The runner treats both identically: it applies them in ascending version order and
 * records each one in the {@code schema_version} ledger.
 */
public interface Migration {

    /** Ascending version number. Must be unique across all registered migrations. */
    int version();

    /** Identifier recorded in the {@code schema_version} ledger, e.g. {@code V3__seed_feature_catalog.sql}. */
    String script();

    /**
     * Applies the migration. The runner supplies a connection with auto-commit disabled and commits
     * once the migration returns; throwing rolls the whole migration back.
     */
    void apply(Connection connection) throws Exception;
}
