package org.ovg.entry;

/** No-op entry refresh for builds without sequencing. */
public final class PySpan {
  public EntrySeq refresh(EntrySlots slots) {
    if (slots == null) {
      return new EntrySeq(new int[] {0, 1, 2});
    }
    return new EntrySeq(slots.base);
  }
}
