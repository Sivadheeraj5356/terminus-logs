package com.blendcert.seal;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.blendcert.JsonCodec;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

public final class FeasibilityDigest {
    private FeasibilityDigest() {}

    public static JsonObject seal(JsonObject allocation, JsonObject dualCertificate) {
        JsonArray rows = new JsonArray();
        for (var el : allocation.getAsJsonArray("solutions")) {
            JsonObject src = el.getAsJsonObject();
            JsonObject row = new JsonObject();
            row.addProperty("spec_id", src.get("spec_id").getAsString());
            row.addProperty("priority", src.get("priority").getAsInt());
            row.addProperty("feasible", src.get("feasible").getAsBoolean());
            row.addProperty("total_cost", src.get("total_cost").getAsDouble());
            row.add("lot_amounts_ml", src.getAsJsonObject("lot_amounts_ml").deepCopy());
            rows.add(row);
        }

        JsonObject certDoc = new JsonObject();
        certDoc.addProperty("cert_version", "1.0");
        certDoc.addProperty("batch_generation", allocation.get("batch_generation").getAsInt());
        certDoc.add("allocation_rows", rows);

        String digest = sha256(JsonCodec.compactSerialize(allocation));
        certDoc.addProperty("feasibility_digest", digest);

        JsonObject layers = new JsonObject();
        layers.addProperty("allocation", digest);
        layers.addProperty("dual", "");
        layers.addProperty("combined", "");
        certDoc.add("digest_layers", layers);

        JsonObject summary = new JsonObject();
        int feasible = 0;
        double totalCost = 0.0;
        for (var el : allocation.getAsJsonArray("solutions")) {
            JsonObject sol = el.getAsJsonObject();
            if (sol.get("feasible").getAsBoolean()) {
                feasible++;
                totalCost += sol.get("total_cost").getAsDouble();
            }
        }
        summary.addProperty("feasible_count", feasible);
        summary.addProperty("infeasible_count", allocation.getAsJsonArray("solutions").size() - feasible);
        summary.addProperty("total_cost", FeasibilityDigest.round6(totalCost));
        certDoc.add("summary", summary);
        return certDoc;
    }

    public static String sha256(String payload) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] dig = md.digest(payload.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : dig) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    public static String threeLayerDigest(
            JsonObject allocation, JsonObject dualCertificate, JsonObject certBody) {
        String allocationLayer = sha256(JsonCodec.compactSerialize(allocation));
        String dualLayer = sha256(JsonCodec.compactSerialize(dualCertificate));
        String combinedLayer = sha256(JsonCodec.compactSerialize(certBody));
        return sha256(allocationLayer + "|" + dualLayer + "|" + combinedLayer);
    }

    public static double round6(double value) {
        return Math.round(value * 1_000_000.0) / 1_000_000.0;
    }
}
