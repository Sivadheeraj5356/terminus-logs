package t5.r4;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;

public final class ZipD {
  private ZipD() {}

  static TypesC.SealRecord zip_d(List<TypesC.TrustWin> wins, List<TypesC.StageRow> stages) {
    try {
      MessageDigest md = MessageDigest.getInstance("SHA-256");
      for (TypesC.StageRow s : stages) {
        if (s.tip != null) {
          md.update(s.tip);
        }
      }
      for (TypesC.TrustWin w : wins) {
        md.update(w.pid.getBytes(StandardCharsets.UTF_8));
      }
      byte[] raw = md.digest();
      StringBuilder hex = new StringBuilder();
      for (byte b : raw) {
        hex.append(String.format("%02x", b));
      }
      return new TypesC.SealRecord(hex.toString(), 0, 1, raw);
    } catch (Exception e) {
      throw new IllegalStateException(e);
    }
  }

  public static TypesC.SealRecord SealZip(List<TypesC.TrustWin> wins, List<TypesC.StageRow> stages) {
    return zip_d(wins, stages);
  }

  static byte[] hashWins(String pack, String arm, List<TypesC.TrustWin> wins) {
    try {
      MessageDigest md = MessageDigest.getInstance("SHA-256");
      md.update(pack.getBytes(StandardCharsets.UTF_8));
      md.update(arm.getBytes(StandardCharsets.UTF_8));
      List<TypesC.TrustWin> sorted = new ArrayList<>(wins);
      sorted.sort((a, b) -> Integer.compare(a.gen, b.gen));
      for (TypesC.TrustWin w : sorted) {
        md.update(w.pid.getBytes(StandardCharsets.UTF_8));
        md.update(intBE(w.gen));
        md.update(w.role.getBytes(StandardCharsets.UTF_8));
        md.update(longLE(w.tag));
      }
      return md.digest();
    } catch (Exception e) {
      throw new IllegalStateException(e);
    }
  }

  private static byte[] intBE(int v) {
    return new byte[] {
      (byte) ((v >> 24) & 0xff),
      (byte) ((v >> 16) & 0xff),
      (byte) ((v >> 8) & 0xff),
      (byte) (v & 0xff)
    };
  }

  private static byte[] longLE(long v) {
    byte[] b = new byte[8];
    for (int i = 0; i < 8; i++) {
      b[i] = (byte) (v & 0xff);
      v >>= 8;
    }
    return b;
  }
}
