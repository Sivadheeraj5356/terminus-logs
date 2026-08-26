package v9;

import common.Io;
import java.nio.file.*;
import java.util.*;

public final class TieW {
  private TieW() {}

  public static void tieW(Path annexRoot, Path digestPath, Path outPath) throws Exception {
    String packBody = Io.read(digestPath.resolve("pack.json"));
    String packed = Io.jqString(packBody, "packed_context_hex");
    String echo = Io.jqString(packBody, "echo_hex");

    List<Map<String, Object>> packRows = new ArrayList<>();
    int idx = 0;
    while (true) {
      int p = packBody.indexOf("\"instance_id\"", idx);
      if (p < 0) break;
      String chunk = packBody.substring(p);
      if (!chunk.contains("\"lane_hex\"")) break;
      Map<String, Object> row = new LinkedHashMap<>();
      row.put("instance_id", Io.jqString(chunk, "instance_id"));
      row.put("lane_id", Io.jqString(chunk, "lane_id"));
      row.put("lane_hex", Io.jqString(chunk, "lane_hex"));
      row.put("floor_ratio", Io.jqNumber(chunk, "floor_ratio"));
      packRows.add(row);
      idx = p + 12;
    }

    Path profiles = Paths.get("/app/data/bands/profiles");
    List<Map<String, Object>> bandRows = new ArrayList<>();
    double imbMax = 0.0;
    for (Path pp : Io.listJson(profiles)) {
      String body = Io.read(pp);
      String pid = Io.jqString(body, "id");
      int bidx = body.indexOf("\"bands\"");
      String bb = body.substring(bidx);
      int pos = 0;
      double sumE = 0.0;
      double sumAdmit = 0.0;
      List<String> lanes = new ArrayList<>();
      for (Map<String, Object> pr : packRows) {
        lanes.add((String) pr.get("lane_id"));
      }
      lanes = new ArrayList<>(new TreeSet<>(lanes));
      String kid = String.join(",", lanes);
      while (true) {
        int np = bb.indexOf("\"name\"", pos);
        if (np < 0) break;
        String name = Io.jqString(bb.substring(np), "name");
        double E = Io.jqNumber(bb.substring(np), "E");
        sumE += E;
        double eAdmit = E;
        sumAdmit += eAdmit;
        String xfer = Io.sha16(pid + ":" + name + ":" + Io.fmt12(eAdmit) + ":" + packed);
        String span = Io.sha16(pid + ":" + name + ":" + kid + ":" + packed);
        Map<String, Object> br = new LinkedHashMap<>();
        br.put("profile_id", pid);
        br.put("band_xfer_hex", xfer);
        br.put("kernel_span_hex", span);
        br.put("e_admit", eAdmit);
        bandRows.add(br);
        pos = np + 6;
      }
      imbMax = Math.max(imbMax, Math.abs(sumAdmit - sumE));
    }

    boolean localOk = imbMax <= 1e-9;
    for (Map<String, Object> pr : packRows) {
      if ((Double) pr.get("floor_ratio") + 1e-9 < 1.0) {
        localOk = false;
      }
    }

    String replay = Io.sha16("local|" + packed);
    int violations = 0;
    int hold = 0;

    StringBuilder sb = new StringBuilder();
    sb.append("{\"schema_version\":\"1.0\",");
    sb.append("\"band_rows\":[");
    for (int i = 0; i < bandRows.size(); i++) {
      Map<String, Object> br = bandRows.get(i);
      if (i > 0) {
        sb.append(',');
      }
      sb.append("{\"profile_id\":\"").append(br.get("profile_id")).append("\",");
      sb.append("\"band_xfer_hex\":\"").append(br.get("band_xfer_hex")).append("\",");
      sb.append("\"kernel_span_hex\":\"").append(br.get("kernel_span_hex")).append("\",");
      sb.append("\"e_admit\":").append(br.get("e_admit")).append("}");
    }
    sb.append("],\"pack_rows\":[");
    for (int i = 0; i < packRows.size(); i++) {
      Map<String, Object> pr = packRows.get(i);
      if (i > 0) {
        sb.append(',');
      }
      sb.append("{\"instance_id\":\"").append(pr.get("instance_id")).append("\",");
      sb.append("\"lane_id\":\"").append(pr.get("lane_id")).append("\",");
      sb.append("\"lane_hex\":\"").append(pr.get("lane_hex")).append("\",");
      sb.append("\"floor_ratio\":").append(pr.get("floor_ratio")).append("}");
    }
    sb.append("],\"echo_hex\":\"").append(echo).append("\",");
    sb.append("\"replay_root\":\"").append(replay).append("\",");
    sb.append("\"algebra_violations\":").append(violations).append(",");
    sb.append("\"local_witness_ok\":").append(localOk ? "true" : "false").append(",");
    sb.append("\"strategy_scan_hold\":").append(hold).append("}");
    Io.write(outPath, sb.toString());
  }
}
