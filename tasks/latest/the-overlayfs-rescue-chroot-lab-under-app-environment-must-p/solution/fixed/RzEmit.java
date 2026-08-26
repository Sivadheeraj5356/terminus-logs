package org.ovg.emit;

import java.nio.file.Path;
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
      byte[] plan = requirePlan(sink);
      byte[] anchor = AnchorSet.fromSlice(slice);
      AnchorSet.preserve(Path.of("/app/environment/kit/scratch"), anchor);
      byte[] seqBytes = seq.toBytes();
      Map<String, Object> row = buildRow(slice, plan, seqBytes, anchor);
      sink.put("row", row);
    } catch (Exception e) {
      throw new IllegalStateException(e);
    }
  }

  private static byte[] requirePlan(ProofSink sink) {
    byte[] plan = sink.getPlan();
    if (plan.length < 20) {
      throw new IllegalArgumentException("plan");
    }
    return plan;
  }

  private static Map<String, Object> buildRow(byte[] slice, byte[] plan, byte[] seqBytes, byte[] anchor)
      throws Exception {
    int flags = slice[4] & 0xff;
    int idB = (slice[7] & 0xff) | ((slice[8] & 0xff) << 8);
    int idC = (slice[9] & 0xff) | ((slice[10] & 0xff) << 8);
    int pairGap = (slice[11] & 0xff) | ((slice[12] & 0xff) << 8);
    int mergeCoord = readMergeCoord(plan);
    int firstSlot = readFirstSlot(seqBytes);
    Map<String, Object> row = new LinkedHashMap<>();
    row.put("plan_hex", HexFormat.of().formatHex(plan));
    row.put("seq_hex", HexFormat.of().formatHex(seqBytes));
    row.put("guard_trace", shaHex(concat(slice, plan, seqBytes, anchor)));
    row.put("slice_digest", shaHex(slice));
    row.put("anchor_digest", shaHex(anchor));
    row.put("band_w", ((flags & 1) != 0 ? 17 : 0) + (mergeCoord & 0xff) % 13);
    row.put("band_o", ((flags & 2) != 0 ? 19 : 0) + firstSlot);
    row.put("band_n", ((flags & 4) != 0 ? 23 : 0) + pairGap);
    row.put("band_s", ((flags & 4) != 0) ? ((idB ^ idC) & 0xffff) : 0);
    return row;
  }

  private static int readMergeCoord(byte[] plan) {
    return (plan[16] & 0xff)
        | ((plan[17] & 0xff) << 8)
        | ((plan[18] & 0xff) << 16)
        | ((plan[19] & 0xff) << 24);
  }

  private static int readFirstSlot(byte[] seqBytes) {
    if (seqBytes.length >= 4) {
      return (seqBytes[2] & 0xff) | ((seqBytes[3] & 0xff) << 8);
    }
    return 0;
  }

  static String shaHex(byte[] data) throws Exception {
    MessageDigest md = MessageDigest.getInstance("SHA-256");
    return HexFormat.of().formatHex(md.digest(data));
  }

  static byte[] concat(byte[]... parts) {
    int n = 0;
    for (byte[] p : parts) {
      n += p.length;
    }
    byte[] out = new byte[n];
    int o = 0;
    for (byte[] p : parts) {
      System.arraycopy(p, 0, out, o, p.length);
      o += p.length;
    }
    return out;
  }
}
