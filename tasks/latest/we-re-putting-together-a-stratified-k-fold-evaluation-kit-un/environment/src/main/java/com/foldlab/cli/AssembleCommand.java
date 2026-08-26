package com.foldlab.cli;

import java.nio.file.Path;

public final class AssembleCommand {
    private final Path dataset;
    private final int foldCount;
    private final String labelColumn;

    private AssembleCommand(Path dataset, int foldCount, String labelColumn) {
        this.dataset = dataset;
        this.foldCount = foldCount;
        this.labelColumn = labelColumn;
    }

    public static AssembleCommand parse(String[] args) {
        throw new UnsupportedOperationException("AssembleCommand.parse not implemented");
    }

    public void run() throws Exception {
        throw new UnsupportedOperationException("AssembleCommand.run not implemented");
    }
}
