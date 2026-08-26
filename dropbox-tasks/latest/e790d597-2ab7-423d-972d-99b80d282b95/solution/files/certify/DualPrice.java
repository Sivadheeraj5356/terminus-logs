package com.blendcert.certify;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.blendcert.solve.BlendSolve;

public final class DualPrice {
    private static final double DUAL_EPS_RATIO = 1e-4;

    private DualPrice() {}

    public static JsonObject computeShadowPrices(
            JsonArray lots, JsonObject spec, double volume, JsonObject solutionRow) {
        double baseCost = solutionRow.get("total_cost").getAsDouble();
        double eps = Math.max(1e-4, volume * DUAL_EPS_RATIO);

        JsonObject prices = new JsonObject();
        BlendSolve.Result volUp = BlendSolve.solve(lots, spec, volume + eps);
        double volumeDual = volUp.feasible ? (volUp.totalCost - baseCost) / eps : 0.0;
        prices.addProperty("volume", BlendSolve.round6(volumeDual));

        JsonObject lotAmounts = solutionRow.getAsJsonObject("lot_amounts_ml");
        JsonObject lotDuals = new JsonObject();
        for (var el : lots) {
            JsonObject lot = el.getAsJsonObject();
            String lotId = lot.get("lot_id").getAsString();
            double amount = lotAmounts.get(lotId).getAsDouble();
            double avail = lot.get("available_ml").getAsDouble();
            double dual = 0.0;
            if (amount >= avail - 1e-6) {
                JsonArray perturbed = perturbLotAvail(lots, lotId, eps);
                BlendSolve.Result relaxed = BlendSolve.solve(perturbed, spec, volume);
                if (relaxed.feasible) {
                    dual = Math.max(0.0, (baseCost - relaxed.totalCost) / eps);
                }
            }
            lotDuals.addProperty(lotId, BlendSolve.round6(dual));
        }
        prices.add("lots", lotDuals);

        JsonObject lowerDuals = new JsonObject();
        JsonObject upperDuals = new JsonObject();
        JsonObject concentrations = solutionRow.getAsJsonObject("concentrations");
        for (var entry : spec.getAsJsonObject("bands").entrySet()) {
            String analyte = entry.getKey();
            JsonObject band = entry.getValue().getAsJsonObject();
            double lower = band.get("lower").getAsDouble();
            double upper = band.get("upper").getAsDouble();
            double conc = concentrations.get(analyte).getAsDouble();

            double lowerDual = 0.0;
            if (conc <= lower + 1e-6) {
                JsonObject tightened = perturbBand(spec, analyte, lower + eps, upper);
                BlendSolve.Result r = BlendSolve.solve(lots, tightened, volume);
                if (r.feasible) {
                    lowerDual = Math.max(0.0, (r.totalCost - baseCost) / eps);
                }
            }
            lowerDuals.addProperty(analyte, BlendSolve.round6(lowerDual));

            double upperDual = 0.0;
            if (conc >= upper - 1e-6) {
                JsonObject relaxed = perturbBand(spec, analyte, lower, upper + eps);
                BlendSolve.Result r = BlendSolve.solve(lots, relaxed, volume);
                if (r.feasible) {
                    upperDual = Math.max(0.0, (baseCost - r.totalCost) / eps);
                }
            }
            upperDuals.addProperty(analyte, BlendSolve.round6(upperDual));
        }
        prices.add("analytes_lower", lowerDuals);
        prices.add("analytes_upper", upperDuals);
        return prices;
    }

    private static JsonArray perturbLotAvail(JsonArray lots, String lotId, double delta) {
        JsonArray out = new JsonArray();
        for (var el : lots) {
            JsonObject lot = el.getAsJsonObject().deepCopy();
            if (lot.get("lot_id").getAsString().equals(lotId)) {
                lot.addProperty(
                        "available_ml",
                        lot.get("available_ml").getAsDouble() + delta);
            }
            out.add(lot);
        }
        return out;
    }

    private static JsonObject perturbBand(
            JsonObject spec, String analyte, double lower, double upper) {
        JsonObject copy = spec.deepCopy();
        JsonObject bands = copy.getAsJsonObject("bands").deepCopy();
        JsonObject band = bands.getAsJsonObject(analyte).deepCopy();
        band.addProperty("lower", lower);
        band.addProperty("upper", upper);
        bands.add(analyte, band);
        copy.add("bands", bands);
        return copy;
    }
}
