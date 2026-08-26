package org.example.parity;

final class Preprocessor {
    static final int CROP = 224;
    static final int VALUES = 3 * CROP * CROP;

    private Preprocessor() {}

    static float[] apply(PpmImage image) {
        throw new UnsupportedOperationException("preprocessing pipeline is incomplete");
    }
}
