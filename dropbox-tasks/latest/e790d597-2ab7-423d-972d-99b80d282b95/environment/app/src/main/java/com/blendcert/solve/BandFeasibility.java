package com.blendcert.solve;

import com.google.gson.JsonObject;

import java.util.Map;

public final class BandFeasibility {
    private static final double EPS = 1e-6;

    private BandFeasibility() {}

    public static boolean concentrationsFeasible(
            JsonObject spec, Map<String, Double> concentrations) {
        JsonObject bands = spec.getAsJsonObject("bands");
        for (var entry : bands.entrySet()) {
            String analyte = entry.getKey();
            double lower = entry.getValue().getAsJsonObject().get("lower").getAsDouble();
            double achieved = concentrations.getOrDefault(analyte, 0.0);
            if (achieved < lower - EPS) {
                return false;
            }
        }
        return true;
    }
}
