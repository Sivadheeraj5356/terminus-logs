package org.ovg.layer;

/** Stack view loaded from a mount slice. */
public final class LayerTypes {
  public static final class LayerStack {
    public final int idA;
    public final int idB;
    public final int idC;
    public final int flags;
    public final int pairGap;
    public final byte[] raw;

    public LayerStack(int idA, int idB, int idC, int flags, int pairGap, byte[] raw) {
      this.idA = idA;
      this.idB = idB;
      this.idC = idC;
      this.flags = flags;
      this.pairGap = pairGap;
      this.raw = raw;
    }
  }

  public static final class LayerPlan {
    public final byte[] planBytes;
    public final int flags;
    public final int idA;
    public final int idB;
    public final int idC;
    public final int mergeCoord;

    public LayerPlan(byte[] planBytes, int flags, int idA, int idB, int idC, int mergeCoord) {
      this.planBytes = planBytes;
      this.flags = flags;
      this.idA = idA;
      this.idB = idB;
      this.idC = idC;
      this.mergeCoord = mergeCoord;
    }
  }

  private LayerTypes() {}
}
