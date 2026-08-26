package org.ovg.layer;

import java.nio.file.Files;
import java.nio.file.Path;

/** Phase driver for fold only. */
public final class FoldMain {
  public static void main(String[] args) throws Exception {
    String slicePath = null;
    String outPath = null;
    for (int i = 0; i < args.length; i++) {
      if ("--slice".equals(args[i]) && i + 1 < args.length) {
        slicePath = args[++i];
      } else if ("--out".equals(args[i]) && i + 1 < args.length) {
        outPath = args[++i];
      }
    }
    if (slicePath == null || outPath == null) {
      System.err.println("usage: FoldMain --slice PATH --out PATH");
      System.exit(2);
    }
    byte[] raw = Files.readAllBytes(Path.of(slicePath));
    if (raw.length < 64) {
      throw new IllegalArgumentException("slice");
    }
    int flags = raw[4] & 0xff;
    int idA = (raw[5] & 0xff) | ((raw[6] & 0xff) << 8);
    int idB = (raw[7] & 0xff) | ((raw[8] & 0xff) << 8);
    int idC = (raw[9] & 0xff) | ((raw[10] & 0xff) << 8);
    int pairGap = (raw[11] & 0xff) | ((raw[12] & 0xff) << 8);
    LayerTypes.LayerStack stack = new LayerTypes.LayerStack(idA, idB, idC, flags, pairGap, raw);
    MemMergeSink sink = new MemMergeSink();
    new KxFold().applyFold(stack, sink);
    sink.writeTo(Path.of(outPath));
  }
}
