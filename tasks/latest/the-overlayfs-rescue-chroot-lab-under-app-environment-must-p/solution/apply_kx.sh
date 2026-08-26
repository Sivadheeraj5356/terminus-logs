#!/bin/bash
set -euo pipefail
python3 <<'PY'
from pathlib import Path
Path('/app/environment/lib_a/src/main/java/org/ovg/layer/KxFold.java').write_text(
    '''package org.ovg.layer;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/** Derives a layer merge plan into the on-disk sink. */
public final class KxFold {
  public LayerTypes.LayerPlan applyFold(LayerTypes.LayerStack stack, MergeSink sink) {
    if (stack == null || sink == null || stack.raw == null || stack.raw.length < 64) {
      throw new IllegalArgumentException("stack");
    }
    int flags = readFlags(stack);
    int mergeCoord = buildMergeCoord(stack, flags);
    byte[] plan = encodePlan(stack, flags, mergeCoord);
    sink.writePlan(plan);
    return new LayerTypes.LayerPlan(plan, flags, stack.idA, stack.idB, stack.idC, mergeCoord);
  }

  private static int readFlags(LayerTypes.LayerStack stack) {
    return stack.flags & 0xff;
  }

  private static int buildMergeCoord(LayerTypes.LayerStack stack, int flags) {
    int mergeCoord = flags;
    if ((flags & 1) != 0) {
      mergeCoord ^= (stack.raw[4] & 0xff) ^ 0xa5;
    }
    if ((flags & 2) != 0) {
      mergeCoord ^= (stack.raw[5] & 0xff) ^ 0x5a;
    }
    return mergeCoord;
  }

  private static byte[] encodePlan(LayerTypes.LayerStack stack, int flags, int mergeCoord) {
    ByteBuffer buf = ByteBuffer.allocate(32).order(ByteOrder.LITTLE_ENDIAN);
    buf.putInt(stack.idA);
    buf.putInt(stack.idB);
    buf.putInt(stack.idC);
    buf.putInt(flags);
    buf.putInt(mergeCoord);
    byte[] anchorPrefix = new byte[12];
    System.arraycopy(stack.raw, 13, anchorPrefix, 0, 12);
    buf.put(anchorPrefix);
    return buf.array();
  }
}
'''
)
PY
