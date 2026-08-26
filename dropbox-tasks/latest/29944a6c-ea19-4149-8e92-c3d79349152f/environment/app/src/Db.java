package gate;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.sql.Timestamp;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Read-only H2 connection helpers. A fresh connection is opened per request
 * (see the API contract document); the caller is responsible for using
 * try-with-resources so the connection is closed before the response returns.
 */
public final class Db implements AutoCloseable {

    static {
        try {
            Class.forName("org.h2.Driver");
        } catch (ClassNotFoundException e) {
            throw new ExceptionInInitializerError(e);
        }
    }

    private final Connection conn;

    private Db(Connection c) { this.conn = c; }

    public static Db open(String url) throws Exception {
        Connection c = DriverManager.getConnection(url, "sa", "");
        return new Db(c);
    }

    public Data readAll() throws Exception {
        List<ApprovedKey> keys = new ArrayList<>();
        List<ExceptionWindow> windows = new ArrayList<>();
        Set<String> infra = new HashSet<>();
        try (Statement st = conn.createStatement()) {
            try (ResultSet rs = st.executeQuery(
                "SELECT fingerprint, owner, status, approved_at, revoked_at "
                    + "FROM approved_keys")) {
                while (rs.next()) {
                    keys.add(new ApprovedKey(
                        rs.getString(1),
                        rs.getString(2),
                        rs.getString(3),
                        toInstant(rs.getTimestamp(4)),
                        toInstant(rs.getTimestamp(5))));
                }
            }
            try (ResultSet rs = st.executeQuery(
                "SELECT id, clause_id, service_glob, starts_at, ends_at, approved_at "
                    + "FROM exception_windows")) {
                while (rs.next()) {
                    windows.add(new ExceptionWindow(
                        rs.getInt(1),
                        rs.getString(2),
                        rs.getString(3),
                        toInstant(rs.getTimestamp(4)),
                        toInstant(rs.getTimestamp(5)),
                        toInstant(rs.getTimestamp(6))));
                }
            }
            try (ResultSet rs = st.executeQuery(
                "SELECT service_name FROM infra_registry")) {
                while (rs.next()) infra.add(rs.getString(1));
            }
        }
        return new Data(keys, windows, infra);
    }

    @Override
    public void close() throws Exception {
        conn.close();
    }

    private static Instant toInstant(Timestamp t) {
        if (t == null) return null;
        // TIMESTAMP columns in the seed are UTC wall-clock; H2 stores them
        // as naive local times, so read them as UTC on the way out.
        return t.toLocalDateTime().toInstant(ZoneOffset.UTC);
    }

    public record ApprovedKey(String fingerprint, String owner, String status,
                              Instant approvedAt, Instant revokedAt) { }

    public record ExceptionWindow(int id, String clauseId, String serviceGlob,
                                   Instant startsAt, Instant endsAt,
                                   Instant approvedAt) { }

    public record Data(List<ApprovedKey> keys, List<ExceptionWindow> windows,
                        Set<String> infra) { }
}
