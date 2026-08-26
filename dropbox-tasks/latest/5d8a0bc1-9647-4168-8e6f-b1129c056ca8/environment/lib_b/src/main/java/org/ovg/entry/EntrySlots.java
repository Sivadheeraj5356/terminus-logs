package org.ovg.entry;

/** Entry slot bag and sequence carriers. */
public final class EntrySlots {
  public final int[] base;

  public EntrySlots(int[] base) {
    this.base = base == null ? new int[] {0, 1, 2} : base.clone();
  }
}
