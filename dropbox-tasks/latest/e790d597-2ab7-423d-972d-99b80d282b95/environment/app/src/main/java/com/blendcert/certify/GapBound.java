package com.blendcert.certify;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

public final class GapBound {
    private GapBound() {}

    public static double optimalityGapBound(
            JsonObject solutionRow,
            JsonObject shadowPrices,
            JsonArray lots,
            JsonObject spec,
            double volume) {
        return 0.0;
    }

    public static double round6(double value) {
        return Math.round(value * 1_000_000.0) / 1_000_000.0;
    }
}
