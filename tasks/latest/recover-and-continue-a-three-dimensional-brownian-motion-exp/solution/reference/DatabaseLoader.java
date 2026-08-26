package org.terminus.calc;

import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.Statement;
import static org.terminus.calc.Model.*;

final class DatabaseLoader {
    static void write(Path path, Recovered recovered, AnalysisData analysis) throws Exception {
        Class.forName("org.duckdb.DuckDBDriver");
        try (Connection connection = DriverManager.getConnection("jdbc:duckdb:" + path.toAbsolutePath())) {
            connection.setAutoCommit(false);
            try (Statement statement = connection.createStatement()) {
                statement.execute("CREATE TABLE source_shards(shard_id VARCHAR, generation BIGINT, records BIGINT, shard_sha256 VARCHAR)");
                statement.execute("CREATE TABLE recovered_records(tick BIGINT, particle_id VARCHAR, x DOUBLE, y DOUBLE, z DOUBLE, generation BIGINT, shard_id VARCHAR)");
                statement.execute("CREATE TABLE trajectory_points(segment_id BIGINT, tick BIGINT, particle_id VARCHAR, x DOUBLE, y DOUBLE, z DOUBLE, ux DOUBLE, uy DOUBLE, uz DOUBLE, drift_x DOUBLE, drift_y DOUBLE, drift_z DOUBLE)");
                statement.execute("CREATE TABLE rejected_timesteps(tick BIGINT, reason VARCHAR)");
                statement.execute("CREATE TABLE msd_by_lag(lag BIGINT, time DOUBLE, pairs BIGINT, msd_x DOUBLE, msd_y DOUBLE, msd_z DOUBLE, msd_total DOUBLE)");
                statement.execute("CREATE TABLE analysis_manifest(schema VARCHAR, source_sha256 VARCHAR, state_sha256 VARCHAR, dataset_sha256 VARCHAR, complete_timesteps BIGINT, rejected_timesteps BIGINT)");
            }
            try (PreparedStatement statement = connection.prepareStatement("INSERT INTO source_shards VALUES(?,?,?,?)")) {
                for (Shard shard : recovered.state.shards) {
                    statement.setString(1, shard.id);
                    statement.setLong(2, shard.generation);
                    statement.setLong(3, shard.records.size());
                    statement.setString(4, shard.sha256);
                    statement.addBatch();
                }
                statement.executeBatch();
            }
            try (PreparedStatement statement = connection.prepareStatement("INSERT INTO recovered_records VALUES(?,?,?,?,?,?,?)")) {
                for (Row row : recovered.selected) {
                    statement.setLong(1, row.tick);
                    statement.setString(2, row.particle);
                    statement.setDouble(3, row.x);
                    statement.setDouble(4, row.y);
                    statement.setDouble(5, row.z);
                    statement.setLong(6, row.generation);
                    statement.setString(7, row.shard);
                    statement.addBatch();
                }
                statement.executeBatch();
            }
            try (PreparedStatement statement = connection.prepareStatement("INSERT INTO trajectory_points VALUES(?,?,?,?,?,?,?,?,?,?,?,?)")) {
                for (Point point : analysis.points) {
                    statement.setLong(1, point.segment);
                    statement.setLong(2, point.tick);
                    statement.setString(3, point.particle);
                    statement.setDouble(4, point.x);
                    statement.setDouble(5, point.y);
                    statement.setDouble(6, point.z);
                    statement.setDouble(7, point.ux);
                    statement.setDouble(8, point.uy);
                    statement.setDouble(9, point.uz);
                    statement.setDouble(10, point.driftX);
                    statement.setDouble(11, point.driftY);
                    statement.setDouble(12, point.driftZ);
                    statement.addBatch();
                }
                statement.executeBatch();
            }
            try (PreparedStatement statement = connection.prepareStatement("INSERT INTO rejected_timesteps VALUES(?,?)")) {
                for (Reject reject : recovered.rejected) {
                    statement.setLong(1, reject.tick);
                    statement.setString(2, reject.reason);
                    statement.addBatch();
                }
                statement.executeBatch();
            }
            try (PreparedStatement statement = connection.prepareStatement("INSERT INTO msd_by_lag VALUES(?,?,?,?,?,?,?)")) {
                for (Msd row : analysis.msd) {
                    statement.setLong(1, row.lag);
                    statement.setDouble(2, row.time);
                    statement.setLong(3, row.pairs);
                    statement.setDouble(4, row.x);
                    statement.setDouble(5, row.y);
                    statement.setDouble(6, row.z);
                    statement.setDouble(7, row.total);
                    statement.addBatch();
                }
                statement.executeBatch();
            }
            try (PreparedStatement statement = connection.prepareStatement("INSERT INTO analysis_manifest VALUES(?,?,?,?,?,?)")) {
                statement.setString(1, REPORT_SCHEMA);
                statement.setString(2, recovered.state.sourceHash);
                statement.setString(3, recovered.state.stateHash);
                statement.setString(4, analysis.datasetHash);
                statement.setLong(5, recovered.complete.size());
                statement.setLong(6, recovered.rejected.size());
                statement.executeUpdate();
            }
            connection.commit();
        }
    }

    private DatabaseLoader() {}
}
