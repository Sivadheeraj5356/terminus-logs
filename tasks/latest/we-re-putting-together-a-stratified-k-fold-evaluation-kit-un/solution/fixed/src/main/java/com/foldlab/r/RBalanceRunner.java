package com.foldlab.r;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.Map;

public final class RBalanceRunner {
    private static final Path BALANCE_SCRIPT = Path.of("/app/r/fold_balance.R");
    private final Gson gson = new Gson();

    @SuppressWarnings("unchecked")
    public Map<String, Object> run(Path manifestPath) throws IOException, InterruptedException {
        ProcessBuilder builder = new ProcessBuilder(
                "Rscript",
                BALANCE_SCRIPT.toString(),
                manifestPath.toString());
        builder.redirectErrorStream(false);
        Process process = builder.start();
        JsonObject parsed;
        try (InputStreamReader reader =
                new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8)) {
            parsed = JsonParser.parseReader(reader).getAsJsonObject();
        }
        int code = process.waitFor();
        if (code != 0) {
            throw new IOException("fold_balance.R failed with exit code " + code);
        }
        return gson.fromJson(parsed, Map.class);
    }
}
