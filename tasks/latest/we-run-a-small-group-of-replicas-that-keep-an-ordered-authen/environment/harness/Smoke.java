package harness;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

public final class Smoke {
    public static void main(String[] args) throws Exception {
        String[] seeds = {
            "seed_steady.txt",
            "seed_handover.txt",
            "seed_minority.txt",
            "seed_outsider.txt",
            "seed_restart.txt",
            "seed_replay.txt",
            "seed_relife.txt",
            "seed_revisit.txt",
            "seed_faulty.txt",
        };
        boolean allOk = true;
        for (String name : seeds) {
            Path path = Path.of("harness", name);
            String mode = "control";
            int n = 5;
            for (String line : Files.readAllLines(path)) {
                List<String> parts = List.of(line.trim().split("\\s+"));
                if (parts.isEmpty()) {
                    continue;
                }
                if (parts.get(0).equals("mode") && parts.size() >= 2) {
                    mode = parts.get(1);
                } else if (parts.get(0).equals("nodes") && parts.size() >= 2) {
                    n = Integer.parseInt(parts.get(1));
                }
            }
            String result = run(mode, n);
            if (result.equals("ok")) {
                System.out.println(name + " OK mode=" + mode + " nodes=" + n);
            } else {
                System.out.println(name + " FAIL mode=" + mode + " nodes=" + n + " " + result);
                allOk = false;
            }
        }
        if (allOk) {
            System.out.println("SMOKE PASS");
        } else {
            System.out.println("SMOKE FAIL");
            System.exit(1);
        }
    }

    private static String run(String mode, int n) {
        SmokeEngine engine = new SmokeEngine(n);
        switch (mode) {
            case "handover":
                return engine.runHandover();
            case "minority":
                return engine.runMinority();
            case "outsider":
                return engine.runOutsider();
            case "restart":
                return engine.runRestart();
            case "replay":
                return engine.runReplay();
            case "relife":
                return engine.runRelife();
            case "revisit":
                return engine.runRevisit();
            case "faulty":
                return engine.runFaulty();
            default:
                return engine.runControl();
        }
    }
}
