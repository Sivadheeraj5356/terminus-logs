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
        model.addProperty("batch_generation", lotsRoot.get("batch_generation").getAsInt());
        model.addProperty("target_volume_ml", lotsRoot.get("target_volume_ml").getAsDouble());
        model.add("lots", lotsRoot.getAsJsonArray("lots").deepCopy());
        model.add("specifications", SpecOrder.sortSpecifications(specs));
        model.addProperty("source_lots", lotsPath.toString());
        model.addProperty("source_specs", specsPath.toString());
        return model;
    }
}
