package n3.k2;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class LaneA {
  private LaneA() {}

  static List<TypesA.EpochCand> lane_a(TypesA.Connection db, List<TypesA.GenKey> gens) {
    List<TypesA.IssueRow> rows = new ArrayList<>(db.issue);
    rows.sort(Comparator.comparingInt((TypesA.IssueRow r) -> r.ts));
    Map<String, TypesA.IssueRow> byPid = new HashMap<>();
    for (TypesA.IssueRow r : rows) {
      byPid.putIfAbsent(r.pid, r);
    }
    List<TypesA.EpochCand> out = new ArrayList<>();
    for (TypesA.IssueRow r : byPid.values()) {
      long tag = tagOf(r.pid, r.scp, r.role, 0);
      out.add(new TypesA.EpochCand(r.pid, 0, r.scp, r.role, tag));
    }
    out.sort(Comparator.comparing((TypesA.EpochCand c) -> c.pid));
    return out;
  }

  public static List<TypesA.EpochCand> PackLane(TypesA.Connection db, List<TypesA.GenKey> gens) {
    return lane_a(db, gens);
  }

  public static long tagOf(String pid, String scp, String role, int gen) {
    try {
      String s = pid + "|" + scp + "|" + role + "|" + gen;
      MessageDigest md = MessageDigest.getInstance("SHA-256");
      byte[] dig = md.digest(s.getBytes(StandardCharsets.UTF_8));
      long v = 0;
      for (int i = 0; i < 8; i++) {
        v = (v << 8) | (dig[i] & 0xffL);
      }
      return v;
    } catch (Exception e) {
      throw new IllegalStateException(e);
    }
  }
}
