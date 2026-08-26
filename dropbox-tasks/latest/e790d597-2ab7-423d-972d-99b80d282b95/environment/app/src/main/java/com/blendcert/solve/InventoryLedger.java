package com.blendcert.solve;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import java.util.HashMap;
import java.util.Map;

public final class InventoryLedger {
    private InventoryLedger() {}

    public static JsonArray catalogWithRemaining(JsonArray catalogLots, JsonObject inventory) {
        Map<String, Double> remaining = new HashMap<>();
        for (var el : inventory.getAsJsonArray("lots")) {
            JsonObject row = el.getAsJsonObject();
            remaining.put(row.get("lot_id").getAsString(), row.get("remaining_ml").getAsDouble());
        }
        JsonArray combined = new JsonArray();
        for (var el : catalogLots) {
            JsonObject catalog = el.getAsJsonObject().deepCopy();
            String lotId = catalog.get("lot_id").getAsString();
            if (remaining.containsKey(lotId)) {
                catalog.addProperty("available_ml", remaining.get(lotId));
            }
            combined.add(catalog);
        }
        return combined;
    }

    public static void debit(JsonObject inventory, JsonObject lotAmountsMl) {
        Map<String, Double> debits = new HashMap<>();
        for (var entry : lotAmountsMl.entrySet()) {
            debits.put(entry.getKey(), entry.getValue().getAsDouble());
        }
        JsonArray rows = inventory.getAsJsonArray("lots");
        for (var el : rows) {
            JsonObject row = el.getAsJsonObject();
            String lotId = row.get("lot_id").getAsString();
            if (debits.containsKey(lotId)) {
                double next = row.get("remaining_ml").getAsDouble() - debits.get(lotId);
                row.addProperty("remaining_ml", BlendSolve.round6(next));
            }
        }
    }
}
