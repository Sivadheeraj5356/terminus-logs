package com.aurora.registry;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;

/**
 * Writes the canonical promotion audit export.
 *
 * <p>The export is the artefact the review board signs off: it is reproduced independently and
 * compared byte for byte, so its layout, ordering, and numeric rendering are fixed by contract
 * rather than left to the writer. The contract lives in the 2027Q1 review dossier (Appendix D).
 */
public final class ExportCommand {

    private static final String HEADER =
            "run_id,model_name,model_version,cohorts_evaluated,rows_considered,"
                    + "drifted_features,underpowered_rows,unscored_rows,max_psi,null_rate_p95,decision";

    /** Renders {@code promotion_audit} to {@code destination} in canonical form. */
    public void run(Connection connection, Path destination) throws Exception {
        StringBuilder body = new StringBuilder();
        body.append(HEADER).append('\n');

        // Appendix D: the most severe determination first, using the rank the registry itself
        // records, and run_id ascending within a determination.
        String query =
                "SELECT a.run_id, a.model_name, a.model_version, a.cohorts_evaluated, "
                        + "a.rows_considered, a.drifted_features, a.underpowered_rows, "
                        + "a.unscored_rows, a.max_psi, a.null_rate_p95, a.decision "
                        + "FROM promotion_audit a "
                        + "JOIN promotion_decision d ON d.decision = a.decision "
                        + "ORDER BY d.rank_order DESC, a.run_id ASC";

        try (Statement statement = connection.createStatement();
                ResultSet rows = statement.executeQuery(query)) {
            while (rows.next()) {
                body.append(rows.getString("run_id")).append(',')
                        .append(rows.getString("model_name")).append(',')
                        .append(rows.getString("model_version")).append(',')
                        .append(rows.getInt("cohorts_evaluated")).append(',')
                        .append(rows.getInt("rows_considered")).append(',')
                        .append(rows.getInt("drifted_features")).append(',')
                        .append(rows.getInt("underpowered_rows")).append(',')
                        .append(rows.getInt("unscored_rows")).append(',')
                        .append(fixed(rows.getDouble("max_psi"), 4)).append(',')
                        .append(fixed(rows.getDouble("null_rate_p95"), 6)).append(',')
                        .append(rows.getString("decision")).append('\n');
            }
        }

        // UTF-8, LF line endings, single trailing newline, no BOM.
        Files.writeString(destination, body.toString(), StandardCharsets.UTF_8);
    }

    /** Exactly {@code scale} digits after the decimal point, rounded half up. */
    private String fixed(double value, int scale) {
        return BigDecimal.valueOf(value).setScale(scale, RoundingMode.HALF_UP).toPlainString();
    }
}
