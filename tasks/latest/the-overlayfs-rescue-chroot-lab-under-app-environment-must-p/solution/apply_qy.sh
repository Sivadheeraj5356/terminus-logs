#!/bin/bash
set -euo pipefail
python3 <<'PY'
from pathlib import Path
Path('/app/environment/lib_b/src/main/java/org/ovg/entry/QySpan.java').write_text(
    '''package org.ovg.entry;

import org.ovg.layer.LayerTypes;

/** Orders entry steps from a loaded plan view. */
public final class QySpan {
  public EntrySeq applySpan(EntrySlots slots, LayerTypes.LayerPlan plan) {
    if (slots == null || plan == null) {
      throw new IllegalArgumentException("args");
    }
    int[] out = copyBase(slots);
    applyOpacitySwap(out, plan.flags);
    applySiblingSwap(out, plan.flags, plan.idB, plan.idC);
    return new EntrySeq(out);
  }

  private static int[] copyBase(EntrySlots slots) {
    int[] base = slots.base.length >= 3 ? slots.base.clone() : new int[] {0, 1, 2};
    return new int[] {base[0], base[1], base[2]};
  }

  private static void applyOpacitySwap(int[] out, int flags) {
    if ((flags & 2) != 0) {
      int t = out[0];
      out[0] = out[1];
      out[1] = t;
    }
  }

  private static void applySiblingSwap(int[] out, int flags, int idB, int idC) {
    if ((flags & 4) != 0 && idC > idB) {
      int t = out[1];
      out[1] = out[2];
      out[2] = t;
    }
  }
}
'''
)
PY
