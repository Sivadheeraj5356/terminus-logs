package com.aurora.registry;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.BufferedReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;
import java.sql.Types;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

/**
 * V7 — ingest the sealed 2027Q1 feature-audit bundle and derive the promotion audit.
 *
 * <p>Scoping, supersession, threshold, and determination rules follow the 2027Q1 review dossier
 * (Part I, with the authoritative amendment log at Appendix E).
 */
public final class V7LoadFeatureAudit implements Migration {

    private static final Path BUNDLE = Path.of("/app/archive/fa_2027q1");
    private static final int ADEQUACY_FLOOR = 500;              // A-4
    private static final double GENERAL_THRESHOLD = 0.20;       // A-1
    private static final double SENSITIVE_THRESHOLD = 0.10;     // A-2
    private static final double MACRO_THRESHOLD = 0.35;         // A-5
    private static final double TELEMETRY_THRESHOLD = 0.15;     // A-11
    private static final LocalDateTime TELEMETRY_THRESHOLD_EFFECTIVE =
            LocalDate.of(2027, 2, 25).atStartOfDay();           // A-11 takes effect 2027-02-25
    private static final LocalDateTime TELEMETRY_THRESHOLD_SUNSET =
            LocalDate.of(2027, 3, 1).atStartOfDay();            // A-13 rescinds A-11 from 2027-03-01
    private static final double HARD_CEILING = 0.50;            // clause 8
    private static final int SYSTEMIC_RUN_COUNT = 3;            // A-14: systemic at >= 3 distinct runs
    private static final double PSI_FLOOR = 0.0005;            // A-15: empty-bin floor for the PSI recompute
    private static final double PROVISIONAL_SURCHARGE = 0.05;   // A-8
    private static final LocalDateTime PROVISIONAL_SURCHARGE_EFFECTIVE =
            LocalDate.of(2027, 2, 1).atStartOfDay();            // A-8 takes effect 2027-02-01
    private static final LocalDateTime PROVISIONAL_SURCHARGE_SUNSET =
            LocalDate.of(2027, 3, 1).atStartOfDay();            // A-12 withdraws A-8 from 2027-03-01
    // Clause 8.1's narrative defers acr_severity_gbm, but Appendix E (which governs) admits it: A-10.
    private static final Set<String> REGULATED_PORTFOLIO =      // A-6 + A-10
            Set.of("acr_fraud_xgb", "acr_subrogation_nn", "acr_severity_gbm");

    @Override
    public int version() {
        return 7;
    }

    @Override
    public String script() {
        return "V7__load_feature_audit.java";
    }

    private record Observation(String runId, String featureId, String cohortId,
                               Double psi, double nullRate, int sampleCount,
                               LocalDateTime observedAt, String source) {
    }

    private record RunRow(String modelName, String modelVersion) {
    }

    private record Cohort(String status, LocalDate retiredOn) {
    }

    @Override
    public void apply(Connection connection) throws Exception {
        Map<String, RunRow> runs = loadRuns(connection);
        Map<String, String> families = loadFeatureFamilies(connection);
        Set<String> monitored = loadMonitoredFeatures(connection);
        Map<String, Cohort> cohorts = loadCohorts(connection);
        Map<String, String> aliases = loadCohortAliases(connection);

        List<Observation> observations =
                readBundle(runs.keySet(), families.keySet(), cohorts.keySet(), aliases);
        List<Observation> surviving = supersede(observations);

        // A-15: after the binning incident, the population stability index for the affected
        // observations is recomputed from the distribution inputs, superseding the raw psi column.
        surviving = recomputePsi(surviving);

        createTables(connection);
        writeFeatureAudit(connection, surviving);

        Map<String, LocalDateTime> rescoredAt = new HashMap<>();
        Set<String> withheld = new HashSet<>();
        readEvents(runs.keySet(), rescoredAt, withheld);

        writePromotionAudit(connection, surviving, runs, families, monitored, cohorts,
                rescoredAt, withheld);
    }

    // ---------------------------------------------------------------- registry reference data

