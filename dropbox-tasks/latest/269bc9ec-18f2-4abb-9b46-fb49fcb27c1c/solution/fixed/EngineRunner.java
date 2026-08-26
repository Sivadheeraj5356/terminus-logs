package org.example.parity;

import ai.djl.Model;
import ai.djl.inference.Predictor;
import ai.djl.ndarray.NDArray;
import ai.djl.ndarray.NDList;
import ai.djl.ndarray.NDManager;
import ai.djl.ndarray.types.Shape;
import ai.djl.translate.NoopTranslator;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

final class EngineRunner {
    private static final String MODEL_NAME = "mobilenet_v3_large";

    private EngineRunner() {}

    static Map<Integer, EngineProfile> run(String engine, Path modelDir, List<float[]> tensors,
            List<Integer> batchSizes, int labelCount) throws Exception {
        Map<Integer, EngineProfile> profiles = new LinkedHashMap<>();
        try (Model model = Model.newInstance(MODEL_NAME, engine)) {
            model.load(modelDir, MODEL_NAME);
            try (Predictor<NDList, NDList> predictor = model.newPredictor(new NoopTranslator())) {
                for (int batchSize : batchSizes) {
                    double[][] probabilities = new double[tensors.size()][labelCount];
                    boolean supported = true;
                    for (int start = 0; start < tensors.size(); start += batchSize) {
                        int count = Math.min(batchSize, tensors.size() - start);
                        float[] batch = new float[count * Preprocessor.VALUES];
                        for (int row = 0; row < count; row++) {
                            System.arraycopy(tensors.get(start + row), 0, batch,
                                    row * Preprocessor.VALUES, Preprocessor.VALUES);
                        }
                        try (NDManager manager = model.getNDManager().newSubManager()) {
                            NDArray input = manager.create(batch, new Shape(count, 3,
                                    Preprocessor.CROP, Preprocessor.CROP));
                            try {
                                try (NDList result = predictor.predict(new NDList(input))) {
                                    if (result.size() != 1) {
                                        throw new IllegalArgumentException(engine + " returned multiple tensors");
                                    }
                                    NDArray output = result.get(0);
                                    Shape shape = output.getShape();
                                    if (shape.getShape().length != 2 || shape.get(1) != labelCount) {
                                        throw new IllegalArgumentException(
                                                engine + " returned unexpected logits shape " + shape);
                                    }
                                    if (shape.get(0) != count) {
                                        supported = false;
                                        break;
                                    }
                                    float[] logits = output.toFloatArray();
                                    for (int row = 0; row < count; row++) {
                                        probabilities[start + row] = softmax(
                                                logits, row * labelCount, labelCount);
                                    }
                                }
                            } catch (Exception exception) {
                                if (batchSize == 1) {
                                    throw exception;
                                }
                                supported = false;
                            }
                        }
                        if (!supported) {
                            break;
                        }
                    }
                    if (batchSize == 1 && !supported) {
                        throw new IllegalArgumentException(engine + " does not support batch size one");
                    }
                    profiles.put(batchSize, new EngineProfile(supported,
                            supported ? probabilities : null));
                }
            }
        }
        return profiles;
    }

    private static double[] softmax(float[] logits, int offset, int count) {
        double maximum = Double.NEGATIVE_INFINITY;
        for (int i = 0; i < count; i++) {
            if (!Float.isFinite(logits[offset + i])) {
                throw new IllegalArgumentException("engine returned non-finite logits");
            }
            maximum = Math.max(maximum, logits[offset + i]);
        }
        double[] values = new double[count];
        double sum = 0;
        for (int i = 0; i < count; i++) {
            values[i] = Math.exp(logits[offset + i] - maximum);
            sum += values[i];
        }
        if (!Double.isFinite(sum) || sum <= 0) {
            throw new IllegalArgumentException("invalid softmax denominator");
        }
        for (int i = 0; i < count; i++) {
            values[i] /= sum;
        }
        return values;
    }
}
