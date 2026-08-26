package nxq.scoreboard;
import java.util.*;
public final class Manifest {
  public static String render(String generation, List<Map<String, String>> cases) {
    StringBuilder sb = new StringBuilder();
    sb.append("{\n");
    sb.append("  \"generation\": \"").append(generation).append("\",\n");
    sb.append("  \"hazard_epoch\": \"").append(generation).append("\",\n");
    sb.append("  \"cases\": [\n");
    for (int i = 0; i < cases.size(); i++) {
      Map<String, String> c = cases.get(i);
      sb.append("    {\"case_id\": \"").append(c.get("case_id"))
        .append("\", \"moves_fp\": \"").append(c.get("moves_fp"))
        .append("\", \"generation\": \"").append(c.get("generation"))
        .append("\", \"status\": \"").append(c.get("status"))
        .append("\", \"score\": ").append(c.get("score")).append("}");
      if (i + 1 < cases.size()) sb.append(",");
      sb.append("\n");
    }
    sb.append("  ]\n}\n");
    return sb.toString();
  }
}
