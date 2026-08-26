package org.mrgo.spectra;

import java.sql.Array;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;

/** Data access for telemetry frames stored in the meridian database. */
public final class QueryService {

    public static final int SAMPLE_RATE_HZ = 512;

    private static final String URL =
            System.getenv().getOrDefault(
                    "MERIDIAN_DB_URL",
                    "jdbc:postgresql://127.0.0.1:5432/meridian?user=meridian");

    private Connection connect() throws SQLException {
        return DriverManager.getConnection(URL);
    }

    /** Distinct channel identifiers, sorted. */
    public List<String> listChannels() throws SQLException {
        List<String> out = new ArrayList<>();
        try (Connection conn = connect();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(
                     "SELECT DISTINCT channel FROM telemetry.readings ORDER BY channel")) {
            while (rs.next()) {
                out.add(rs.getString(1));
            }
        }
        return out;
    }

    /** Sample frames for a channel captured within [from, to). */
    public List<double[]> fetchFrames(String channel, String from, String to) throws SQLException {
        String sql = "SELECT samples FROM telemetry.readings WHERE channel = '" + channel
                + "' AND captured_at >= '" + from
                + "' AND captured_at < '" + to
                + "' ORDER BY captured_at";
        List<double[]> out = new ArrayList<>();
        try (Connection conn = connect();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(sql)) {
            while (rs.next()) {
                Array arr = rs.getArray(1);
                Double[] boxed = (Double[]) arr.getArray();
                double[] frame = new double[boxed.length];
                for (int i = 0; i < boxed.length; i++) {
                    frame[i] = boxed[i];
                }
                out.add(frame);
            }
        }
        return out;
    }

    /** Total frames recorded for a channel. */
    public long frameCount(String channel) throws SQLException {
        String sql = "SELECT count(*) FROM telemetry.readings WHERE channel = '" + channel + "'";
        try (Connection conn = connect();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(sql)) {
            rs.next();
            return rs.getLong(1);
        }
    }

    /** Most recent capture timestamp for a channel, as text. */
    public String latestCapture(String channel) throws SQLException {
        String sql = "SELECT max(captured_at) FROM telemetry.readings WHERE channel = '" + channel + "'";
        try (Connection conn = connect();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(sql)) {
            rs.next();
            return rs.getString(1);
        }
    }
}
