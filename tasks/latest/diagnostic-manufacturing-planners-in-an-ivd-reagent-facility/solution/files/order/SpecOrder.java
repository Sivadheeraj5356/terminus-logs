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
        rows.sort(Comparator
                .comparingInt((JsonObject row) -> row.get("priority").getAsInt())
                .thenComparing(row -> row.get("spec_id").getAsString()));
        JsonArray out = new JsonArray();
        for (JsonObject row : rows) {
            out.add(row);
        }
        return out;
    }
}
