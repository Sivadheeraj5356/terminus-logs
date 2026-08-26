package com.blendcert.certify;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.blendcert.solve.BlendSolve;

public final class DualPrice {
    private DualPrice() {}

    public static JsonObject computeShadowPrices(
            JsonArray lots, JsonObject spec, double volume, JsonObject solutionRow) {
        double avgCost = 0.0;
        for (var el : lots) {
            avgCost += el.getAsJsonObject().get("cost_per_ml").getAsDouble();
        }
        avgCost /= lots.size();

        JsonObject prices = new JsonObject();
        prices.addProperty("volume", BlendSolve.round6(avgCost));

        JsonObject lotDuals = new JsonObject();
        for (var el : lots) {
            String lotId = el.getAsJsonObject().get("lot_id").getAsString();
            lotDuals.addProperty(lotId, BlendSolve.round6(avgCost));
        }
        prices.add("lots", lotDuals);

        JsonObject lowerDuals = new JsonObject();
        JsonObject upperDuals = new JsonObject();
        for (var entry : spec.getAsJsonObject("bands").entrySet()) {
            String analyte = entry.getKey();
            lowerDuals.addProperty(analyte, BlendSolve.round6(avgCost));
            upperDuals.addProperty(analyte, BlendSolve.round6(avgCost));
        }
        prices.add("analytes_lower", lowerDuals);
        prices.add("analytes_upper", upperDuals);
        return prices;
    }
}
