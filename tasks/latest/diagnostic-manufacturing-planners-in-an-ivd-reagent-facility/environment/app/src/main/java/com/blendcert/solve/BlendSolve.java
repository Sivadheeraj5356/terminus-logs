package com.blendcert.solve;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

public final class BlendSolve {
    private static final int STEPS = 101;
    private static final double EPS = 1e-6;

    private BlendSolve() {}

    public static final class Result {
        public final boolean feasible;
        public final double totalCost;
        public final Map<String, Double> lotAmountsMl;
        public final Map<String, Double> concentrations;

        public Result(
                boolean feasible,
                double totalCost,
                Map<String, Double> lotAmountsMl,
                Map<String, Double> concentrations) {
            this.feasible = feasible;
            this.totalCost = totalCost;
            this.lotAmountsMl = lotAmountsMl;
            this.concentrations = concentrations;
        }
    }

    public static Result solve(JsonArray lots, JsonObject spec, double targetVolumeMl) {
        int n = lots.size();
        if (n == 0 || n > 4) {
            return new Result(false, 0.0, Map.of(), Map.of());
        }
        List<String> analyteNames = sortedAnalytes(spec);
        List<JsonObject> lotRows = new ArrayList<>();
        for (var el : lots) {
            lotRows.add(el.getAsJsonObject());
        }

        int[] fracs = new int[n];
        Result best = enumerateAll(lotRows, analyteNames, spec, targetVolumeMl, n, fracs, 0);
        return best == null ? new Result(false, 0.0, Map.of(), Map.of()) : best;
    }

    private static Result enumerateAll(
            List<JsonObject> lots,
            List<String> analytes,
            JsonObject spec,
            double volume,
            int n,
            int[] fracs,
            int depth) {
        Result best = null;
        if (depth == n - 1) {
            int sum = 0;
            for (int i = 0; i < n - 1; i++) {
                sum += fracs[i];
            }
            if (sum > STEPS) {
                return null;
            }
            fracs[n - 1] = STEPS - sum;
            return evaluateFractions(lots, analytes, spec, volume, fracs);
        }
        for (int f = 0; f <= STEPS; f++) {
            fracs[depth] = f;
            int partial = 0;
            for (int i = 0; i <= depth; i++) {
                partial += fracs[i];
            }
            if (partial > STEPS) {
                continue;
            }
            Result candidate = enumerateAll(lots, analytes, spec, volume, n, fracs, depth + 1);
            if (candidate != null && candidate.feasible) {
                if (best == null || candidate.totalCost < best.totalCost - EPS) {
                    best = candidate;
                }
            }
        }
        return best;
    }

    private static Result evaluateFractions(
            List<JsonObject> lots,
            List<String> analytes,
            JsonObject spec,
            double volume,
            int[] fracs) {
        int n = lots.size();
        double[] amounts = new double[n];
        for (int i = 0; i < n; i++) {
            amounts[i] = (fracs[i] / (double) STEPS) * volume;
            double avail = lots.get(i).get("available_ml").getAsDouble();
            if (amounts[i] > avail + EPS) {
                return new Result(false, 0.0, Map.of(), Map.of());
            }
        }
        Map<String, Double> concentrations = new LinkedHashMap<>();
        for (String analyte : analytes) {
            double total = 0.0;
            for (int i = 0; i < n; i++) {
                double assay = lots.get(i).getAsJsonObject("assays").get(analyte).getAsDouble();
                total += amounts[i] * assay;
            }
            concentrations.put(analyte, total / volume);
        }
        if (!BandFeasibility.concentrationsFeasible(spec, concentrations)) {
            return new Result(false, 0.0, Map.of(), Map.of());
        }
        double cost = 0.0;
        Map<String, Double> lotAmounts = new LinkedHashMap<>();
        for (int i = 0; i < n; i++) {
            String lotId = lots.get(i).get("lot_id").getAsString();
            lotAmounts.put(lotId, amounts[i]);
            cost += amounts[i] * lots.get(i).get("cost_per_ml").getAsDouble();
        }
        return new Result(true, cost, lotAmounts, concentrations);
    }

    public static List<String> sortedAnalytes(JsonObject spec) {
        List<String> names = new ArrayList<>();
        for (var entry : spec.getAsJsonObject("bands").entrySet()) {
            names.add(entry.getKey());
        }
        names.sort(String::compareTo);
        return names;
    }

    public static JsonObject concentrationsJson(Map<String, Double> concentrations) {
        JsonObject out = new JsonObject();
        TreeMap<String, Double> sorted = new TreeMap<>(concentrations);
        for (var entry : sorted.entrySet()) {
            out.addProperty(entry.getKey(), round6(entry.getValue()));
        }
        return out;
    }

    public static JsonObject lotAmountsJson(Map<String, Double> amounts) {
        JsonObject out = new JsonObject();
        TreeMap<String, Double> sorted = new TreeMap<>(amounts);
        for (var entry : sorted.entrySet()) {
            out.addProperty(entry.getKey(), round6(entry.getValue()));
        }
        return out;
    }

    public static double round6(double value) {
        return Math.round(value * 1_000_000.0) / 1_000_000.0;
    }
}
