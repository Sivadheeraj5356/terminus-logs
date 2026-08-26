package nxq.model;
import nxq.hazards.Chambers;
import nxq.play.Adventure;
import nxq.play.PlayHash;
import java.util.*;
public final class Transcript {
  private Transcript() {}
  public static String json(String caseId, List<String> moves, Adventure adv, Chambers hz) throws Exception {
    List<String> inv = new ArrayList<>(adv.inventory);
    Collections.sort(inv);
    String hash = PlayHash.compute(caseId, moves, adv, hz);
    StringBuilder sb = new StringBuilder();
    sb.append("{\n");
    sb.append("  \"case_id\": \"").append(caseId).append("\",\n");
    sb.append("  \"status\": \"").append(adv.status()).append("\",\n");
    sb.append("  \"score\": ").append(adv.score()).append(",\n");
    sb.append("  \"moves\": ").append(adv.applied).append(",\n");
    sb.append("  \"visited\": ").append(arr(adv.visited)).append(",\n");
    sb.append("  \"inventory\": ").append(arr(inv)).append(",\n");
    sb.append("  \"violations\": ").append(arr(adv.violations)).append(",\n");
    sb.append("  \"trace_hash\": \"").append(hash).append("\",\n");
    sb.append("  \"generation\": \"").append(hz.generation).append("\",\n");
    String start = "atrium";
    String end = adv.room;
    int uniq = new LinkedHashSet<>(adv.visited).size();
    sb.append("  \"path_summary\": {\"start\": \"").append(start)
      .append("\", \"end\": \"").append(end)
      .append("\", \"unique_rooms\": ").append(uniq).append("}\n");
    sb.append("}\n");
    return sb.toString();
  }
  private static String arr(Collection<String> xs) {
    StringBuilder sb = new StringBuilder("[");
    boolean first = true;
    for (String x : xs) {
      if (!first) sb.append(", ");
      first = false;
      sb.append('"').append(x).append('"');
    }
    sb.append(']');
    return sb.toString();
  }
}
