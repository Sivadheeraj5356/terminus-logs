package org.example.parity;

import com.fasterxml.jackson.core.StreamReadFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;

final class Labels {
    private static final ObjectMapper MAPPER = JsonMapper.builder()
            .enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION).build();

    private Labels() {}

    static List<String> read(Path path) throws IOException {
        JsonNode root = MAPPER.readTree(path.toFile());
        JsonNode mapping = root.get("id2label");
        if (mapping == null || !mapping.isObject() || mapping.isEmpty()) {
            throw new IllegalArgumentException("config id2label must be a non-empty object");
        }
        List<String> actualKeys = new ArrayList<>();
        mapping.fieldNames().forEachRemaining(actualKeys::add);
        List<String> expectedKeys = new ArrayList<>();
        for (int index = 0; index < mapping.size(); index++) {
            expectedKeys.add(Integer.toString(index));
        }
        if (!actualKeys.equals(expectedKeys)) {
            throw new IllegalArgumentException("config id2label keys must be consecutive and ordered");
        }
        List<String> labels = new ArrayList<>();
        for (int index = 0; index < mapping.size(); index++) {
            JsonNode label = mapping.get(Integer.toString(index));
            if (label == null || !label.isTextual() || label.textValue().isBlank()) {
                throw new IllegalArgumentException("config id2label indices must be consecutive");
            }
            labels.add(label.textValue());
        }
        if (new HashSet<>(labels).size() != labels.size()) {
            throw new IllegalArgumentException("config labels must be unique");
        }
        return List.copyOf(labels);
    }
}
