package org.ovg.entry;

import org.ovg.layer.LayerTypes;

/** Orders entry steps from a loaded plan view. */
public final class QySpan {
  public EntrySeq applySpan(EntrySlots slots, LayerTypes.LayerPlan plan) {
    if (slots == null || plan == null) {
      throw new IllegalArgumentException("args");
    }
    int[] base = slots.base.length >= 3 ? slots.base : new int[] {0, 1, 2};
    return new EntrySeq(new int[] {base[0], base[1], base[2]});
  }
}
