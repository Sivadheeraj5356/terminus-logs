package org.ovg.daemon;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Overlay/chroot phase driver via separate phase mains. */
public final class Run {
  private final Path root;
  private final String cp;

  public Run(Path root, String cp) {
    this.root = root;
    this.cp = cp;
  }

  public Map<String, Object> runArm(String armId, String sliceRel, String pathKind)
      throws Exception {
    Path work = root.resolve("kit/scratch/work").resolve(armId + "-" + pathKind);
    Files.createDirectories(work);
    Path slice = root.resolve(sliceRel);
    Path plan = work.resolve("plan.bin");
    Path seq = work.resolve("seq.bin");
    Path row = work.resolve("row.txt");

    exec("org.ovg.layer.FoldMain", "--slice", slice.toString(), "--out", plan.toString());
    exec("org.ovg.entry.SpanMain", "--plan", plan.toString(), "--out", seq.toString());
    exec(
        "org.ovg.emit.EmitMain",
        "--slice",
        slice.toString(),
        "--plan",
        plan.toString(),
        "--seq",
        seq.toString(),
        "--out",
        row.toString(),
        "--arm",
        armId,
        "--path-kind",
        pathKind);

    Map<String, Object> parsed = parseRow(Files.readString(row));
    parsed.put("arm_id", armId);
    parsed.put("path_kind", pathKind);
    return parsed;
  }

  private void exec(String mainClass, String... argv) throws Exception {
    List<String> cmd = new ArrayList<>();
    cmd.add("java");
    cmd.add("-cp");
    cmd.add(cp);
    cmd.add(mainClass);
    for (String a : argv) {
      cmd.add(a);
    }
    ProcessBuilder pb = new ProcessBuilder(cmd);
    pb.directory(root.toFile());
    pb.redirectErrorStream(true);
    Process p = pb.start();
    String out = new String(p.getInputStream().readAllBytes());
    int rc = p.waitFor();
    if (rc != 0) {
      throw new IllegalStateException(mainClass + " failed: " + out);
    }
  }

  private static Map<String, Object> parseRow(String text) {
    Map<String, Object> m = new LinkedHashMap<>();
    for (String line : text.split("\n")) {
      int eq = line.indexOf('=');
      if (eq <= 0) {
        continue;
      }
      String k = line.substring(0, eq).trim();
      String v = line.substring(eq + 1).trim();
      if (k.startsWith("band_")) {
        m.put(k, Integer.parseInt(v));
      } else {
        m.put(k, v);
      }
    }
    return m;
  }
}
