package com.foldlab.eval;

public final class HoldoutMirror {
    public int holdoutFoldId(int rotationEpoch, int foldCount) {
        if (foldCount < 1) {
            throw new IllegalArgumentException("foldCount must be >= 1");
        }
        return Math.floorMod(rotationEpoch - 1, foldCount);
    }
}
