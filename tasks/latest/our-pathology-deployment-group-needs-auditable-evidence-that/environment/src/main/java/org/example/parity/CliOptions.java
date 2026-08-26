package org.example.parity;

import java.nio.file.Path;
record CliOptions(Path manifest, Path policy, Path modelDir, Path source, Path output) {
    static CliOptions parse(String[] args) {
        throw new UnsupportedOperationException("CLI validation is incomplete");
    }
}
