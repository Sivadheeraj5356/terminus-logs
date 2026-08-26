package org.example.parity;

import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public final class Main {
    private Main() {}

    public static void main(String[] args) {
        try {
            run(args);
        } catch (Exception exception) {
            String message = exception.getMessage();
            System.err.println(message == null || message.isBlank() ? exception.getClass().getSimpleName() : message);
            System.exit(2);
        }
    }

    private static void run(String[] args) throws Exception {
        CliOptions options = CliOptions.parse(args);
        SourceSpec source = SourceSpec.read(options.source());
        source.verify(options.modelDir());
        List<String> labels = Labels.read(options.modelDir().resolve("config.json"));
        List<ManifestEntry> entries = ManifestReader.read(options.manifest());
        Policy policy = Policy.read(options.policy(), labels.size(), entries);

        List<float[]> tensors = new ArrayList<>();
        for (ManifestEntry entry : entries) {
            tensors.add(Preprocessor.apply(PpmImage.read(entry.path())));
        }
        Map<Integer, EngineProfile> pytorch = EngineRunner.run(
                "PyTorch", options.modelDir(), tensors, policy.batchSizes(), labels.size());
        Map<Integer, EngineProfile> onnx = EngineRunner.run(
                "OnnxRuntime", options.modelDir(), tensors, policy.batchSizes(), labels.size());
        ObjectNode report = ParityEvaluator.report(
                new TrialData(source, policy, labels, entries, tensors, pytorch, onnx));
        AtomicPublisher.write(options.output(), report);
    }
}
