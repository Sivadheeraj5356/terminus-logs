package com.aurora.registry;

import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;

/**
 * Command line entry point for the registry.
 *
 * <pre>
 *   registry migrate --db /app/data/registry
 *   registry export  --db /app/data/registry --out /app/out/promotion_audit.csv
 *   registry status  --db /app/data/registry
 * </pre>
 */
public final class Main {

    public static void main(String[] args) throws Exception {
        if (args.length == 0) {
            usage();
            System.exit(2);
        }

        String command = args[0];
        String db = option(args, "--db", "/app/data/registry");
        String out = option(args, "--out", null);

        switch (command) {
            case "migrate" -> {
                try (Connection connection = Db.open(db)) {
                    new MigrationRunner().migrate(connection);
                }
                System.out.println("migrate: done");
            }
            case "export" -> {
                if (out == null) {
                    System.err.println("export requires --out <file>");
                    System.exit(2);
                }
                Path destination = Path.of(out);
                if (destination.getParent() != null) {
                    Files.createDirectories(destination.getParent());
                }
                try (Connection connection = Db.open(db)) {
                    new ExportCommand().run(connection, destination);
                }
                System.out.println("export: wrote " + out);
            }
            case "status" -> {
                try (Connection connection = Db.open(db);
                        Statement statement = connection.createStatement();
                        ResultSet rows = statement.executeQuery(
                                "SELECT version, script, applied_at FROM schema_version ORDER BY version")) {
                    System.out.println("version | script | applied_at");
                    while (rows.next()) {
                        System.out.printf("%7d | %s | %s%n", rows.getInt(1), rows.getString(2), rows.getString(3));
                    }
                }
            }
            default -> {
                usage();
                System.exit(2);
            }
        }
    }

    private static String option(String[] args, String name, String fallback) {
        for (int i = 0; i < args.length - 1; i++) {
            if (args[i].equals(name)) {
                return args[i + 1];
            }
        }
        return fallback;
    }

    private static void usage() {
        System.err.println("usage: registry <migrate|export|status> [--db <base>] [--out <file>]");
    }
}
