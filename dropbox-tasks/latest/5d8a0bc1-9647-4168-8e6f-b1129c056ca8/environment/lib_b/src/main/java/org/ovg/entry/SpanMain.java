package org.ovg.entry;

import java.nio.file.Files;
import java.nio.file.Path;
import org.ovg.layer.LayerTypes;

/** Phase driver for span only. */
public final class SpanMain {
  public static void main(String[] args) throws Exception {
    String planPath = null;
    String outPath = null;
    for (int i = 0; i < args.length; i++) {
      if ("--plan".equals(args[i]) && i + 1 < args.length) {
        planPath = args[++i];
      } else if ("--out".equals(args[i]) && i + 1 < args.length) {
        outPath = args[++i];
      }
    }
    if (planPath == null || outPath == null) {
      System.err.println("usage: SpanMain --plan PATH --out PATH");
      System.exit(2);
    }
    byte[] planBytes = Files.readAllBytes(Path.of(planPath));
    if (planBytes.length < 20) {
      throw new IllegalArgumentException("plan");
    }
    int idA = le32(planBytes, 0);
    int idB = le32(planBytes, 4);
    int idC = le32(planBytes, 8);
    int flags = le32(planBytes, 12);
    int mergeCoord = le32(planBytes, 16);
    LayerTypes.LayerPlan plan =
        new LayerTypes.LayerPlan(planBytes, flags, idA, idB, idC, mergeCoord);
    EntrySeq seq = new QySpan().applySpan(new EntrySlots(new int[] {0, 1, 2}), plan);
    Files.createDirectories(Path.of(outPath).getParent());
    Files.write(Path.of(outPath), seq.toBytes());
  }

  private static int le32(byte[] b, int off) {
    return (b[off] & 0xff)
        | ((b[off + 1] & 0xff) << 8)
        | ((b[off + 2] & 0xff) << 16)
        | ((b[off + 3] & 0xff) << 24);
  }
}
