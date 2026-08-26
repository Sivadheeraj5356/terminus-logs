package org.example.parity;

import java.util.List;
import java.util.Map;

record TrialData(SourceSpec source, Policy policy, List<String> labels,
        List<ManifestEntry> entries, List<float[]> tensors, Map<Integer, EngineProfile> pytorch,
        Map<Integer, EngineProfile> onnxruntime) {}
