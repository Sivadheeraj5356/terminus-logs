package org.ovg.check;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.ovg.daemon.Run;

/** Checker CLI entry. */
public final class Main {
  public static void main(String[] args) throws Exception {
    boolean full = false;
    String out = "/app/output/invariant_proof_log.json";
    for (int i = 0; i < args.length; i++) {
      if ("--full-matrix".equals(args[i])) {
        full = true;
      } else if ("--out".equals(args[i]) && i + 1 < args.length) {
        out = args[++i];
      }
    }
    if (!full) {
      System.err.println("usage: og_check --full-matrix --out PATH");
      System.exit(2);
    }

    Path root = Path.of("/app/environment");
    String cp = System.getProperty("ovg.cp", "");
    if (cp.isEmpty()) {
      System.err.println("ovg.cp not set");
      System.exit(2);
    }

    String[][] arms =
        new String[][] {
          {"train_a", "kit/blk/tc.mnt"},
          {"train_b", "kit/blk/tc.mnt"},
          {"adv_c", "kit/blk/td.mnt"},
          {"adv_d", "kit/blk/td.mnt"},
        };

    Run run = new Run(root, cp);
    List<Map<String, Object>> instances = new ArrayList<>();

    for (String[] arm : arms) {
      instances.add(run.runArm(arm[0], arm[1], "uninterrupted"));
    }

    ProcessBuilder mig =
        new ProcessBuilder("bash", root.resolve("migrations/mig_ov.sh").toString(), "--restore-anchors");
    mig.directory(root.toFile());
    mig.redirectErrorStream(true);
    Process mp = mig.start();
    String mout = new String(mp.getInputStream().readAllBytes());
    if (mp.waitFor() != 0) {
      System.err.println("recovery failed: " + mout);
      System.exit(1);
    }

    for (String[] arm : arms) {
      instances.add(run.runArm(arm[0], arm[1], "recovered"));
    }

    Map<String, Object> log = new LinkedHashMap<>();
    log.put("schema_id", "ov7");
    log.put("instances", instances);

    Path outPath = Path.of(out);
    Files.createDirectories(outPath.getParent());
    Files.writeString(outPath, toJson(log));

    List<String> errors = new Engine().validate(root, log);
    if (!errors.isEmpty()) {
      System.err.println("check_failed:" + String.join(",", errors));
      System.exit(1);
    }
    System.out.println("check_ok");
  }

  static String toJson(Map<String, Object> log) {
    StringBuilder sb = new StringBuilder();
    sb.append("{\n  \"schema_id\": \"ov7\",\n  \"instances\": [\n");
    @SuppressWarnings("unchecked")
    List<Map<String, Object>> instances = (List<Map<String, Object>>) log.get("instances");
    for (int i = 0; i < instances.size(); i++) {
      Map<String, Object> row = instances.get(i);
      if (i > 0) {
        sb.append(",\n");
      }
      sb.append("    {\n");
      sb.append("      \"arm_id\": \"").append(row.get("arm_id")).append("\",\n");
      sb.append("      \"path_kind\": \"").append(row.get("path_kind")).append("\",\n");
      sb.append("      \"plan_hex\": \"").append(row.get("plan_hex")).append("\",\n");
      sb.append("      \"seq_hex\": \"").append(row.get("seq_hex")).append("\",\n");
      sb.append("      \"guard_trace\": \"").append(row.get("guard_trace")).append("\",\n");
      sb.append("      \"slice_digest\": \"").append(row.get("slice_digest")).append("\",\n");
      sb.append("      \"anchor_digest\": \"").append(row.get("anchor_digest")).append("\",\n");
      sb.append("      \"band_w\": ").append(row.get("band_w")).append(",\n");
      sb.append("      \"band_o\": ").append(row.get("band_o")).append(",\n");
      sb.append("      \"band_n\": ").append(row.get("band_n")).append(",\n");
      sb.append("      \"band_s\": ").append(row.get("band_s")).append("\n");
      sb.append("    }");
    }
    sb.append("\n  ]\n}\n");
    return sb.toString();
  }
}
