package com.aurora.registry;

import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import org.h2.tools.RunScript;

/** A migration backed by a SQL script on the classpath under {@code db/migration}. */
public final class SqlMigration implements Migration {

    private final int version;
    private final String script;

    public SqlMigration(int version, String script) {
        this.version = version;
        this.script = script;
    }

    @Override
    public int version() {
        return version;
    }

    @Override
    public String script() {
        return script;
    }

    @Override
    public void apply(Connection connection) throws Exception {
        String resource = "db/migration/" + script;
        try (InputStream in = getClass().getClassLoader().getResourceAsStream(resource)) {
            if (in == null) {
                throw new IllegalStateException("migration script not found on classpath: " + resource);
            }
            try (Reader reader = new InputStreamReader(in, StandardCharsets.UTF_8)) {
                RunScript.execute(connection, reader);
            }
        }
    }
}
