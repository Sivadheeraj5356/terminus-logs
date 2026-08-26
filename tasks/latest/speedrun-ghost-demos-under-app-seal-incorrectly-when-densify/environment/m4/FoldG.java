package m4;

import common.Io;
import java.nio.file.*;
import java.util.*;

public final class FoldG {
  static final class PackRow {
    String instanceId;
    String laneId;
    String laneHex;
    double floorRatio;
  }

  private FoldG() {}

  public static List<PackRow> foldG(Path regimePath, Path floorPath) throws Exception {
    double floor = FoldAux.minDensifyFloor(floorPath);
    List<PackRow> rows = new ArrayList<>();
        Path man = regimePath.resolve("manifest.tsv");
    for (String line : Io.read(man).split("\n")) {
      if (line.startsWith("id") || line.isBlank()) continue;
      String[] parts = line.split("\t");
      String body = Io.read(regimePath.resolve(parts[1]));
      String iid = Io.jqString(body, "id");
      int idx = 0;
      while (true) {
        int fpos = body.indexOf("\"lane_id\"", idx);
        if (fpos < 0) break;
        String lane = Io.jqString(body.substring(fpos), "lane_id");
        double dens = Io.jqNumber(body.substring(fpos), "density_hint");
        PackRow row = new PackRow();
        row.instanceId = iid;
        row.laneId = lane;
        row.laneHex = Io.sha16(iid + "|" + lane + "|" + Io.fmt6(dens) + "|raw");
        row.floorRatio = dens / floor;
        rows.add(row);
        idx = fpos + 8;
      }
    }
    rows.sort(Comparator.comparing((PackRow r) -> r.instanceId).thenComparing(r -> r.laneId));
    return rows;
  }

  public static String echoHex(List<PackRow> rows) throws Exception {
    StringBuilder join = new StringBuilder();
    for (int i = 0; i < rows.size(); i++) {
      if (i > 0) join.append('|');
      join.append(rows.get(i).laneHex);
    }
    return Io.sha16(join.toString());
  }

  public static void writePack(Path out, List<PackRow> rows, String echo) throws Exception {
    StringBuilder sb = new StringBuilder();
    sb.append("{\"packed_context_hex\":\"").append(echo).append("\",\"echo_hex\":\"").append(echo).append("\",\"rows\":[");
    for (int i = 0; i < rows.size(); i++) {
      PackRow r = rows.get(i);
      if (i > 0) sb.append(',');
      sb.append("{\"instance_id\":\"").append(r.instanceId).append("\",");
      sb.append("\"lane_id\":\"").append(r.laneId).append("\",");
      sb.append("\"lane_hex\":\"").append(r.laneHex).append("\",");
      sb.append("\"floor_ratio\":").append(r.floorRatio).append("}");
    }
    sb.append("]}");
    Io.write(out, sb.toString());
  }
}
