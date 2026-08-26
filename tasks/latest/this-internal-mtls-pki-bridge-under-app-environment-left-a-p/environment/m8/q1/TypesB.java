package m8.q1;

import java.util.ArrayList;
import java.util.List;
import n3.k2.TypesA;

/** Carriers for material bind. */
public final class TypesB {
  private TypesB() {}

  public static final class PemBlob {
    public final int gen;
    public final String pid;
    public final String fp;
    public final String role;

    public PemBlob(int gen, String pid, String fp, String role) {
      this.gen = gen;
      this.pid = pid;
      this.fp = fp;
      this.role = role;
    }
  }

  public static final class AnchorGen {
    public final int gen;
    public final String label;

    public AnchorGen(int gen, String label) {
      this.gen = gen;
      this.label = label;
    }
  }

  public static final class BoundView {
    public final String pid;
    public final int gen;
    public final String scp;
    public final String role;
    public final String fp;
    public final long tag;

    public BoundView(String pid, int gen, String scp, String role, String fp, long tag) {
      this.pid = pid;
      this.gen = gen;
      this.scp = scp;
      this.role = role;
      this.fp = fp;
      this.tag = tag;
    }
  }
}
