package org.ovg.entry;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/** Ordered entry steps. */
public final class EntrySeq {
  public final int[] slots;

  public EntrySeq(int[] slots) {
    this.slots = slots == null ? new int[0] : slots.clone();
  }

  public byte[] toBytes() {
    ByteBuffer buf = ByteBuffer.allocate(2 + slots.length * 2).order(ByteOrder.LITTLE_ENDIAN);
    buf.putShort((short) slots.length);
    for (int s : slots) {
      buf.putShort((short) s);
    }
    return buf.array();
  }

  public static EntrySeq fromBytes(byte[] raw) {
    ByteBuffer buf = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN);
    int n = buf.getShort() & 0xffff;
    int[] slots = new int[n];
    for (int i = 0; i < n; i++) {
      slots[i] = buf.getShort() & 0xffff;
    }
    return new EntrySeq(slots);
  }
}
