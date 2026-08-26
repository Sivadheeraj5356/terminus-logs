package com.blendcert;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;

public final class JsonCodec {
    private static final Gson GSON = new GsonBuilder().disableHtmlEscaping().create();

    private JsonCodec() {}

    public static String compactSerialize(JsonElement element) {
        return GSON.toJson(sortKeys(element));
    }

    private static JsonElement sortKeys(JsonElement element) {
        if (element.isJsonObject()) {
            JsonObject sorted = new JsonObject();
            List<String> keys = new ArrayList<>();
            for (Map.Entry<String, JsonElement> entry : element.getAsJsonObject().entrySet()) {
                keys.add(entry.getKey());
            }
            Collections.sort(keys);
            for (String key : keys) {
                sorted.add(key, sortKeys(element.getAsJsonObject().get(key)));
            }
            return sorted;
        }
        if (element.isJsonArray()) {
            JsonArray sorted = new JsonArray();
            for (JsonElement child : element.getAsJsonArray()) {
                sorted.add(sortKeys(child));
            }
            return sorted;
        }
        return element;
    }

    public static JsonElement read(Path path) {
        try {
            String raw = Files.readString(path, StandardCharsets.UTF_8);
            return JsonParser.parseString(raw);
        } catch (IOException e) {
            throw new BadInputException("cannot read " + path + ": " + e.getMessage());
        }
    }

    public static void write(Path path, JsonElement element) {
        try {
            Files.createDirectories(path.getParent());
            Files.writeString(path, compactSerialize(element), StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new BadInputException("cannot write " + path + ": " + e.getMessage());
        }
    }
}
