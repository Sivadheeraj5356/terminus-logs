package org.ovg.layer;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/** Derives a layer merge plan into the on-disk sink. */
public final class KxFold {
  public LayerTypes.LayerPlan applyFold(LayerTypes.LayerStack stack, MergeSink sink) {
    if (stack == null || sink == null || stack.raw == null || stack.raw.length < 64) {
      throw new IllegalArgumentException("stack");
    }
    int flags = 0;
    int mergeCoord = stack.idA & 0xff;
    ByteBuffer buf = ByteBuffer.allocate(32).order(ByteOrder.LITTLE_ENDIAN);
    buf.putInt(stack.idA);
    buf.putInt(stack.idB);
    buf.putInt(stack.idC);
    buf.putInt(flags);
    buf.putInt(mergeCoord);
    byte[] anchorPrefix = new byte[12];
    System.arraycopy(stack.raw, 13, anchorPrefix, 0, 12);
    buf.put(anchorPrefix);
    byte[] plan = buf.array();
    sink.writePlan(plan);
    return new LayerTypes.LayerPlan(plan, flags, stack.idA, stack.idB, stack.idC, mergeCoord);
  }
}
