package drv;

import java.util.List;
import m8.q1.TypesB;
import n3.k2.TypesA;
import t5.r4.SyncC;
import t5.r4.TypesC;
import t5.r4.ZipD;

/** Second-half pipe: sync then seal. */
public final class PipeSeal {
  private PipeSeal() {}

  public static List<TypesC.TrustWin> syncWins(
      TypesA.Connection db, List<TypesB.BoundView> views, List<TypesC.HsFrag> frags) {
    return SyncC.SnapSync(db, views, frags);
  }

  public static TypesC.SealRecord seal(
      List<TypesC.TrustWin> wins, List<TypesC.StageRow> stages) {
    return ZipD.SealZip(wins, stages);
  }
}
