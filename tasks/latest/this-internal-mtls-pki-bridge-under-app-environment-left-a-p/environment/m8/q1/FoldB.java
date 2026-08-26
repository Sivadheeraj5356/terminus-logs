package m8.q1;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import n3.k2.TypesA;

public final class FoldB {
  private FoldB() {}

  static List<TypesB.BoundView> fold_b(
      List<TypesA.EpochCand> cands, List<TypesB.PemBlob> mats, List<TypesB.AnchorGen> anchors) {
    List<TypesB.BoundView> out = new ArrayList<>();
    for (TypesA.EpochCand c : cands) {
      out.add(new TypesB.BoundView(c.pid, c.gen, c.scp, c.role, "", c.tag));
    }
    out.sort(Comparator.comparing((TypesB.BoundView v) -> v.pid + ":" + v.gen));
    return out;
  }

  public static List<TypesB.BoundView> BindFold(
      List<TypesA.EpochCand> cands, List<TypesB.PemBlob> mats, List<TypesB.AnchorGen> anchors) {
    return fold_b(cands, mats, anchors);
  }
}
