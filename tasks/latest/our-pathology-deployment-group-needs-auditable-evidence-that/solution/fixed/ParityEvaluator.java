package org.example.parity;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

final class ParityEvaluator {
    private static final ObjectMapper MAPPER = JsonMapper.builder().build();

    private ParityEvaluator() {}

    static ObjectNode report(TrialData data) {
        ObjectNode root = MAPPER.createObjectNode();
        root.put("schema_version", 2);
        root.set("model", model(data.source()));
        root.set("preprocessing", preprocessing());
        root.set("policy", policy(data.policy()));

        ArrayNode samples = root.putArray("samples");
        Map<String, GroupStats> groups = new LinkedHashMap<>();
        for (String group : data.policy().requiredGroups()) {
            groups.put(group, new GroupStats());
        }
        boolean allBatchSupported = true;
        boolean allTopK = true;
        boolean allPass = true;
        double maximumCross = 0;
        double maximumJs = 0;
        double maximumBatch = 0;
        for (int sampleIndex = 0; sampleIndex < data.entries().size(); sampleIndex++) {
            ManifestEntry entry = data.entries().get(sampleIndex);
            double[] torchBaseline = data.pytorch().get(1).probabilities()[sampleIndex];
            double[] onnxBaseline = data.onnxruntime().get(1).probabilities()[sampleIndex];
            ObjectNode sample = samples.addObject();
            sample.put("id", entry.id());
            sample.put("image", entry.image());
            sample.put("sha256", entry.sha256());
            sample.put("group", entry.group());
            sample.put("tensor_sha256", TensorFingerprint.sha256(data.tensors().get(sampleIndex)));
            ObjectNode engines = sample.putObject("engines");
            engines.set("pytorch", engine(torchBaseline, data.labels(), data.policy().topK()));
            engines.set("onnxruntime", engine(onnxBaseline, data.labels(), data.policy().topK()));
            ArrayNode profiles = sample.putArray("profiles");
            boolean samplePass = true;
            double sampleCross = 0;
            double sampleJs = 0;
            double sampleBatch = 0;
            for (int batchSize : data.policy().batchSizes()) {
                EngineProfile torchProfile = data.pytorch().get(batchSize);
                EngineProfile onnxProfile = data.onnxruntime().get(batchSize);
                boolean torchSupported = torchProfile.supported();
                boolean onnxSupported = onnxProfile.supported();
                double[] torch = torchSupported ? torchProfile.probabilities()[sampleIndex] : null;
                double[] onnx = onnxSupported ? onnxProfile.probabilities()[sampleIndex] : null;

                Double rawCross = torchSupported && onnxSupported ? drift(torch, onnx) : null;
                Double rawJs = torchSupported && onnxSupported ? jsDivergence(torch, onnx) : null;
                Double rawTorchBatch = torchSupported ? drift(torchBaseline, torch) : null;
                Double rawOnnxBatch = onnxSupported ? drift(onnxBaseline, onnx) : null;
                Double shownCross = rawCross == null ? null : drift(rounded(torch), rounded(onnx));
                Double shownJs = rawJs == null ? null : jsDivergence(rounded(torch), rounded(onnx));
                Double shownTorchBatch = rawTorchBatch == null ? null
                        : drift(rounded(torchBaseline), rounded(torch));
                Double shownOnnxBatch = rawOnnxBatch == null ? null
                        : drift(rounded(onnxBaseline), rounded(onnx));
                List<Integer> torchTop = torchSupported ? top(torch, data.policy().topK()) : null;
                List<Integer> onnxTop = onnxSupported ? top(onnx, data.policy().topK()) : null;
                boolean topMatch = torchTop != null && torchTop.equals(onnxTop);

                ObjectNode profile = profiles.addObject();
                profile.put("batch_size", batchSize);
                profile.put("pytorch_batch_supported", torchSupported);
                profile.put("onnxruntime_batch_supported", onnxSupported);
                putVector(profile, "pytorch_probabilities", torch);
                putVector(profile, "onnxruntime_probabilities", onnx);
                putNullable(profile, "cross_engine_max_drift", shownCross);
                putNullable(profile, "cross_engine_js_divergence", shownJs);
                putNullable(profile, "pytorch_batch_max_drift", shownTorchBatch);
                putNullable(profile, "onnxruntime_batch_max_drift", shownOnnxBatch);
                putRanking(profile, "pytorch_top_k", torchTop);
                putRanking(profile, "onnxruntime_top_k", onnxTop);
                profile.put("top_k_match", topMatch);

                samplePass &= torchSupported && onnxSupported && topMatch
                        && rawCross <= data.policy().maxProbabilityDrift()
                        && rawJs <= data.policy().maxJsDivergence()
                        && rawTorchBatch <= data.policy().maxBatchDrift()
                        && rawOnnxBatch <= data.policy().maxBatchDrift();
                allBatchSupported &= torchSupported && onnxSupported;
                allTopK &= topMatch;
                if (shownCross != null) {
                    sampleCross = Math.max(sampleCross, shownCross);
                    maximumCross = Math.max(maximumCross, shownCross);
                }
                if (shownJs != null) {
                    sampleJs = Math.max(sampleJs, shownJs);
                    maximumJs = Math.max(maximumJs, shownJs);
                }
                if (shownTorchBatch != null) {
                    sampleBatch = Math.max(sampleBatch, shownTorchBatch);
                    maximumBatch = Math.max(maximumBatch, shownTorchBatch);
                }
                if (shownOnnxBatch != null) {
                    sampleBatch = Math.max(sampleBatch, shownOnnxBatch);
                    maximumBatch = Math.max(maximumBatch, shownOnnxBatch);
                }
            }
            sample.put("gate_pass", samplePass);
            groups.get(entry.group()).include(samplePass, sampleCross, sampleJs, sampleBatch);
            allPass &= samplePass;
        }

        ObjectNode summary = root.putObject("summary");
        summary.put("sample_count", data.entries().size());
        ArrayNode groupResults = summary.putArray("group_results");
        for (Map.Entry<String, GroupStats> item : groups.entrySet()) {
            ObjectNode group = groupResults.addObject();
            group.put("group", item.getKey());
            group.put("sample_count", item.getValue().count);
            group.put("gate_pass", item.getValue().pass);
            group.set("max_probability_drift", number(item.getValue().cross));
            group.set("max_js_divergence", number(item.getValue().js));
            group.set("max_batch_drift", number(item.getValue().batch));
        }
        summary.put("all_batch_sizes_supported", allBatchSupported);
        summary.put("all_top_k_match", allTopK);
        summary.set("max_probability_drift", number(maximumCross));
        summary.set("max_js_divergence", number(maximumJs));
        summary.set("max_batch_drift", number(maximumBatch));
        summary.put("portability_gate", allPass && groups.values().stream().allMatch(group -> group.pass));
        return root;
    }

