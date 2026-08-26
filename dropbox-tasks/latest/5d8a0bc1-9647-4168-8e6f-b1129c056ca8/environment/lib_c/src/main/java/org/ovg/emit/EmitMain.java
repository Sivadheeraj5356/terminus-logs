package org.ovg.emit;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import org.ovg.entry.EntrySeq;

/** Phase driver for emit only. */
public final class EmitMain {
  public static void main(String[] args) throws Exception {
    String slicePath = null;
    String planPath = null;
    String seqPath = null;
    String outPath = null;
    String armId = "arm";
    String pathKind = "uninterrupted";
    for (int i = 0; i < args.length; i++) {
      if ("--slice".equals(args[i]) && i + 1 < args.length) {
        slicePath = args[++i];
      } else if ("--plan".equals(args[i]) && i + 1 < args.length) {
        planPath = args[++i];
      } else if ("--seq".equals(args[i]) && i + 1 < args.length) {
        seqPath = args[++i];
      } else if ("--out".equals(args[i]) && i + 1 < args.length) {
        outPath = args[++i];
      } else if ("--arm".equals(args[i]) && i + 1 < args.length) {
        armId = args[++i];
      } else if ("--path-kind".equals(args[i]) && i + 1 < args.length) {
        pathKind = args[++i];
      }
    }
    if (slicePath == null || planPath == null || seqPath == null || outPath == null) {
      System.err.println(
          "usage: EmitMain --slice P --plan P --seq P --out P [--arm ID] [--path-kind K]");
      System.exit(2);
    }
    byte[] slice = Files.readAllBytes(Path.of(slicePath));
    byte[] plan = Files.readAllBytes(Path.of(planPath));
    EntrySeq seq = EntrySeq.fromBytes(Files.readAllBytes(Path.of(seqPath)));
    ProofSink sink = new ProofSink();
    sink.setPlan(plan);
    sink.setMeta(armId, pathKind);
    new RzEmit().applyEmit(sink, slice, seq);
    Map<String, Object> row = sink.snapshot().get("row");
    StringBuilder sb = new StringBuilder();
    sb.append("arm_id=").append(armId).append('\n');
    sb.append("path_kind=").append(pathKind).append('\n');
    for (String k :
        new String[] {
          "plan_hex",
          "seq_hex",
          "guard_trace",
          "slice_digest",
          "anchor_digest",
          "band_w",
          "band_o",
          "band_n",
          "band_s"
        }) {
      sb.append(k).append('=').append(row.get(k)).append('\n');
    }
    Files.createDirectories(Path.of(outPath).getParent());
    Files.writeString(Path.of(outPath), sb.toString());
  }
}
