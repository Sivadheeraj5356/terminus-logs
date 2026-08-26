import java.io.BufferedReader;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;

public class Solver {
    private static final boolean IGNORE_GAP_DECAY = false;
    private static final boolean UPDATE_BEFORE_PREDICT = false;
    private static final boolean WRONG_UNIT_CONVERSION = false;
    private static final boolean DISABLE_COOLDOWN = false;

    private static class Config {
        double alpha;
        double priorStrength;
        double phDelta;
        double phLambda;
        int resetCooldown;
        double gapDecay;
        double eps;
        List<String> dayparts;
    }

    private static class State {
        double pos = 0.0;
        double weight = 0.0;
        double ph = 0.0;
        double residMean = 0.0;
        double seen = 0.0;
        int cooldown = 0;
    }

    private static class Request {
        String requestId;
        int eventId;
        double threshold;
    }

    private static class Label {
        int arrivalEventId;
        int sourceEventId;
        double sub3;
    }

    private static class Pending {
        String requestId;
        int sourceEventId;
        String daypart;
        double knownWh;
        double threshold;
        double probability;
    }

    private static class Prediction {
        String requestId;
        int eventId;
        double probability;
    }

    private static class Reset {
        int eventId;
        String daypart;
    }

    private static class Window {
        String id;
        int start;
        int end;
        int n = 0;
        double brier = 0.0;
        double logLoss = 0.0;
    }

    private static List<Map<String, String>> readCsv(Path path) throws IOException {
        List<Map<String, String>> rows = new ArrayList<>();
        try (BufferedReader reader = Files.newBufferedReader(path)) {
            String headerLine = reader.readLine();
            if (headerLine == null) {
                return rows;
            }
            String[] headers = headerLine.split(",", -1);
            String line;
            while ((line = reader.readLine()) != null) {
                String[] parts = line.split(",", -1);
                Map<String, String> row = new HashMap<>();
                for (int i = 0; i < headers.length; i++) {
                    row.put(headers[i], i < parts.length ? parts[i] : "");
                }
                rows.add(row);
            }
        }
        return rows;
    }

    private static Config readConfig(Path dir) throws IOException {
        Map<String, String> values = new HashMap<>();
        for (Map<String, String> row : readCsv(dir.resolve("learner_config.csv"))) {
            values.put(row.get("key"), row.get("value"));
        }
        Config cfg = new Config();
        cfg.alpha = Double.parseDouble(values.get("alpha"));
        cfg.priorStrength = Double.parseDouble(values.get("prior_strength"));
        cfg.phDelta = Double.parseDouble(values.get("page_hinkley_delta"));
        cfg.phLambda = Double.parseDouble(values.get("page_hinkley_lambda"));
        cfg.resetCooldown = Integer.parseInt(values.get("reset_cooldown"));
        cfg.gapDecay = Double.parseDouble(values.get("gap_decay"));
        cfg.eps = Double.parseDouble(values.get("probability_epsilon"));
        cfg.dayparts = new ArrayList<>();
        Collections.addAll(cfg.dayparts, values.get("dayparts").split("\\|", -1));
        return cfg;
    }

    private static boolean missing(Map<String, String> row) {
        return "1".equals(row.get("missing_flag"));
    }

    private static double parseDouble(String value) {
        return Double.parseDouble(value);
    }

    private static int parseInt(String value) {
        return Integer.parseInt(value);
    }

    private static double probability(State state, Config cfg) {
        return (state.pos + 0.5 * cfg.priorStrength) / (state.weight + cfg.priorStrength);
    }

