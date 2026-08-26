package org.ovg.layer;

/** Sink that stores the derived plan bytes for later phases. */
public interface MergeSink {
  void writePlan(byte[] planBytes);

  byte[] readPlan();
}