    private Map<String, RunRow> loadRuns(Connection connection) throws Exception {
        Map<String, RunRow> runs = new LinkedHashMap<>();
        try (Statement statement = connection.createStatement();
                ResultSet rows = statement.executeQuery(
                        "SELECT run_id, model_name, model_version FROM model_run")) {
            while (rows.next()) {
                runs.put(rows.getString(1), new RunRow(rows.getString(2), rows.getString(3)));
            }
        }
        return runs;
    }

    private Map<String, String> loadFeatureFamilies(Connection connection) throws Exception {
        Map<String, String> families = new HashMap<>();
        try (Statement statement = connection.createStatement();
                ResultSet rows = statement.executeQuery("SELECT feature_id, family FROM feature_catalog")) {
            while (rows.next()) {
                families.put(rows.getString(1), rows.getString(2));
            }
        }
        return families;
    }

    private Set<String> loadMonitoredFeatures(Connection connection) throws Exception {
        Set<String> monitored = new HashSet<>();
        try (Statement statement = connection.createStatement();
                ResultSet rows = statement.executeQuery(
                        "SELECT feature_id FROM feature_catalog WHERE monitored = TRUE")) {
            while (rows.next()) {
                monitored.add(rows.getString(1));
            }
        }
        return monitored;
    }

    private Map<String, Cohort> loadCohorts(Connection connection) throws Exception {
        Map<String, Cohort> cohorts = new HashMap<>();
        try (Statement statement = connection.createStatement();
                ResultSet rows = statement.executeQuery(
                        "SELECT cohort_id, status, retired_on FROM cohort_register")) {
            while (rows.next()) {
                LocalDate retired = rows.getDate(3) == null ? null : rows.getDate(3).toLocalDate();
                cohorts.put(rows.getString(1), new Cohort(rows.getString(2), retired));
            }
        }
        return cohorts;
    }

    private Map<String, String> loadCohortAliases(Connection connection) throws Exception {
        Map<String, String> aliases = new HashMap<>();
        try (Statement statement = connection.createStatement();
                ResultSet rows = statement.executeQuery(
                        "SELECT legacy_alias, cohort_id FROM cohort_register WHERE legacy_alias IS NOT NULL")) {
            while (rows.next()) {
                aliases.put(rows.getString(1), rows.getString(2));
            }
        }
        return aliases;
    }

    // ---------------------------------------------------------------- bundle ingestion

    private List<Observation> readBundle(Set<String> knownRuns, Set<String> knownFeatures,
                                         Set<String> knownCohorts, Map<String, String> aliases)
            throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        JsonNode manifest = mapper.readTree(BUNDLE.resolve("manifest.json").toFile());

