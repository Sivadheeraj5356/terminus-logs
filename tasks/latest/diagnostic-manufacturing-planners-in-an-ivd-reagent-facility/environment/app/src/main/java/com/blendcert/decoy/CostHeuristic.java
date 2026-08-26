package com.blendcert.decoy;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.blendcert.JsonCodec;
import com.blendcert.solve.BlendSolve;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public final class CostHeuristic {
    private CostHeuristic() {}

    public static void maybeWrite(JsonObject model, JsonArray solutions) {
        String flag = System.getenv("BLEND_GREEDY_PREVIEW");
        if (flag == null || !flag.equals("1")) {
            return;
        }
        JsonArray lots = model.getAsJsonArray("lots");
        List<JsonObject> sortedLots = new ArrayList<>();
        for (var el : lots) {
            sortedLots.add(el.getAsJsonObject());
        }
        sortedLots.sort(Comparator.comparingDouble(l -> l.get("cost_per_ml").getAsDouble()));

        JsonArray preview = new JsonArray();
        double volume = model.get("target_volume_ml").getAsDouble();
        for (var el : solutions) {
            JsonObject sol = el.getAsJsonObject();
            JsonObject row = new JsonObject();
            row.addProperty("spec_id", sol.get("spec_id").getAsString());
            JsonObject greedy = new JsonObject();
            double remaining = volume;
            for (JsonObject lot : sortedLots) {
                String lotId = lot.get("lot_id").getAsString();
                double take = Math.min(remaining, lot.get("available_ml").getAsDouble());
                greedy.addProperty(lotId, BlendSolve.round6(take));
                remaining -= take;
                if (remaining <= 0.0) {
                    break;
                }
            }
            row.add("greedy_amounts_ml", greedy);
            preview.add(row);
        }

        JsonObject out = new JsonObject();
        out.addProperty("schema_version", "greedy-preview/1");
        out.add("preview", preview);
        try {
            JsonCodec.write(Path.of("/app/state/greedy-preview.json"), out);
        } catch (Exception ignored) {
            // decoy only — never affects certify or seal
        }
    }
}
