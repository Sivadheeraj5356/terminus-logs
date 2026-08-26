package com.foldlab;

import com.foldlab.cli.AssembleCommand;

public final class FoldLabApp {
    public static void main(String[] args) {
        if (args.length == 0 || !"assemble".equals(args[0])) {
            System.err.println("usage: foldctl assemble --dataset PATH --folds K --label COLUMN");
            System.exit(1);
        }
        try {
            AssembleCommand command = AssembleCommand.parse(args);
            command.run();
        } catch (Exception ex) {
            System.err.println(ex.getMessage());
            System.exit(1);
        }
    }

    private FoldLabApp() {}
}
