package com.foldlab.epoch;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

public final class RotationEpochPlanner {
    private static final Path EPOCH_PATH = Path.of("/app/var/fold_work/rotation_epoch.txt");

    public int nextEpoch() throws IOException {
        int epoch = 1;
        if (Files.exists(EPOCH_PATH)) {
            String raw = Files.readString(EPOCH_PATH).trim();
            epoch = Integer.parseInt(raw) + 1;
        }
        return epoch;
    }

    public void commitEpoch(int epoch) throws IOException {
        Files.createDirectories(EPOCH_PATH.getParent());
        Files.writeString(EPOCH_PATH, Integer.toString(epoch));
    }
}
