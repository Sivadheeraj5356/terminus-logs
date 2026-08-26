package com.foldlab.stage;

import java.io.IOException;
import java.nio.file.Path;
import java.util.List;

public final class CohortStager {
    private static final Path STAGE_SCRIPT = Path.of("/app/scripts/stage_cohort.sh");
    private static final Path WORK_DIR = Path.of("/app/var/fold_work");
    private static final Path STAGED_FILE = WORK_DIR.resolve("cohort_staged.csv");

    public Path stage(Path dataset, String labelColumn) throws IOException, InterruptedException {
        ProcessBuilder builder = new ProcessBuilder(
                "bash",
                STAGE_SCRIPT.toString(),
                dataset.toString(),
                WORK_DIR.toString(),
                labelColumn);
        builder.redirectErrorStream(true);
        Process process = builder.start();
        int code = process.waitFor();
        if (code != 0) {
            throw new IOException("stage_cohort.sh failed with exit code " + code);
        }
        return STAGED_FILE.toAbsolutePath().normalize();
    }
}