    private static ObjectNode model(SourceSpec source) {
        ObjectNode node = MAPPER.createObjectNode();
        node.put("repository", source.repository());
        node.put("revision", source.revision());
        ArrayNode artifacts = node.putArray("artifacts");
        for (Map.Entry<String, String> artifact : source.artifacts().entrySet()) {
            ObjectNode item = artifacts.addObject();
            item.put("file", artifact.getKey());
            item.put("sha256", artifact.getValue());
        }
        return node;
    }

    private static ObjectNode preprocessing() {
        ObjectNode node = MAPPER.createObjectNode();
        node.put("resize_shorter", 256);
        node.put("crop_size", 224);
        node.put("layout", "NCHW");
        node.put("channel_order", "RGB");
        node.put("scale", "1/max_value");
        addVector(node.putArray("mean"), new double[] {0.485, 0.456, 0.406});
        addVector(node.putArray("std"), new double[] {0.229, 0.224, 0.225});
        node.put("tensor_fingerprint", "sha256-f32le-nchw");
        return node;
    }

    private static ObjectNode policy(Policy policy) {
        ObjectNode node = MAPPER.createObjectNode();
        node.put("top_k", policy.topK());
        node.set("max_probability_drift", number(policy.maxProbabilityDrift()));
        node.set("max_batch_drift", number(policy.maxBatchDrift()));
        node.set("max_js_divergence", number(policy.maxJsDivergence()));
        ArrayNode sizes = node.putArray("batch_sizes");
        policy.batchSizes().forEach(sizes::add);
        ArrayNode groups = node.putArray("required_groups");
        policy.requiredGroups().forEach(groups::add);
        return node;
    }

