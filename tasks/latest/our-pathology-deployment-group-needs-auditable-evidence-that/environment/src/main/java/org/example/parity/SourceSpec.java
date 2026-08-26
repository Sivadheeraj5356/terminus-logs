package org.example.parity;

import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;

record SourceSpec(String repository, String revision, LinkedHashMap<String, String> artifacts) {
    static final List<String> FILES = List.of("mobilenet_v3_large.pt", "mobilenet_v3_large.onnx",
            "mobilenet_v3_large.onnx.data", "config.json");
    static SourceSpec read(Path path) {
        throw new UnsupportedOperationException("model provenance parsing is incomplete");
    }

    void verify(Path modelDir) {
        throw new UnsupportedOperationException("model artifact verification is incomplete");
    }
}
