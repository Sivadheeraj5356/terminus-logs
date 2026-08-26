package org.ovg.check;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Digest and band validation against pact OV7. */
public final class Engine {
  public List<String> validate(Path root, Map<String, Object> log) throws Exception {
    List<String> errors = new ArrayList<>();
    if (!"ov7".equals(String.valueOf(log.get("schema_id")))) {
      errors.add("schema_id");
    }
    @SuppressWarnings("unchecked")
    List<Map<String, Object>> instances = (List<Map<String, Object>>) log.get("instances");
    if (instances == null || instances.size() < 8) {
      errors.add("instances_count");
      return errors;
    }

    Map<String, String> guards = new LinkedHashMap<>();
    for (Map<String, Object> row : instances) {
      String arm = String.valueOf(row.get("arm_id"));
      String kind = String.valueOf(row.get("path_kind"));
      Path slicePath = sliceFor(root, arm);
      byte[] slice = Files.readAllBytes(slicePath);
      byte[] plan = HexFormat.of().parseHex(String.valueOf(row.get("plan_hex")));
      byte[] seq = HexFormat.of().parseHex(String.valueOf(row.get("seq_hex")));
      byte[] anchor = new byte[16];
      System.arraycopy(slice, 13, anchor, 0, 16);

      String wantSlice = shaHex(slice);
      String wantAnchor = shaHex(anchor);
      String wantGuard = shaHex(concat(slice, plan, seq, anchor));
      if (!wantSlice.equals(row.get("slice_digest"))) {
        errors.add(arm + "/" + kind + ":slice_digest");
      }
      if (!wantAnchor.equals(row.get("anchor_digest"))) {
        errors.add(arm + "/" + kind + ":anchor_digest");
      }
      if (!wantGuard.equals(row.get("guard_trace"))) {
        errors.add(arm + "/" + kind + ":guard_trace");
      }

      ExpectedPlan ep = expectedPlan(slice);
      if (plan.length != 32 || !java.util.Arrays.equals(plan, ep.bytes)) {
        errors.add(arm + "/" + kind + ":plan");
      }
      byte[] wantSeq = expectedSeq(slice, ep);
      if (!java.util.Arrays.equals(seq, wantSeq)) {
        errors.add(arm + "/" + kind + ":seq");
      }

      int bandW = asInt(row.get("band_w"));
      int bandO = asInt(row.get("band_o"));
      int bandN = asInt(row.get("band_n"));
      int bandS = asInt(row.get("band_s"));
      if (bandW != ep.bandW || bandO != ep.bandO || bandN != ep.bandN || bandS != ep.bandS) {
        errors.add(arm + "/" + kind + ":bands");
      }

      String gkey = arm;
      if ("uninterrupted".equals(kind)) {
        guards.put(gkey, String.valueOf(row.get("guard_trace")));
      } else if ("recovered".equals(kind)) {
        String prior = guards.get(gkey);
        if (prior == null || !prior.equals(String.valueOf(row.get("guard_trace")))) {
          errors.add(arm + ":guard_mismatch");
        }
      }
    }

    Path anchor = root.resolve("kit/scratch/anchor.bin");
    if (!Files.isRegularFile(anchor) || Files.size(anchor) != 16) {
      errors.add("anchor_missing");
    }
    return errors;
  }

  static Path sliceFor(Path root, String arm) {
    if ("train_a".equals(arm) || "train_b".equals(arm)) {
      return root.resolve("kit/blk/tc.mnt");
    }
    return root.resolve("kit/blk/td.mnt");
  }

  static final class ExpectedPlan {
    final byte[] bytes;
    final int flags;
    final int idA;
    final int idB;
    final int idC;
    final int mergeCoord;
    final int bandW;
    final int bandO;
    final int bandN;
    final int bandS;
    final int firstSlot;

    ExpectedPlan(
        byte[] bytes,
        int flags,
        int idA,
        int idB,
        int idC,
        int mergeCoord,
        int bandW,
        int bandO,
        int bandN,
        int bandS,
        int firstSlot) {
      this.bytes = bytes;
      this.flags = flags;
      this.idA = idA;
      this.idB = idB;
      this.idC = idC;
      this.mergeCoord = mergeCoord;
      this.bandW = bandW;
      this.bandO = bandO;
      this.bandN = bandN;
      this.bandS = bandS;
      this.firstSlot = firstSlot;
    }
  }

  static ExpectedPlan expectedPlan(byte[] slice) {
    int flags = slice[4] & 0xff;
    int idA = u16(slice, 5);
    int idB = u16(slice, 7);
    int idC = u16(slice, 9);
    int pairGap = u16(slice, 11);
    int mergeCoord = flags & 0xff;
    if ((flags & 1) != 0) {
      mergeCoord ^= (slice[4] & 0xff) ^ 0xa5;
    }
    if ((flags & 2) != 0) {
      mergeCoord ^= (slice[5] & 0xff) ^ 0x5a;
    }
    ByteBuffer buf = ByteBuffer.allocate(32).order(ByteOrder.LITTLE_ENDIAN);
    buf.putInt(idA);
    buf.putInt(idB);
    buf.putInt(idC);
    buf.putInt(flags);
    buf.putInt(mergeCoord);
    buf.put(slice, 13, 12);
    byte[] plan = buf.array();

    int[] slots = expectedSlots(flags, idB, idC);
    int first = slots[0];
    int bandW = ((flags & 1) != 0 ? 17 : 0) + (mergeCoord & 0xff) % 13;
    int bandO = ((flags & 2) != 0 ? 19 : 0) + first;
    int bandN = ((flags & 4) != 0 ? 23 : 0) + pairGap;
    int bandS = ((flags & 4) != 0) ? ((idB ^ idC) & 0xffff) : 0;
    return new ExpectedPlan(
        plan, flags, idA, idB, idC, mergeCoord, bandW, bandO, bandN, bandS, first);
  }

  static byte[] expectedSeq(byte[] slice, ExpectedPlan ep) {
    int[] slots = expectedSlots(ep.flags, ep.idB, ep.idC);
    ByteBuffer buf = ByteBuffer.allocate(2 + slots.length * 2).order(ByteOrder.LITTLE_ENDIAN);
    buf.putShort((short) slots.length);
    for (int s : slots) {
      buf.putShort((short) s);
    }
    return buf.array();
  }

  static int[] expectedSlots(int flags, int idB, int idC) {
    int[] slots = new int[] {0, 1, 2};
    if ((flags & 2) != 0) {
      int t = slots[0];
      slots[0] = slots[1];
      slots[1] = t;
    }
    if ((flags & 4) != 0 && idC > idB) {
      int t = slots[1];
      slots[1] = slots[2];
      slots[2] = t;
    }
    return slots;
  }

  static int u16(byte[] b, int off) {
    return (b[off] & 0xff) | ((b[off + 1] & 0xff) << 8);
  }

  static int asInt(Object o) {
    if (o instanceof Number) {
      return ((Number) o).intValue();
    }
    return Integer.parseInt(String.valueOf(o));
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

  static String shaHex(byte[] data) throws Exception {
    MessageDigest md = MessageDigest.getInstance("SHA-256");
    return HexFormat.of().formatHex(md.digest(data));
  }
}
