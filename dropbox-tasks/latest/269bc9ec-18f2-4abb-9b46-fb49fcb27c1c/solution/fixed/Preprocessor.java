package org.example.parity;

final class Preprocessor {
    static final int CROP = 224;
    static final int VALUES = 3 * CROP * CROP;
    private static final int RESIZE_SHORTER = 256;
    private static final double[] MEAN = {0.485, 0.456, 0.406};
    private static final double[] STD = {0.229, 0.224, 0.225};

    private Preprocessor() {}

    static float[] apply(PpmImage image) {
        int shortEdge = Math.min(image.width(), image.height());
        int resizedWidth = roundedDimension(image.width(), shortEdge);
        int resizedHeight = roundedDimension(image.height(), shortEdge);
        double[][][] resized = new double[resizedHeight][resizedWidth][3];
        for (int y = 0; y < resizedHeight; y++) {
            double sourceY = (y + 0.5) * image.height() / resizedHeight - 0.5;
            int y0 = clamp((int) Math.floor(sourceY), 0, image.height() - 1);
            int y1 = clamp(y0 + 1, 0, image.height() - 1);
            double wy = Math.max(0.0, Math.min(1.0, sourceY - Math.floor(sourceY)));
            for (int x = 0; x < resizedWidth; x++) {
                double sourceX = (x + 0.5) * image.width() / resizedWidth - 0.5;
                int x0 = clamp((int) Math.floor(sourceX), 0, image.width() - 1);
                int x1 = clamp(x0 + 1, 0, image.width() - 1);
                double wx = Math.max(0.0, Math.min(1.0, sourceX - Math.floor(sourceX)));
                for (int channel = 0; channel < 3; channel++) {
                    double top = pixel(image, x0, y0, channel) * (1 - wx)
                            + pixel(image, x1, y0, channel) * wx;
                    double bottom = pixel(image, x0, y1, channel) * (1 - wx)
                            + pixel(image, x1, y1, channel) * wx;
                    resized[y][x][channel] = top * (1 - wy) + bottom * wy;
                }
            }
        }

        int offsetX = (resizedWidth - CROP) / 2;
        int offsetY = (resizedHeight - CROP) / 2;
        float[] output = new float[VALUES];
        for (int channel = 0; channel < 3; channel++) {
            int channelOffset = channel * CROP * CROP;
            for (int y = 0; y < CROP; y++) {
                for (int x = 0; x < CROP; x++) {
                    double normalized = (resized[y + offsetY][x + offsetX][channel]
                            - MEAN[channel]) / STD[channel];
                    output[channelOffset + y * CROP + x] = (float) normalized;
                }
            }
        }
        return output;
    }

    private static int roundedDimension(int dimension, int shortEdge) {
        long numerator = (long) dimension * RESIZE_SHORTER;
        return (int) ((2 * numerator + shortEdge - 1) / (2L * shortEdge));
    }

    private static double pixel(PpmImage image, int x, int y, int channel) {
        return image.samples()[(y * image.width() + x) * 3 + channel] / (double) image.maxValue();
    }

    private static int clamp(int value, int low, int high) {
        return Math.max(low, Math.min(high, value));
    }
}
