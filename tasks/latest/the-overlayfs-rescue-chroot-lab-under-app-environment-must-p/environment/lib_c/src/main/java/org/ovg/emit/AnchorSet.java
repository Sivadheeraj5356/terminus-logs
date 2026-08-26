package org.ovg.emit;

import java.nio.file.Files;
import java.nio.file.Path;

/** Scratch anchor helper. */
public final class AnchorSet {
  private AnchorSet() {}

  public static byte[] fromSlice(byte[] slice) {
    if (slice == null || slice.length < 29) {
      throw new IllegalArgumentException("slice");
    }
    byte[] a = new byte[16];
    System.arraycopy(slice, 13, a, 0, 16);
    return a;
  }

  public static void preserve(Path scratchDir, byte[] anchor) throws Exception {
    Files.createDirectories(scratchDir);
    Files.write(scratchDir.resolve("anchor.bin"), anchor);
  }

  public static byte[] load(Path scratchDir) throws Exception {
    Path p = scratchDir.resolve("anchor.bin");
    if (!Files.isRegularFile(p)) {
      return new byte[0];
    }
    return Files.readAllBytes(p);
  }
}
