package q7;

import common.Io;
import java.nio.file.*;
import java.util.*;

public final class SepH {
  static final class CutRow {
    String instanceId;
    String laneId;
    String spanHex;
    double tickCost;
    double densityHint;
  }

  static final Map<String, String> MEMO = new HashMap<>();

  private SepH() {}

  public static List<CutRow> sepH(Path annexRoot, Path bandPath) throws Exception {
    List<CutRow> rows = new ArrayList<>();
    int arrival = 0;
    for (Path ip : SepAux.instancePaths(annexRoot)) {
      String body = Io.read(ip);
      String iid = Io.jqString(body, "id");
      String pin = Io.jqString(body, "client_pin");
            int idx = 0;
      while (true) {
        int fpos = body.indexOf("\"lane_id\"", idx);
        if (fpos < 0) break;
        String lane = Io.jqString(body.substring(fpos), "lane_id");
        double tick = Io.jqNumber(body.substring(fpos), "tick_cost");
        double dens = Io.jqNumber(body.substring(fpos), "density_hint");
        String phex = Io.jqString(body.substring(fpos), "pin_hex");
        String memoKey = lane;
        String span;
        if (MEMO.containsKey(memoKey)) {
          span = MEMO.get(memoKey);
        } else {
          span = Io.sha16(lane + "|" + pin + "|" + phex + "|" + Io.fmt6(tick) + "|arr" + arrival);
          MEMO.put(memoKey, span);
        }
        CutRow row = new CutRow();
        row.instanceId = iid;
        row.laneId = lane;
        row.spanHex = span;
        row.tickCost = tick;
        row.densityHint = dens;
        rows.add(row);
        arrival++;
        idx = fpos + 8;
      }
    }
    return rows;
  }

  public static void writeCut(Path out, List<CutRow> rows) throws Exception {
    StringBuilder sb = new StringBuilder();
    sb.append("{\"rows\":[");
    for (int i = 0; i < rows.size(); i++) {
      CutRow r = rows.get(i);
      if (i > 0) sb.append(',');
      sb.append("{\"instance_id\":\"").append(r.instanceId).append("\",");
      sb.append("\"lane_id\":\"").append(r.laneId).append("\",");
      sb.append("\"span_hex\":\"").append(r.spanHex).append("\",");
      sb.append("\"tick_cost\":").append(r.tickCost).append(",");
      sb.append("\"density_hint\":").append(r.densityHint).append("}");
    }
    sb.append("]}");
    Io.write(out, sb.toString());
  }
}
