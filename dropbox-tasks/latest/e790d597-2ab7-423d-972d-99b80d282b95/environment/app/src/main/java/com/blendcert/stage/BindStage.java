package com.blendcert.stage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.blendcert.BadInputException;
import com.blendcert.JsonCodec;
import com.blendcert.bind.BlendModelBind;
import com.blendcert.bind.LotInventoryBind;

import java.nio.file.Path;

public final class BindStage {
    private static final Path LOTS = Path.of("/app/input/lots.json");
    private static final Path SPECS = Path.of("/app/input/specs.json");
    private static final Path OUT = Path.of("/app/state/blend-model.json");
    private static final Path INVENTORY = Path.of("/app/state/lot-inventory.json");

    private BindStage() {}

    public static int run() {
        if (!LOTS.toFile().exists() || !SPECS.toFile().exists()) {
            throw new BadInputException("missing input files");
        }
        JsonObject lotsRoot = JsonCodec.read(LOTS).getAsJsonObject();
        JsonObject specsRoot = JsonCodec.read(SPECS).getAsJsonObject();
        JsonArray specs = specsRoot.getAsJsonArray("specifications");
        JsonObject model = BlendModelBind.buildModel(lotsRoot, specs, LOTS, SPECS);
        JsonCodec.write(OUT, model);
        JsonObject inventory = LotInventoryBind.buildSnapshot(lotsRoot);
        JsonCodec.write(INVENTORY, inventory);
        return 0;
    }
}
