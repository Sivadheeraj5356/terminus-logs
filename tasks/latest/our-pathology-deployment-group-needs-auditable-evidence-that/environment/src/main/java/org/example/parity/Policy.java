package org.example.parity;

import java.nio.file.Path;
import java.util.List;

record Policy(int topK, double maxProbabilityDrift, double maxBatchDrift,
        double maxJsDivergence, List<Integer> batchSizes, List<String> requiredGroups) {
    static Policy read(Path path, int labels, List<ManifestEntry> entries) {
        throw new UnsupportedOperationException("parity policy validation is incomplete");
    }
}
