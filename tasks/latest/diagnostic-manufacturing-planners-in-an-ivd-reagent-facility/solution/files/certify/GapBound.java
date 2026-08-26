package com.blendcert.certify;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

public final class GapBound {
    private static final double TOL = 1e-6;

    private GapBound() {}

    public static double optimalityGapBound(
            JsonObject solutionRow,
            JsonObject shadowPrices,
            JsonArray lots,
            JsonObject spec,
            double volume) {
        double gap = 0.0;
        JsonObject lotAmounts = solutionRow.getAsJsonObject("lot_amounts_ml");
        JsonObject lotDuals = shadowPrices.getAsJsonObject("lots");
        for (var el : lots) {
            JsonObject lot = el.getAsJsonObject();
            String lotId = lot.get("lot_id").getAsString();
            double avail = lot.get("available_ml").getAsDouble();
            double amount = lotAmounts.get(lotId).getAsDouble();
            double slack = avail - amount;
            double dual = lotDuals.get(lotId).getAsDouble();
            if (slack > TOL && dual > TOL) {
                gap += slack * dual;
            }
        }

        JsonObject concentrations = solutionRow.getAsJsonObject("concentrations");
        JsonObject lowerDuals = shadowPrices.getAsJsonObject("analytes_lower");
        JsonObject upperDuals = shadowPrices.getAsJsonObject("analytes_upper");
        for (var entry : spec.getAsJsonObject("bands").entrySet()) {
            String analyte = entry.getKey();
            JsonObject band = entry.getValue().getAsJsonObject();
            double lower = band.get("lower").getAsDouble();
            double upper = band.get("upper").getAsDouble();
            double conc = concentrations.get(analyte).getAsDouble();
            double lowerSlack = conc - lower;
            double upperSlack = upper - conc;
            double lowerDual = lowerDuals.get(analyte).getAsDouble();
            double upperDual = upperDuals.get(analyte).getAsDouble();
            if (lowerSlack > TOL && lowerDual > TOL) {
                gap += lowerSlack * lowerDual;
            }
            if (upperSlack > TOL && upperDual > TOL) {
                gap += upperSlack * upperDual;
            }
        }
        return gap;
    }

    public static double round6(double value) {
        return Math.round(value * 1_000_000.0) / 1_000_000.0;
    }
}
