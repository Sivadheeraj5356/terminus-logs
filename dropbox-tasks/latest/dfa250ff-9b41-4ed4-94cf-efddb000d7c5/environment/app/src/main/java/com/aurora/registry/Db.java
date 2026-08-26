package com.aurora.registry;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

/** JDBC wiring for the file-backed H2 registry. */
public final class Db {

    private Db() {
    }

    /**
     * Opens the registry held at {@code base} (a path with no {@code .mv.db} suffix, e.g.
     * {@code /app/data/registry}).
     */
    public static Connection open(String base) throws SQLException {
        String url = "jdbc:h2:file:" + base + ";DB_CLOSE_ON_EXIT=TRUE";
        return DriverManager.getConnection(url, "sa", "");
    }
}
