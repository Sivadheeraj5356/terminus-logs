package org.example.parity;

import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.file.Path;

final class AtomicPublisher {
    private AtomicPublisher() {}

    static void write(Path output, ObjectNode report) {
        throw new UnsupportedOperationException("transactional report publishing is incomplete");
    }
}
