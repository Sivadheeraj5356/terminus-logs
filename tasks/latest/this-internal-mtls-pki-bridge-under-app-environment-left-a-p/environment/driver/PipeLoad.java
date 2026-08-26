package drv;

import java.util.List;
import m8.q1.FoldB;
import m8.q1.TypesB;
import n3.k2.LaneA;
import n3.k2.TypesA;

/** First-half pipe: lane fold then material bind. */
public final class PipeLoad {
  private PipeLoad() {}

  public static List<TypesA.EpochCand> foldLane(TypesA.Connection db, List<TypesA.GenKey> gens) {
    return LaneA.PackLane(db, gens);
  }

  public static List<TypesB.BoundView> bindMats(
      List<TypesA.EpochCand> cands, List<TypesB.PemBlob> mats, List<TypesB.AnchorGen> anchors) {
    return FoldB.BindFold(cands, mats, anchors);
  }
}
