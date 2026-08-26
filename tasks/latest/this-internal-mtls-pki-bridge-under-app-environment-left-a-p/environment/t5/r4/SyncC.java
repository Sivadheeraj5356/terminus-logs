package t5.r4;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import m8.q1.TypesB;
import n3.k2.TypesA;

public final class SyncC {
  private SyncC() {}

  static List<TypesC.TrustWin> sync_c(
      TypesA.Connection db, List<TypesB.BoundView> views, List<TypesC.HsFrag> frags) {
    List<TypesC.TrustWin> out = new ArrayList<>();
    for (TypesB.BoundView v : views) {
      out.add(new TypesC.TrustWin(v.pid, v.gen, v.role, v.tag, true, true));
    }
    out.sort(Comparator.comparing((TypesC.TrustWin w) -> w.pid + ":" + w.gen));
    try {
      Path stage = Path.of("/app/output/stage");
      Files.createDirectories(stage);
      StringBuilder tip = new StringBuilder();
      for (TypesC.TrustWin w : out) {
        tip.append(w.pid).append(":").append(w.gen).append("\n");
      }
      Files.writeString(stage.resolve("early.tip"), tip.toString());
    } catch (Exception ignored) {
    }
    return out;
  }

  public static List<TypesC.TrustWin> SnapSync(
      TypesA.Connection db, List<TypesB.BoundView> views, List<TypesC.HsFrag> frags) {
    return sync_c(db, views, frags);
  }

  static boolean lookupRev(TypesA.Connection db, String pid, int gen) {
    for (TypesA.RevRow r : db.revoke) {
      if (r.pid.equals(pid)) {
        return r.revoked != 0;
      }
    }
    return false;
  }
}
