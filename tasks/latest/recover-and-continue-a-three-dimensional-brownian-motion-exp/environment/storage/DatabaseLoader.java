package org.terminus.calc;

import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.Statement;
import static org.terminus.calc.Model.*;

final class DatabaseLoader {
    static void write(Path path, Recovered recovered, AnalysisData analysis) throws Exception {
        Class.forName("org.duckdb.DuckDBDriver");
        try (Connection connection = DriverManager.getConnection("jdbc:duckdb:" + path.toAbsolutePath());
             Statement statement = connection.createStatement()) {
            statement.execute("CREATE TABLE source_shards(shard_id VARCHAR, generation BIGINT, records BIGINT, shard_sha256 VARCHAR)");
            statement.execute("CREATE TABLE recovered_records(tick BIGINT, particle_id VARCHAR, x DOUBLE, y DOUBLE, z DOUBLE, generation BIGINT, shard_id VARCHAR)");
            statement.execute("CREATE TABLE trajectory_points(segment_id BIGINT, tick BIGINT, particle_id VARCHAR, x DOUBLE, y DOUBLE, z DOUBLE, ux DOUBLE, uy DOUBLE, uz DOUBLE, drift_x DOUBLE, drift_y DOUBLE, drift_z DOUBLE)");
            statement.execute("CREATE TABLE rejected_timesteps(tick BIGINT, reason VARCHAR)");
            statement.execute("CREATE TABLE msd_by_lag(lag BIGINT, time DOUBLE, pairs BIGINT, msd_x DOUBLE, msd_y DOUBLE, msd_z DOUBLE, msd_total DOUBLE)");
            statement.execute("CREATE TABLE analysis_manifest(schema VARCHAR, source_sha256 VARCHAR, state_sha256 VARCHAR, dataset_sha256 VARCHAR, complete_timesteps BIGINT, rejected_timesteps BIGINT)");
        }
    }

    private DatabaseLoader() {}
}
