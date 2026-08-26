package com.blendcert.bind;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.blendcert.order.SpecOrder;

import java.nio.file.Path;

public final class BlendModelBind {
    private BlendModelBind() {}

    public static JsonObject buildModel(
            JsonObject lotsRoot, JsonArray specs, Path lotsPath, Path specsPath) {
        JsonObject model = new JsonObject();
        model.addProperty("schema_version", "blend-model/1");
        int generation = lotsRoot.get("batch_generation").getAsInt();
        model.addProperty("batch_generation", generation - 1);
        model.addProperty("target_volume_ml", lotsRoot.get("target_volume_ml").getAsDouble());
        model.add("lots", roundAssays(lotsRoot.getAsJsonArray("lots")));
        model.add("specifications", SpecOrder.sortSpecifications(specs));
        model.addProperty("source_lots", lotsPath.toString());
        model.addProperty("source_specs", specsPath.toString());
        return model;
    }

    private static JsonArray roundAssays(JsonArray lots) {
        JsonArray out = new JsonArray();
        for (var el : lots) {
            JsonObject lot = el.getAsJsonObject().deepCopy();
            JsonObject assays = new JsonObject();
            for (var entry : lot.getAsJsonObject("assays").entrySet()) {
                double raw = entry.getValue().getAsDouble();
                assays.addProperty(entry.getKey(), Math.round(raw * 10.0) / 10.0);
            }
            lot.add("assays", assays);
            out.add(lot);
        }
        return out;
    }
}
