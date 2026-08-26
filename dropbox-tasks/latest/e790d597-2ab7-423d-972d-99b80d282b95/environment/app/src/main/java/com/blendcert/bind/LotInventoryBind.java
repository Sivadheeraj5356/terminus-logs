package com.blendcert.bind;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

public final class LotInventoryBind {
    private LotInventoryBind() {}

    public static JsonObject buildSnapshot(JsonObject lotsRoot) {
        JsonObject inventory = new JsonObject();
        inventory.addProperty("schema_version", "lot-inventory/1");
        inventory.addProperty("batch_generation", lotsRoot.get("batch_generation").getAsInt());
        inventory.add("lots", rowsFromCatalog(lotsRoot.getAsJsonArray("lots")));
        return inventory;
    }

    public static JsonObject buildSnapshotFromCatalog(JsonArray catalogLots, int batchGeneration) {
        JsonObject inventory = new JsonObject();
        inventory.addProperty("schema_version", "lot-inventory/1");
        inventory.addProperty("batch_generation", batchGeneration);
        inventory.add("lots", rowsFromCatalog(catalogLots));
        return inventory;
    }

    private static JsonArray rowsFromCatalog(JsonArray catalogLots) {
        JsonArray rows = new JsonArray();
        for (var el : catalogLots) {
            JsonObject lot = el.getAsJsonObject();
            JsonObject row = new JsonObject();
            row.addProperty("lot_id", lot.get("lot_id").getAsString());
            row.addProperty("remaining_ml", lot.get("available_ml").getAsDouble());
            rows.add(row);
        }
        return rows;
    }
}
