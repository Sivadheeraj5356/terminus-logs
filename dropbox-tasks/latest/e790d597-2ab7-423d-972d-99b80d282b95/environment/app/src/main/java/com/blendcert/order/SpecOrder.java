package com.blendcert.order;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public final class SpecOrder {
    private SpecOrder() {}

    public static JsonArray sortSpecifications(JsonArray specs) {
        List<JsonObject> rows = new ArrayList<>();
        for (var el : specs) {
            rows.add(el.getAsJsonObject().deepCopy());
        }
        rows.sort(Comparator.comparingDouble(SpecOrder::lowerBoundSum)
                .thenComparing(row -> row.get("spec_id").getAsString()));
        JsonArray out = new JsonArray();
        for (JsonObject row : rows) {
            out.add(row);
        }
        return out;
    }

    private static double lowerBoundSum(JsonObject spec) {
        double sum = 0.0;
        for (var entry : spec.getAsJsonObject("bands").entrySet()) {
            sum += entry.getValue().getAsJsonObject().get("lower").getAsDouble();
        }
        return sum;
    }
}