    private static ObjectNode engine(double[] probabilities, List<String> labels, int topK) {
        ObjectNode node = MAPPER.createObjectNode();
        ArrayNode vector = node.putArray("probabilities");
        for (double probability : probabilities) {
            vector.add(number(probability));
        }
        ArrayNode ranking = node.putArray("top_k");
        for (int index : top(probabilities, topK)) {
            ObjectNode item = ranking.addObject();
            item.put("index", index);
            item.put("label", labels.get(index));
            item.set("probability", number(probabilities[index]));
        }
        return node;
    }

    private static List<Integer> top(double[] probabilities, int count) {
        List<Integer> indices = new ArrayList<>();
        for (int i = 0; i < probabilities.length; i++) {
            indices.add(i);
        }
        indices.sort(Comparator.<Integer>comparingDouble(index -> probabilities[index])
                .reversed().thenComparingInt(Integer::intValue));
        return List.copyOf(indices.subList(0, count));
    }

    private static double drift(double[] left, double[] right) {
        if (left.length != right.length) {
            throw new IllegalArgumentException("probability vector length mismatch");
        }
        double maximum = 0;
        for (int i = 0; i < left.length; i++) {
            maximum = Math.max(maximum, Math.abs(left[i] - right[i]));
        }
        return maximum;
    }

    private static double jsDivergence(double[] left, double[] right) {
        if (left.length != right.length) {
            throw new IllegalArgumentException("probability vector length mismatch");
        }
        double value = 0;
        for (int i = 0; i < left.length; i++) {
            double midpoint = (left[i] + right[i]) / 2;
            if (left[i] > 0) {
                value += 0.5 * left[i] * Math.log(left[i] / midpoint) / Math.log(2);
            }
            if (right[i] > 0) {
                value += 0.5 * right[i] * Math.log(right[i] / midpoint) / Math.log(2);
            }
        }
        return Math.max(0, value);
    }

    private static double[] rounded(double[] values) {
        double[] result = new double[values.length];
        for (int i = 0; i < values.length; i++) {
            result[i] = BigDecimal.valueOf(values[i]).setScale(8, RoundingMode.HALF_UP).doubleValue();
        }
        return result;
    }

    private static JsonNode number(double value) {
        if (!Double.isFinite(value)) {
            throw new IllegalArgumentException("non-finite report value");
        }
        BigDecimal decimal = BigDecimal.valueOf(value).setScale(8, RoundingMode.HALF_UP);
        if (decimal.signum() == 0) {
            decimal = BigDecimal.ZERO.setScale(8);
        }
        return MAPPER.getNodeFactory().numberNode(decimal);
    }

    private static void putNullable(ObjectNode node, String name, Double value) {
        if (value == null) {
            node.putNull(name);
        } else {
            node.set(name, number(value));
        }
    }

    private static void putRanking(ObjectNode node, String name, List<Integer> ranking) {
        if (ranking == null) {
            node.putNull(name);
            return;
        }
        ArrayNode array = node.putArray(name);
        ranking.forEach(array::add);
    }

    private static void putVector(ObjectNode node, String name, double[] values) {
        if (values == null) {
            node.putNull(name);
            return;
        }
        ArrayNode array = node.putArray(name);
        for (double value : values) {
            array.add(number(value));
        }
    }

    private static void addVector(ArrayNode node, double[] values) {
        for (double value : values) {
            node.add(number(value));
        }
    }

    private static final class GroupStats {
        private int count;
        private boolean pass = true;
        private double cross;
        private double js;
        private double batch;

        private void include(boolean samplePass, double sampleCross, double sampleJs, double sampleBatch) {
            count++;
            pass &= samplePass;
            cross = Math.max(cross, sampleCross);
            js = Math.max(js, sampleJs);
            batch = Math.max(batch, sampleBatch);
        }
    }
}
