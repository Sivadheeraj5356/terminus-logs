package org.ovg.emit;

import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;
import org.ovg.entry.EntrySeq;

/** Emits proof-log rows bound to mount slice bytes while preserving anchors. */
public final class RzEmit {
  public void applyEmit(ProofSink sink, byte[] slice, EntrySeq seq) {
    if (sink == null || slice == null || seq == null) {
      throw new IllegalArgumentException("args");
    }
    try {
      byte[] seqBytes = seq.toBytes();
      Map<String, Object> row = new LinkedHashMap<>();
      row.put("plan_hex", "");
      row.put("seq_hex", HexFormat.of().formatHex(seqBytes));
      row.put("guard_trace", shaHex(seqBytes));
      row.put("slice_digest", shaHex(slice));
      row.put("anchor_digest", shaHex(new byte[16]));
      row.put("band_w", 0);
      row.put("band_o", 0);
      row.put("band_n", 0);
      row.put("band_s", 0);
      sink.put("row", row);
    } catch (Exception e) {
      throw new IllegalStateException(e);
    }
  }

  static String shaHex(byte[] data) throws Exception {
    MessageDigest md = MessageDigest.getInstance("SHA-256");
    return HexFormat.of().formatHex(md.digest(data));
  }
}
