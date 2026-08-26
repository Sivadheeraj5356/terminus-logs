package com.blendcert.stage;

import com.google.gson.JsonObject;
import com.blendcert.JsonCodec;
import com.blendcert.MissingStateArtifactException;
import com.blendcert.seal.FeasibilityDigest;

import java.nio.file.Path;

public final class SealStage {
    private static final Path ALLOCATION = Path.of("/app/state/allocation.json");
    private static final Path DUAL = Path.of("/app/state/dual-certificate.json");
    private static final Path OUT = Path.of("/app/output/blend-feasibility-cert.json");

    private SealStage() {}

    public static int run() {
        if (!ALLOCATION.toFile().exists() || !DUAL.toFile().exists()) {
            throw new MissingStateArtifactException("allocation or dual-certificate missing");
        }
        JsonObject allocation = JsonCodec.read(ALLOCATION).getAsJsonObject();
        JsonObject dual = JsonCodec.read(DUAL).getAsJsonObject();
        JsonObject cert = FeasibilityDigest.seal(allocation, dual);
        JsonCodec.write(OUT, cert);
        return 0;
    }
}