    private static String q(String value) {
        return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    private static String number(double value) {
        if (Double.isNaN(value) || Double.isInfinite(value)) {
            throw new IllegalStateException("non-finite output");
        }
        return String.format(Locale.US, "%.12f", value);
    }

    private static void processLabels(
        int arrivalEventId,
        List<Label> labels,
        Map<Integer, List<Pending>> pendingBySource,
        LinkedHashMap<String, State> states,
        List<Reset> resets,
        List<Window> windows,
        Config cfg,
        int[] labelsApplied
    ) {
        if (labels == null) {
            return;
        }
        labels.sort((a, b) -> {
            int cmp = Integer.compare(a.sourceEventId, b.sourceEventId);
            if (cmp != 0) {
                return cmp;
            }
            return Integer.compare(a.arrivalEventId, b.arrivalEventId);
        });
        for (Label label : labels) {
            List<Pending> pendings = pendingBySource.remove(label.sourceEventId);
            if (pendings == null) {
                continue;
            }
            for (Pending pending : pendings) {
                double denom = WRONG_UNIT_CONVERSION ? pending.knownWh * 60.0 : pending.knownWh;
                double share = denom > 0.0 ? label.sub3 / denom : 0.0;
                double y = share >= pending.threshold ? 1.0 : 0.0;
                double p = pending.probability;
                labelsApplied[0] += 1;

                double clipped = Math.max(cfg.eps, Math.min(1.0 - cfg.eps, p));
                double brier = (p - y) * (p - y);
                double logLoss = -(y * Math.log(clipped) + (1.0 - y) * Math.log(1.0 - clipped));
                for (Window window : windows) {
                    if (pending.sourceEventId >= window.start && pending.sourceEventId <= window.end) {
                        window.n += 1;
                        window.brier += brier;
                        window.logLoss += logLoss;
                    }
                }

                State state = states.get(pending.daypart);
                if (state == null) {
                    throw new IllegalStateException("unknown daypart " + pending.daypart);
                }
                if (!UPDATE_BEFORE_PREDICT) {
                    state.pos = (1.0 - cfg.alpha) * state.pos + cfg.alpha * y;
                    state.weight = (1.0 - cfg.alpha) * state.weight + cfg.alpha;
                }

                double residual = y - p;
                state.seen += 1.0;
                state.residMean += (residual - state.residMean) / state.seen;
                state.ph = Math.max(0.0, state.ph + residual - state.residMean - cfg.phDelta);
                if (state.cooldown > 0) {
                    state.cooldown -= 1;
                }
                boolean cooldownOk = DISABLE_COOLDOWN || state.cooldown == 0;
                if (state.ph > cfg.phLambda && cooldownOk) {
                    Reset reset = new Reset();
                    reset.eventId = arrivalEventId;
                    reset.daypart = pending.daypart;
                    resets.add(reset);
                    state.pos = 0.0;
                    state.weight = 0.0;
                    state.ph = 0.0;
                    state.residMean = 0.0;
                    state.seen = 0.0;
                    state.cooldown = DISABLE_COOLDOWN ? 0 : cfg.resetCooldown;
                }
            }
        }
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            throw new IllegalArgumentException("expected data directory argument");
        }
        Path dir = Path.of(args[0]);
        Config cfg = readConfig(dir);

        LinkedHashMap<String, State> states = new LinkedHashMap<>();
        for (String daypart : cfg.dayparts) {
            states.put(daypart, new State());
        }

        Map<Integer, List<Request>> requestsByEvent = new HashMap<>();
        for (Map<String, String> row : readCsv(dir.resolve("prediction_requests.csv"))) {
            Request request = new Request();
            request.requestId = row.get("request_id");
            request.eventId = parseInt(row.get("event_id"));
            request.threshold = parseDouble(row.get("threshold_share"));
            requestsByEvent.computeIfAbsent(request.eventId, key -> new ArrayList<>()).add(request);
        }
        for (List<Request> requests : requestsByEvent.values()) {
            requests.sort((a, b) -> a.requestId.compareTo(b.requestId));
        }

        TreeMap<Integer, List<Label>> labelsByArrival = new TreeMap<>();
        for (Map<String, String> row : readCsv(dir.resolve("label_arrivals.csv"))) {
            Label label = new Label();
            label.arrivalEventId = parseInt(row.get("arrival_event_id"));
            label.sourceEventId = parseInt(row.get("source_event_id"));
            label.sub3 = parseDouble(row.get("sub_metering_3_wh"));
            labelsByArrival.computeIfAbsent(label.arrivalEventId, key -> new ArrayList<>()).add(label);
        }

        List<Window> windows = new ArrayList<>();
        for (Map<String, String> row : readCsv(dir.resolve("score_windows.csv"))) {
            Window window = new Window();
            window.id = row.get("window_id");
            window.start = parseInt(row.get("start_event_id"));
            window.end = parseInt(row.get("end_event_id"));
            windows.add(window);
        }

        List<Map<String, String>> readings = readCsv(dir.resolve("readings.csv"));
        Map<Integer, List<Pending>> pendingBySource = new HashMap<>();
        List<Prediction> predictions = new ArrayList<>();
        List<Reset> resets = new ArrayList<>();
        int missingEvents = 0;
        int[] labelsApplied = new int[] {0};

        for (Map<String, String> row : readings) {
            int eventId = parseInt(row.get("event_id"));
            if (missing(row)) {
                missingEvents += 1;
                double decay = IGNORE_GAP_DECAY ? 1.0 : cfg.gapDecay;
                for (State state : states.values()) {
                    state.pos *= decay;
                    state.weight *= decay;
                }
            } else {
                String daypart = row.get("daypart_id");
                State state = states.get(daypart);
                if (state == null) {
                    throw new IllegalStateException("unknown daypart " + daypart);
                }
                double activeKw = parseDouble(row.get("global_active_power_kw"));
                double knownWh = activeKw * 1000.0 / 60.0;
                List<Request> requests = requestsByEvent.get(eventId);
                if (requests != null) {
                    for (Request request : requests) {
                        double p = probability(state, cfg);
                        if (UPDATE_BEFORE_PREDICT) {
                            p = probability(state, cfg);
                        }
                        Prediction prediction = new Prediction();
                        prediction.requestId = request.requestId;
                        prediction.eventId = eventId;
                        prediction.probability = p;
                        predictions.add(prediction);

                        Pending pending = new Pending();
                        pending.requestId = request.requestId;
                        pending.sourceEventId = eventId;
                        pending.daypart = daypart;
                        pending.knownWh = knownWh;
                        pending.threshold = request.threshold;
                        pending.probability = p;
                        pendingBySource.computeIfAbsent(eventId, key -> new ArrayList<>()).add(pending);
                    }
                }
            }
            List<Label> labels = labelsByArrival.remove(eventId);
            processLabels(eventId, labels, pendingBySource, states, resets, windows, cfg, labelsApplied);
        }

        while (!labelsByArrival.isEmpty()) {
            Map.Entry<Integer, List<Label>> entry = labelsByArrival.pollFirstEntry();
            processLabels(entry.getKey(), entry.getValue(), pendingBySource, states, resets, windows, cfg, labelsApplied);
        }

        StringBuilder out = new StringBuilder();
        out.append("{");
        out.append(q("n_events")).append(":").append(readings.size()).append(",");
        out.append(q("n_predictions")).append(":").append(predictions.size()).append(",");
        out.append(q("n_labels")).append(":").append(labelsApplied[0]).append(",");
        out.append(q("n_missing_events")).append(":").append(missingEvents).append(",");

        out.append(q("predictions")).append(":[");
        for (int i = 0; i < predictions.size(); i++) {
            Prediction p = predictions.get(i);
            if (i > 0) {
                out.append(",");
            }
            out.append("{")
                .append(q("request_id")).append(":").append(q(p.requestId)).append(",")
                .append(q("event_id")).append(":").append(p.eventId).append(",")
                .append(q("probability")).append(":").append(number(p.probability))
                .append("}");
        }
        out.append("],");

        out.append(q("resets")).append(":[");
        for (int i = 0; i < resets.size(); i++) {
            Reset reset = resets.get(i);
            if (i > 0) {
                out.append(",");
            }
            out.append("{")
                .append(q("event_id")).append(":").append(reset.eventId).append(",")
                .append(q("daypart_id")).append(":").append(q(reset.daypart))
                .append("}");
        }
        out.append("],");

        out.append(q("windows")).append(":[");
        for (int i = 0; i < windows.size(); i++) {
            Window window = windows.get(i);
            if (i > 0) {
                out.append(",");
            }
            out.append("{")
                .append(q("window_id")).append(":").append(q(window.id)).append(",")
                .append(q("n_scored")).append(":").append(window.n).append(",")
                .append(q("brier")).append(":");
            if (window.n == 0) {
                out.append("null");
            } else {
                out.append(number(window.brier / window.n));
            }
            out.append(",").append(q("log_loss")).append(":");
            if (window.n == 0) {
                out.append("null");
            } else {
                out.append(number(window.logLoss / window.n));
            }
            out.append("}");
        }
        out.append("],");

        out.append(q("final_state")).append(":{")
            .append(q("gap_events")).append(":").append(missingEvents).append(",")
            .append(q("labels_applied")).append(":").append(labelsApplied[0]).append(",")
            .append(q("dayparts")).append(":[");
        int index = 0;
        for (Map.Entry<String, State> entry : states.entrySet()) {
            State state = entry.getValue();
            if (index > 0) {
                out.append(",");
            }
            out.append("{")
                .append(q("daypart_id")).append(":").append(q(entry.getKey())).append(",")
                .append(q("pos")).append(":").append(number(state.pos)).append(",")
                .append(q("weight")).append(":").append(number(state.weight)).append(",")
                .append(q("ph")).append(":").append(number(state.ph)).append(",")
                .append(q("resid_mean")).append(":").append(number(state.residMean)).append(",")
                .append(q("seen")).append(":").append(number(state.seen)).append(",")
                .append(q("cooldown")).append(":").append(state.cooldown)
                .append("}");
            index += 1;
        }
        out.append("]}}");
        System.out.println(out);
    }
}
