package com.blendcert.stage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.blendcert.JsonCodec;
import com.blendcert.MissingStateArtifactException;
import com.blendcert.certify.DualPrice;
import com.blendcert.certify.GapBound;
import com.blendcert.bind.LotInventoryBind;
import com.blendcert.seal.FeasibilityDigest;
import com.blendcert.solve.InventoryLedger;

import java.nio.file.Path;

public final class CertifyStage {
    private static final Path MODEL = Path.of("/app/state/blend-model.json");
    private static final Path ALLOCATION = Path.of("/app/state/allocation.json");
    private static final Path OUT = Path.of("/app/state/dual-certificate.json");

    private CertifyStage() {}

    public static int run() {
        if (!MODEL.toFile().exists() || !ALLOCATION.toFile().exists()) {
            throw new MissingStateArtifactException("blend-model or allocation missing");
        }
        JsonObject model = JsonCodec.read(MODEL).getAsJsonObject();
        JsonObject allocation = JsonCodec.read(ALLOCATION).getAsJsonObject();
        JsonArray catalogLots = model.getAsJsonArray("lots");
        double volume = model.get("target_volume_ml").getAsDouble();
        String modelDigest = FeasibilityDigest.layerFromPath(MODEL);

        JsonArray certificates = new JsonArray();
        JsonObject workingInventory = LotInventoryBind.buildSnapshotFromCatalog(
                catalogLots, model.get("batch_generation").getAsInt());
        for (var el : allocation.getAsJsonArray("solutions")) {
            JsonObject solutionRow = el.getAsJsonObject();
            JsonObject cert = new JsonObject();
            cert.addProperty("spec_id", solutionRow.get("spec_id").getAsString());
            if (!solutionRow.get("feasible").getAsBoolean()) {
                cert.addProperty("certified", false);
                cert.add("shadow_prices", new JsonObject());
                cert.addProperty("optimality_gap_bound", 0.0);
                certificates.add(cert);
                continue;
            }
            JsonObject spec = findSpec(model.getAsJsonArray("specifications"), solutionRow.get("spec_id").getAsString());
            JsonArray lotsForSpec = InventoryLedger.catalogWithRemaining(catalogLots, workingInventory);
            JsonObject shadowPrices = DualPrice.computeShadowPrices(lotsForSpec, spec, volume, solutionRow);
            double gap = GapBound.optimalityGapBound(solutionRow, shadowPrices, lotsForSpec, spec, volume);
            cert.addProperty("certified", true);
            cert.add("shadow_prices", shadowPrices);
            cert.addProperty("optimality_gap_bound", GapBound.round6(gap));
            certificates.add(cert);
            InventoryLedger.debit(workingInventory, solutionRow.getAsJsonObject("lot_amounts_ml"));
        }

        JsonObject dual = new JsonObject();
        dual.addProperty("schema_version", "dual-certificate/1");
        dual.addProperty("batch_generation", allocation.get("batch_generation").getAsInt());
        dual.addProperty("model_layer_digest", modelDigest);
        dual.add("certificates", certificates);
        JsonCodec.write(OUT, dual);
        return 0;
    }

    private static JsonObject findSpec(JsonArray specs, String specId) {
        for (var el : specs) {
            JsonObject spec = el.getAsJsonObject();
            if (spec.get("spec_id").getAsString().equals(specId)) {
                return spec;
            }
        }
        throw new MissingStateArtifactException("spec not found in model: " + specId);
    }
}
