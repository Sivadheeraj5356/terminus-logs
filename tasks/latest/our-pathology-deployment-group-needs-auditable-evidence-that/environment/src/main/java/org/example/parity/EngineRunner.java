package org.example.parity;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;

final class EngineRunner {
    private EngineRunner() {}

    static Map<Integer, EngineProfile> run(String engine, Path modelDir, List<float[]> tensors,
            List<Integer> batchSizes, int labelCount) {
        throw new UnsupportedOperationException("DJL engine execution is incomplete");
    }
}