        List<Observation> observations = new ArrayList<>();
        for (JsonNode member : manifest.get("members")) {
            // Clause 1.2: only released members are ingested; quarantine excludes a member entirely.
            if (!"released".equals(member.get("status").asText())) {
                continue;
            }
            String format = member.get("format").asText();
            Path path = BUNDLE.resolve(member.get("path").asText());
            if ("csv".equals(format)) {
                observations.addAll(readCsv(path, knownRuns, knownFeatures, knownCohorts));
            } else if ("tsv".equals(format)) {
                observations.addAll(readLegacy(path, knownRuns, knownFeatures, aliases));
            }
        }
        return observations;
    }

    private List<Observation> readCsv(Path path, Set<String> knownRuns, Set<String> knownFeatures,
                                      Set<String> knownCohorts) throws Exception {
        List<Observation> observations = new ArrayList<>();
        try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            reader.readLine();  // header
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.isBlank()) {
                    continue;
                }
                String[] cell = splitCsv(line);
                String runId = cell[0];
                String featureId = cell[1];
                String cohortId = cell[2];
                // Clause 2: referential integrity is decided by the registry, not by the bundle.
                if (!knownRuns.contains(runId) || !knownFeatures.contains(featureId)
                        || !knownCohorts.contains(cohortId)) {
                    continue;
                }
                observations.add(new Observation(runId, featureId, cohortId,
                        parsePsi(cell[3]), Double.parseDouble(cell[4]), Integer.parseInt(cell[5]),
                        utc(cell[6]), "csv"));
            }
        }
        return observations;
    }

    private List<Observation> readLegacy(Path path, Set<String> knownRuns, Set<String> knownFeatures,
                                         Map<String, String> aliases) throws Exception {
        List<Observation> observations = new ArrayList<>();
        String tab = "\t";
        try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            // Clause 1.3: the legacy extracts disagree on column order, so the header is the only
            // thing that says what a column holds. Never read these by position.
            String[] header = reader.readLine().split(tab, -1);
            Map<String, Integer> column = new HashMap<>();
            for (int i = 0; i < header.length; i++) {
                column.put(header[i].trim(), i);
            }

            String line;
            while ((line = reader.readLine()) != null) {
                if (line.isBlank()) {
                    continue;
                }
                String[] cell = line.split(tab, -1);
                // Clause 2: a legacy alias with no registered owner resolves to nothing.
                String cohortId = aliases.get(cell[column.get("cohort_alias")]);
                String featureId = cell[column.get("feature")];
                String runId = cell[column.get("run")];
                if (cohortId == null || !knownRuns.contains(runId) || !knownFeatures.contains(featureId)) {
                    continue;
                }
                // Clause 1.3: basis points, parts per million, epoch milliseconds.
                double psi = Double.parseDouble(cell[column.get("psi_bp")]) / 10_000.0;
                double nullRate = Double.parseDouble(cell[column.get("nulls_ppm")]) / 1_000_000.0;
                int samples = Integer.parseInt(cell[column.get("samples")]);
                LocalDateTime observedAt = LocalDateTime.ofInstant(
                        Instant.ofEpochMilli(Long.parseLong(cell[column.get("observed_at_ms")])),
                        ZoneOffset.UTC);
                observations.add(new Observation(runId, featureId, cohortId, psi, nullRate,
                        samples, observedAt, "legacy"));
            }
        }
        return observations;
    }

    /** RFC 4180 field splitting: honour quoted fields and unescape doubled quotes. */
    private String[] splitCsv(String line) {
        List<String> fields = new ArrayList<>();
        StringBuilder field = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (quoted) {
                if (c == '"') {
                    if (i + 1 < line.length() && line.charAt(i + 1) == '"') {
                        field.append('"');
                        i++;
                    } else {
                        quoted = false;
                    }
                } else {
                    field.append(c);
                }
            } else if (c == '"') {
                quoted = true;
            } else if (c == ',') {
                fields.add(field.toString());
                field.setLength(0);
            } else {
                field.append(c);
            }
        }
        fields.add(field.toString());
        return fields.toArray(new String[0]);
    }

    private Double parsePsi(String raw) {
        String value = raw.trim();
        if (value.isEmpty() || value.equalsIgnoreCase("nan")) {
            return null;
        }
        double psi = Double.parseDouble(value);
        return Double.isNaN(psi) ? null : psi;
    }

    private LocalDateTime utc(String iso) {
        return OffsetDateTime.parse(iso.trim()).withOffsetSameInstant(ZoneOffset.UTC).toLocalDateTime();
    }

    /** Clause 4: the latest observation wins; on an exact tie the CSV member beats the legacy member. */
    private List<Observation> supersede(List<Observation> observations) {
        Map<String, Observation> winners = new TreeMap<>();
        for (Observation candidate : observations) {
            String key = candidate.runId() + " " + candidate.featureId() + " " + candidate.cohortId();
            Observation held = winners.get(key);
            if (held == null || beats(candidate, held)) {
                winners.put(key, candidate);
            }
        }
        return new ArrayList<>(winners.values());
    }

    private boolean beats(Observation candidate, Observation held) {
        int byInstant = candidate.observedAt().compareTo(held.observedAt());
        if (byInstant != 0) {
            return byInstant > 0;
        }
        return "csv".equals(candidate.source()) && !"csv".equals(held.source());
    }

    // ---------------------------------------------------------------- PSI recompute (A-15)

    /**
     * A-15: an observation that carries a binned distribution input has its population stability
     * index recomputed from those bins and the raw psi column superseded. Only observations that
     * survived supersession and integrity are touched; the rest keep their loaded value.
     */
    private List<Observation> recomputePsi(List<Observation> surviving) throws Exception {
        Map<String, Double> recomputed = readDistributions();
        if (recomputed.isEmpty()) {
            return surviving;
        }
        List<Observation> adjusted = new ArrayList<>();
        for (Observation observation : surviving) {
            String key = observation.runId() + " " + observation.featureId() + " " + observation.cohortId();
            Double psi = recomputed.get(key);
            if (psi == null) {
                adjusted.add(observation);
            } else {
                adjusted.add(new Observation(observation.runId(), observation.featureId(),
                        observation.cohortId(), psi, observation.nullRate(), observation.sampleCount(),
                        observation.observedAt(), observation.source()));
            }
        }
        return adjusted;
    }

    private Map<String, Double> readDistributions() throws Exception {
        Map<String, Double> out = new HashMap<>();
        ObjectMapper mapper = new ObjectMapper();
        JsonNode manifest = mapper.readTree(BUNDLE.resolve("manifest.json").toFile());
        for (JsonNode member : manifest.get("members")) {
            if (!"released".equals(member.get("status").asText())
                    || !"psi_bins".equals(member.get("format").asText())) {
                continue;
            }
            Path path = BUNDLE.resolve(member.get("path").asText());
            try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
                reader.readLine();  // header
                String line;
                while ((line = reader.readLine()) != null) {
                    if (line.isBlank()) {
                        continue;
                    }
                    String[] cell = splitCsv(line);
                    out.put(cell[0] + " " + cell[1] + " " + cell[2],
                            computePsi(parseBinList(cell[3]), parseBinList(cell[4])));
                }
            }
        }
        return out;
    }

    /**
     * The population stability index over the supplied bins: the actual counts are turned into
     * shares against their total, every expected and actual share below {@code PSI_FLOOR} is
     * floored to it, and the index is the sum over bins of (actual - expected) * ln(actual/expected).
     */
    private double computePsi(double[] expected, double[] actualCounts) {
        double total = 0.0;
        for (double count : actualCounts) {
            total += count;
        }
        double psi = 0.0;
        for (int i = 0; i < expected.length; i++) {
            double e = Math.max(expected[i], PSI_FLOOR);
            double a = Math.max(actualCounts[i] / total, PSI_FLOOR);
            psi += (a - e) * Math.log(a / e);
        }
        return psi;
    }

    private double[] parseBinList(String field) {
        String[] parts = field.split("\\|", -1);
        double[] values = new double[parts.length];
        for (int i = 0; i < parts.length; i++) {
            values[i] = Double.parseDouble(parts[i].trim());
        }
        return values;
    }

    // ---------------------------------------------------------------- run lifecycle events

    private void readEvents(Set<String> knownRuns, Map<String, LocalDateTime> rescoredAt,
                            Set<String> withheld) throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        Map<String, LocalDateTime> latestEventAt = new HashMap<>();
        Map<String, String> latestEvent = new HashMap<>();

        for (String line : Files.readAllLines(BUNDLE.resolve("events/run_events.jsonl"),
                StandardCharsets.UTF_8)) {
            if (line.isBlank()) {
                continue;
            }
            JsonNode event = mapper.readTree(line);
            String runId = event.get("run_id").asText();
            if (!knownRuns.contains(runId)) {
                continue;
            }
            String kind = event.get("event").asText();
            LocalDateTime at = utc(event.get("at").asText());

            LocalDateTime seen = latestEventAt.get(runId);
            if (seen == null || at.isAfter(seen)) {
                latestEventAt.put(runId, at);
                latestEvent.put(runId, kind);
            }
            // Clause 5: where a run carries several rescores, the latest one governs.
            if ("RESCORED".equals(kind)) {
                LocalDateTime held = rescoredAt.get(runId);
                if (held == null || at.isAfter(held)) {
                    rescoredAt.put(runId, at);
                }
            }
        }
        // Clause 5: an abort matters only when it is the terminal event.
        for (Map.Entry<String, String> entry : latestEvent.entrySet()) {
            if ("AUDIT_ABORTED".equals(entry.getValue())) {
                withheld.add(entry.getKey());
            }
        }
    }

    // ---------------------------------------------------------------- persistence

    private void createTables(Connection connection) throws Exception {
        try (Statement statement = connection.createStatement()) {
            statement.execute(
                    "CREATE TABLE feature_audit ("
                            + "run_id VARCHAR(64) NOT NULL, "
                            + "feature_id VARCHAR(64) NOT NULL, "
                            + "cohort_id VARCHAR(64) NOT NULL, "
                            + "psi DOUBLE, "
                            + "null_rate DOUBLE NOT NULL, "
                            + "sample_count INTEGER NOT NULL, "
                            + "observed_at TIMESTAMP NOT NULL, "
                            + "source VARCHAR(16) NOT NULL, "
                            + "PRIMARY KEY (run_id, feature_id, cohort_id))");
            statement.execute(
                    "CREATE TABLE promotion_audit ("
                            + "run_id VARCHAR(64) NOT NULL PRIMARY KEY, "
                            + "model_name VARCHAR(64) NOT NULL, "
                            + "model_version VARCHAR(32) NOT NULL, "
                            + "cohorts_evaluated INTEGER NOT NULL, "
                            + "rows_considered INTEGER NOT NULL, "
                            + "drifted_features INTEGER NOT NULL, "
                            + "underpowered_rows INTEGER NOT NULL, "
                            + "unscored_rows INTEGER NOT NULL, "
                            + "max_psi DOUBLE NOT NULL, "
                            + "null_rate_p95 DOUBLE NOT NULL, "
                            + "decision VARCHAR(16) NOT NULL, "
                            + "CONSTRAINT fk_promotion_decision FOREIGN KEY (decision) "
                            + "REFERENCES promotion_decision (decision))");
        }
    }

    private void writeFeatureAudit(Connection connection, List<Observation> surviving) throws Exception {
        try (PreparedStatement insert = connection.prepareStatement(
                "INSERT INTO feature_audit (run_id, feature_id, cohort_id, psi, null_rate, "
                        + "sample_count, observed_at, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)")) {
            for (Observation observation : surviving) {
                insert.setString(1, observation.runId());
                insert.setString(2, observation.featureId());
                insert.setString(3, observation.cohortId());
                if (observation.psi() == null) {
                    insert.setNull(4, Types.DOUBLE);
                } else {
                    insert.setDouble(4, observation.psi());
                }
                insert.setDouble(5, observation.nullRate());
                insert.setInt(6, observation.sampleCount());
                insert.setObject(7, observation.observedAt());
                insert.setString(8, observation.source());
                insert.addBatch();
            }
            insert.executeBatch();
        }
    }

    private void writePromotionAudit(Connection connection, List<Observation> surviving,
                                     Map<String, RunRow> runs, Map<String, String> families,
                                     Set<String> monitored, Map<String, Cohort> cohorts,
                                     Map<String, LocalDateTime> rescoredAt, Set<String> withheld)
            throws Exception {
        // Per-run figures are computed for every run first, because clause 8.2's systemic-feature
        // escalation is a cycle-level judgement: whether a feature is systemic depends on how many
        // distinct runs it drifts in across the whole audit, so no run can be decided in isolation.
        record Audit(String runId, RunRow run, int cohortsEvaluated, int rowsConsidered,
                     Set<String> driftedFeatures, int underpowered, int unscored, double maxPsi,
                     double nullRateP95, boolean sensitiveDrift) {
        }

        List<Audit> audits = new ArrayList<>();
        Map<String, Set<String>> driftRunsByFeature = new HashMap<>();

        for (String runId : new TreeSet<>(runs.keySet())) {
            if (withheld.contains(runId)) {
                continue;                                       // clause 5: terminal abort
            }
            RunRow run = runs.get(runId);
            LocalDateTime rescore = rescoredAt.get(runId);

            List<Observation> eligible = new ArrayList<>();
            for (Observation observation : surviving) {
                if (!observation.runId().equals(runId)) {
                    continue;
                }
                if (!monitored.contains(observation.featureId())) {
                    continue;                                   // unmonitored features are not evaluated
                }
                if (!inScope(cohorts.get(observation.cohortId()), observation.observedAt())) {
                    continue;                                   // clause 3: cohort scoping
                }
                if (rescore != null && observation.observedAt().isBefore(rescore)) {
                    continue;                                   // clause 5: reference window rebuilt
                }
                eligible.add(observation);
            }
            if (eligible.isEmpty()) {
                continue;                                       // clause 8: no eligible observation
            }

            // Clause 6: classify each eligible observation exactly once, unscored first.
            int unscored = 0;
            int underpowered = 0;
            List<Observation> scored = new ArrayList<>();
            for (Observation observation : eligible) {
                if (observation.psi() == null) {
                    unscored++;
                } else if (observation.sampleCount() < ADEQUACY_FLOOR) {
                    underpowered++;
                } else {
                    scored.add(observation);
                }
            }

            Set<String> driftedFeatures = new TreeSet<>();
            boolean sensitiveDrift = false;
            double maxPsi = 0.0;
            for (Observation observation : scored) {
                String family = families.get(observation.featureId());
                String status = cohorts.get(observation.cohortId()).status();
                maxPsi = Math.max(maxPsi, observation.psi());
                // clause 7: inclusive comparison, against the threshold in force when this
                // observation was recorded (clause 0: an amendment binds from its effective date)
                if (observation.psi() >= threshold(family, status, observation.observedAt())) {
                    driftedFeatures.add(observation.featureId());
                    if ("sensitive_attr".equals(family)) {
                        sensitiveDrift = true;
                    }
                }
            }
            // A-14: accumulate, per feature, the distinct runs in which it drifts.
            for (String feature : driftedFeatures) {
                driftRunsByFeature.computeIfAbsent(feature, key -> new TreeSet<>()).add(runId);
            }

            // Clause 9.2: nearest-rank 95th percentile of the eligible null rates.
            List<Double> nullRates = new ArrayList<>();
            for (Observation observation : eligible) {
                nullRates.add(observation.nullRate());
            }
            double nullRateP95 = nearestRankP95(nullRates);

            Set<String> evaluatedCohorts = new TreeSet<>();
            for (Observation observation : eligible) {
                evaluatedCohorts.add(observation.cohortId());
            }

            audits.add(new Audit(runId, run, evaluatedCohorts.size(), eligible.size(),
                    driftedFeatures, underpowered, unscored, maxPsi, nullRateP95, sensitiveDrift));
        }

        // Clause 8.2 / A-14: a feature that drifts in three or more distinct runs across the cycle
        // is systemic. Counted over distinct runs, not over drift findings.
        Set<String> systemic = new TreeSet<>();
        for (Map.Entry<String, Set<String>> entry : driftRunsByFeature.entrySet()) {
            if (entry.getValue().size() >= SYSTEMIC_RUN_COUNT) {
                systemic.add(entry.getKey());
            }
        }

        try (PreparedStatement insert = connection.prepareStatement(
                "INSERT INTO promotion_audit (run_id, model_name, model_version, cohorts_evaluated, "
                        + "rows_considered, drifted_features, underpowered_rows, unscored_rows, "
                        + "max_psi, null_rate_p95, decision) "
                        + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")) {

            for (Audit audit : audits) {
                String decision = decide(audit.run().modelName(), audit.sensitiveDrift(),
                        audit.driftedFeatures().size(), audit.maxPsi(), audit.unscored());
                // Clause 8.2 / A-14: escalation is applied after the base determination and only
                // ever turns a manual-review hold into a rejection; it does not override a
                // conduct-override or material-drift rejection, nor disturb a clear run.
                if ("HOLD".equals(decision)
                        && !Collections.disjoint(audit.driftedFeatures(), systemic)) {
                    decision = "REJECT";
                }

                insert.setString(1, audit.runId());
                insert.setString(2, audit.run().modelName());
                insert.setString(3, audit.run().modelVersion());
                insert.setInt(4, audit.cohortsEvaluated());
                insert.setInt(5, audit.rowsConsidered());
                insert.setInt(6, audit.driftedFeatures().size());
                insert.setInt(7, audit.underpowered());
                insert.setInt(8, audit.unscored());
                insert.setDouble(9, audit.maxPsi());
                insert.setDouble(10, audit.nullRateP95());
                insert.setString(11, decision);
                insert.addBatch();
            }
            insert.executeBatch();
        }
    }

    /** Clause 3: ACTIVE and PROVISIONAL are in scope; SUSPENDED never is; RETIRED is, until it retires. */
    private boolean inScope(Cohort cohort, LocalDateTime observedAt) {
        if (cohort == null || "SUSPENDED".equals(cohort.status())) {
            return false;
        }
        if ("RETIRED".equals(cohort.status())) {
            if (cohort.retiredOn() == null) {
                return false;
            }
            return observedAt.isBefore(cohort.retiredOn().atStartOfDay());
        }
        return true;
    }

    /** Clause 7, as amended by A-1, A-2, A-5, A-8, A-11, A-12 and A-13, resolved as of the observation's instant. */
    private double threshold(String family, String cohortStatus, LocalDateTime observedAt) {
        double threshold = GENERAL_THRESHOLD;
        if ("sensitive_attr".equals(family)) {
            threshold = SENSITIVE_THRESHOLD;
        } else if ("macro_econ".equals(family)) {
            threshold = MACRO_THRESHOLD;
        } else if ("telemetry".equals(family)
                && !observedAt.isBefore(TELEMETRY_THRESHOLD_EFFECTIVE)
                && observedAt.isBefore(TELEMETRY_THRESHOLD_SUNSET)) {
            // A-11: telemetry carries an enacted 0.15 figure, but only from its effective date, and
            // A-13 rescinds it from 2027-03-01. Outside the window [A-11, A-13) a telemetry feature
            // falls back to the general threshold (clause 0).
            threshold = TELEMETRY_THRESHOLD;
        }
        // A-8 reaches observations recorded on or after it took effect, and A-12 withdraws it from
        // its own effective date (clause 0): the surcharge binds only the window [A-8, A-12).
        if ("PROVISIONAL".equals(cohortStatus)
                && !observedAt.isBefore(PROVISIONAL_SURCHARGE_EFFECTIVE)
                && observedAt.isBefore(PROVISIONAL_SURCHARGE_SUNSET)) {
            threshold -= PROVISIONAL_SURCHARGE;
        }
        return threshold;
    }

    /**
     * Clause 9.2: the 95th percentile by the nearest-rank method - sort ascending and take the
     * value at the 1-based position ceil(0.95 * N). No interpolation between neighbours.
     */
    private double nearestRankP95(List<Double> values) {
        if (values.isEmpty()) {
            return 0.0;
        }
        List<Double> ordered = new ArrayList<>(values);
        Collections.sort(ordered);
        int rank = (int) Math.ceil(0.95 * ordered.size());
        return ordered.get(Math.max(1, rank) - 1);
    }

    /** Clause 8: the clauses are applied in order and the first that matches decides the run. */
    private String decide(String modelName, boolean sensitiveDrift, int driftedFeatures,
                          double maxPsi, int unscored) {
        if (REGULATED_PORTFOLIO.contains(modelName) && sensitiveDrift) {
            return "REJECT";
        }
        if (driftedFeatures >= 3 || maxPsi >= HARD_CEILING) {
            return "REJECT";
        }
        if (driftedFeatures >= 1 || unscored > 0) {
            return "HOLD";
        }
        return "PROMOTE";
    }
}
