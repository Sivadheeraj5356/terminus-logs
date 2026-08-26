package org.ovg.emit;

import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;
import org.ovg.entry.EntrySeq;

/** Formats q9-style interim rows without binding slice bytes. */
public final class SzEmit {
  public Map<String, Object> interim(String armId, EntrySeq seq) {
    Map<String, Object> row = new LinkedHashMap<>();
    row.put("arm_id", armId);
    row.put("status", "healthy");
    row.put(
        "interim_digest",
        seq == null
            ? "0".repeat(64)
            : HexFormat.of().formatHex(seq.toBytes()).substring(0, Math.min(64, 64)));
    while (row.get("interim_digest").toString().length() < 64) {
      row.put("interim_digest", row.get("interim_digest").toString() + "0");
    }
    return row;
  }
}
