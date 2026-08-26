package org.example.parity;

import java.nio.file.Path;

record PpmImage(int width, int height, int maxValue, int[] samples) {
    static PpmImage read(Path path) {
        throw new UnsupportedOperationException("P3 PPM decoding is incomplete");
    }
}
