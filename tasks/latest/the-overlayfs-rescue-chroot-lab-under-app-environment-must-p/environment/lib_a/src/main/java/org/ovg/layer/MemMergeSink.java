package org.ovg.layer;

import java.nio.file.Files;
import java.nio.file.Path;

/** In-memory merge sink used by FoldMain. */
public final class MemMergeSink implements MergeSink {
  private byte[] plan = new byte[0];

  @Override
  public void writePlan(byte[] planBytes) {
    this.plan = planBytes == null ? new byte[0] : planBytes.clone();
  }

  @Override
  public byte[] readPlan() {
    return plan.clone();
  }

  public void writeTo(Path path) throws Exception {
    Files.createDirectories(path.getParent());
    Files.write(path, plan);
  }
}
