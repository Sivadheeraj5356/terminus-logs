package t5.r4;

import java.util.ArrayList;
import java.util.List;
import m8.q1.TypesB;

/** Carriers for sync and seal. */
public final class TypesC {
  private TypesC() {}

  public static final class HsFrag {
    public final String pid;
    public final int gen;
    public final boolean ok;
    public final String nonce;

    public HsFrag(String pid, int gen, boolean ok, String nonce) {
      this.pid = pid;
      this.gen = gen;
      this.ok = ok;
      this.nonce = nonce;
    }
  }

  public static final class TrustWin {
    public final String pid;
    public final int gen;
    public final String role;
    public final long tag;
    public final boolean revoked;
    public final boolean hsFail;

    public TrustWin(
        String pid, int gen, String role, long tag, boolean revoked, boolean hsFail) {
      this.pid = pid;
      this.gen = gen;
      this.role = role;
      this.tag = tag;
      this.revoked = revoked;
      this.hsFail = hsFail;
    }
  }

  public static final class StageRow {
    public final String packId;
    public final String armId;
    public final byte[] tip;

    public StageRow(String packId, String armId, byte[] tip) {
      this.packId = packId;
      this.armId = armId;
      this.tip = tip;
    }
  }

  public static final class SealRecord {
    public final String hexLane;
    public final int violN;
    public final int sealOk;
    public final byte[] raw;

    public SealRecord(String hexLane, int violN, int sealOk, byte[] raw) {
      this.hexLane = hexLane;
      this.violN = violN;
      this.sealOk = sealOk;
      this.raw = raw;
    }
  }
}
