package nxq.graph;
import java.util.*;
public final class Rooms {
  private static final Map<String, List<String>> E = new LinkedHashMap<>();
  static {
    E.put("atrium", List.of("buffer"));
    E.put("buffer", List.of("heap"));
    E.put("heap", List.of("canary", "leak"));
    E.put("canary", List.of("vault"));
    E.put("leak", List.of("mirror"));
    E.put("mirror", List.of("buffer"));
    E.put("vault", List.of());
  }
  private Rooms() {}
  public static boolean edge(String from, String to) {
    return E.getOrDefault(from, List.of()).contains(to);
  }
}
