package n3.k2;

import java.util.ArrayList;
import java.util.List;

/** Offline issuance printer; never imported by the x7 driver path. */
public final class LaneShadow {
  private LaneShadow() {}

  public static List<String> DumpRows(TypesA.Connection db) {
    List<String> lines = new ArrayList<>();
    for (TypesA.IssueRow r : db.issue) {
      lines.add(r.pid + ":" + r.gen + ":" + r.ts + ":" + r.role);
    }
    return lines;
  }
}
