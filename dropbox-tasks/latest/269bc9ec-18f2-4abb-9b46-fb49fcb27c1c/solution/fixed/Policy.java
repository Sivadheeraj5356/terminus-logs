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
import java.util.Set;
import java.util.TreeSet;

record Policy(int topK, double maxProbabilityDrift, double maxBatchDrift,
        double maxJsDivergence, List<Integer> batchSizes, List<String> requiredGroups) {
    private static final List<String> KEYS = List.of(
            "top_k", "max_probability_drift", "max_batch_drift", "max_js_divergence",
            "batch_sizes", "required_groups");
    private static final ObjectMapper MAPPER = JsonMapper.builder()
            .enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION).build();

    static Policy read(Path path, int labels, List<ManifestEntry> entries) throws IOException {
        JsonNode root = MAPPER.readTree(path.toFile());
        List<String> keys = new ArrayList<>();
        root.fieldNames().forEachRemaining(keys::add);
        if (!root.isObject() || !keys.equals(KEYS)) {
            throw new IllegalArgumentException("invalid policy keys or ordering");
        }
        JsonNode topNode = root.get("top_k");
        if (!topNode.isIntegralNumber() || !topNode.canConvertToInt()) {
            throw new IllegalArgumentException("invalid top_k");
        }
        int topK = topNode.intValue();
        double cross = finiteNumber(root.get("max_probability_drift"), "max_probability_drift");
        double batch = finiteNumber(root.get("max_batch_drift"), "max_batch_drift");
        double js = finiteNumber(root.get("max_js_divergence"), "max_js_divergence");
        if (topK < 1 || topK > labels || cross < 0 || cross > 1 || batch < 0 || batch > 1
                || js < 0 || js > 1) {
            throw new IllegalArgumentException("policy value out of range");
        }
        JsonNode sizes = root.get("batch_sizes");
        if (!sizes.isArray() || sizes.isEmpty()) {
            throw new IllegalArgumentException("batch_sizes must be a non-empty array");
        }
        List<Integer> parsed = new ArrayList<>();
        Set<Integer> seen = new HashSet<>();
        int previous = 0;
        for (JsonNode node : sizes) {
            if (!node.isIntegralNumber() || !node.canConvertToInt()) {
                throw new IllegalArgumentException("invalid batch size");
            }
            int value = node.intValue();
            if (value <= previous || value > entries.size() || !seen.add(value)) {
                throw new IllegalArgumentException("invalid batch size");
            }
            parsed.add(value);
            previous = value;
        }
        if (parsed.get(0) != 1) {
            throw new IllegalArgumentException("batch_sizes must contain 1");
        }
        JsonNode groupsNode = root.get("required_groups");
        if (!groupsNode.isArray() || groupsNode.isEmpty()) {
            throw new IllegalArgumentException("required_groups must be a non-empty array");
        }
        List<String> groups = new ArrayList<>();
        String previousGroup = null;
        for (JsonNode node : groupsNode) {
            if (!node.isTextual() || node.textValue().isBlank()
                    || previousGroup != null && node.textValue().compareTo(previousGroup) <= 0) {
                throw new IllegalArgumentException("required_groups must be unique and sorted");
            }
            groups.add(node.textValue());
            previousGroup = node.textValue();
        }
        Set<String> manifestGroups = new TreeSet<>();
        entries.forEach(entry -> manifestGroups.add(entry.group()));
        if (!manifestGroups.equals(new TreeSet<>(groups))) {
            throw new IllegalArgumentException("required_groups must equal manifest groups");
        }
        return new Policy(topK, cross, batch, js, List.copyOf(parsed), List.copyOf(groups));
    }

    private static double finiteNumber(JsonNode node, String name) {
        if (node == null || !node.isNumber()) {
            throw new IllegalArgumentException(name + " must be a number");
        }
        double value = node.doubleValue();
        if (!Double.isFinite(value)) {
            throw new IllegalArgumentException(name + " must be finite");
        }
        return value;
    }
}
