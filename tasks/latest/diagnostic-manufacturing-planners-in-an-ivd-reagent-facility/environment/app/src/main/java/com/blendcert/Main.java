package com.blendcert;

import com.blendcert.stage.BindStage;
import com.blendcert.stage.CertifyStage;
import com.blendcert.stage.SealStage;
import com.blendcert.stage.SolveStage;

public final class Main {
    private Main() {}

    public static void main(String[] args) {
        if (args.length < 1) {
            System.err.println("usage: blendcert <bind|solve|certify|seal>");
            System.exit(3);
        }
        String cmd = args[0];
        try {
            int code = switch (cmd) {
                case "bind" -> BindStage.run();
                case "solve" -> SolveStage.run();
                case "certify" -> CertifyStage.run();
                case "seal" -> SealStage.run();
                default -> 3;
            };
            System.exit(code);
        } catch (MissingStateArtifactException e) {
            System.exit(2);
        } catch (BadInputException e) {
            System.exit(3);
        } catch (Exception e) {
            System.err.println(e.getMessage());
            System.exit(3);
        }
    }
}
