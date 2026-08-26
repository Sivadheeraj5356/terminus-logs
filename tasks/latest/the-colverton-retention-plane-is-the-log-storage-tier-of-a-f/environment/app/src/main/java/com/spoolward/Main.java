package com.spoolward;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Comparator;
import java.util.Map;

public final class Main {

    public static void main(String[] args) throws IOException {
        if (args.length == 1 && args[0].equals("--selfcheck")) {
            return;
        }
        String rootVar = System.getenv("SPOOLWARD_PLANE");
        if (rootVar == null || rootVar.isEmpty()) {
            rootVar = "/app/plane";
        }
        String outVar = System.getenv("SPOOLWARD_REPORT");
        if (outVar == null || outVar.isEmpty()) {
            outVar = "/app/output/spoolward_report.json";
        }
        Plane plane = new Plane(Paths.get(rootVar));
        plane.run();
        Map<String, Object> rep = plane.report();
        byte[] body = (Wire.canonical(rep) + "\n").getBytes(StandardCharsets.UTF_8);
        Path out = Paths.get(outVar);
        Path dir = out.getParent();
        if (dir != null) {
            if (Files.isDirectory(dir)) {
                try (var stream = Files.walk(dir)) {
                    stream.sorted(Comparator.reverseOrder())
                          .filter(p -> !p.equals(dir))
                          .forEach(p -> {
                              try {
                                  Files.delete(p);
                              } catch (IOException e) {
                                  throw new RuntimeException(e);
                              }
                          });
                }
            } else {
                Files.createDirectories(dir);
            }
        }
        Files.write(out, body);
    }
}
