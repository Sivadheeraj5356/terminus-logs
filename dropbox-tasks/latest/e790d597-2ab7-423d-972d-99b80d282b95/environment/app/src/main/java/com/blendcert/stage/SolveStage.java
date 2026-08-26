package com.blendcert.stage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.blendcert.JsonCodec;
import com.blendcert.MissingStateArtifactException;
import com.blendcert.decoy.CostHeuristic;
import com.blendcert.solve.BlendSolve;

import java.nio.file.Path;

public final class SolveStage {
    private static final Path MODEL = Path.of("/app/state/blend-model.json");
    private static final Path ALLOCATION = Path.of("/app/state/allocation.json");
    private static final Path LEDGER = Path.of("/app/output/blend-ledger.json");

    private SolveStage() {}

    public static int run() {
        if (!MODEL.toFile().exists()) {
            throw new MissingStateArtifactException("blend-model.json missing");
        }
        JsonObject model = JsonCodec.read(MODEL).getAsJsonObject();
        JsonArray lots = model.getAsJsonArray("lots");
        JsonArray specs = model.getAsJsonArray("specifications");
        double volume = model.get("target_volume_ml").getAsDouble();

        JsonArray solutions = new JsonArray();
        JsonArray ledgerEntries = new JsonArray();
        for (var el : specs) {
            JsonObject spec = el.getAsJsonObject();
            BlendSolve.Result result = BlendSolve.solve(lots, spec, volume);
            JsonObject row = new JsonObject();
            row.addProperty("spec_id", spec.get("spec_id").getAsString());
            row.addProperty("priority", spec.get("priority").getAsInt());
            if (result.feasible) {
                row.addProperty("feasible", true);
                row.addProperty("total_cost", BlendSolve.round6(result.totalCost));
                row.add("lot_amounts_ml", BlendSolve.lotAmountsJson(result.lotAmountsMl));
                row.add("concentrations", BlendSolve.concentrationsJson(result.concentrations));
            } else {
                row.addProperty("feasible", false);
                row.addProperty("total_cost", 0.0);
                row.add("lot_amounts_ml", new JsonObject());
                row.add("concentrations", new JsonObject());
            }
            solutions.add(row);

            JsonObject ledgerRow = new JsonObject();
            ledgerRow.addProperty("spec_id", spec.get("spec_id").getAsString());
            ledgerRow.addProperty("priority", spec.get("priority").getAsInt());
            ledgerRow.addProperty("feasible", row.get("feasible").getAsBoolean());
            ledgerRow.addProperty("total_cost", row.get("total_cost").getAsDouble());
            ledgerRow.add("lot_amounts_ml", row.getAsJsonObject("lot_amounts_ml").deepCopy());
            ledgerEntries.add(ledgerRow);
        }

        JsonObject allocation = new JsonObject();
        allocation.addProperty("schema_version", "allocation/1");
        allocation.addProperty("batch_generation", model.get("batch_generation").getAsInt());
        allocation.addProperty("target_volume_ml", volume);
        allocation.add("solutions", solutions);
        JsonCodec.write(ALLOCATION, allocation);

        JsonObject ledger = new JsonObject();
        ledger.addProperty("schema_version", "blend-ledger/1");
        ledger.addProperty("batch_generation", model.get("batch_generation").getAsInt());
        ledger.add("entries", ledgerEntries);
        JsonCodec.write(LEDGER, ledger);

        CostHeuristic.maybeWrite(model, solutions);
        return 0;
    }
}
