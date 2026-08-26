package com.foldlab.io;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

public final class ManifestWriter {
    private final Gson gson = new GsonBuilder().disableHtmlEscaping().create();

    public void write(Path manifestPath, Map<String, Object> payload) throws IOException {
        Files.createDirectories(manifestPath.getParent());
        Files.writeString(manifestPath, gson.toJson(payload), StandardCharsets.UTF_8);
    }

    public String toJson(Map<String, Object> payload) {
        return gson.toJson(payload);
    }
}
