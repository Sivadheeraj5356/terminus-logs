package drv;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import m8.q1.TypesB;
import n3.k2.TypesA;
import t5.r4.TypesC;

/** Opaque driver entry launched by /app/bin/x7. */
public final class Main {
  public static void main(String[] args) throws Exception {
    Path evidence = null;
    Path out = null;
    for (int i = 0; i < args.length; i++) {
      if ("--evidence".equals(args[i]) && i + 1 < args.length) {
        evidence = Path.of(args[++i]);
      } else if ("--out".equals(args[i]) && i + 1 < args.length) {
        out = Path.of(args[++i]);
      }
    }
    if (evidence == null || out == null) {
      System.err.println("usage: Main --evidence DIR --out FILE");
      System.exit(2);
    }
    Path stage = Path.of("/app/output/stage");
    Files.createDirectories(stage);
    Files.createDirectories(out.getParent());

    List<IoKit.Arm> arms = IoKit.loadArms(evidence.resolve("arms.toml"));
    Map<String, IoKit.Pack> packs = IoKit.loadPacks(evidence.resolve("arms.toml"));
    List<TypesA.GenKey> gens = IoKit.loadGens(evidence.resolve("anchors.toml"));
    List<TypesB.AnchorGen> anchors = IoKit.loadAnchors(evidence.resolve("anchors.toml"));

    List<Row> rows = new ArrayList<>();
    List<String> lanes = new ArrayList<>();
    int totalViol = 0;

    for (IoKit.Arm arm : arms) {
      IoKit.Pack pack = packs.get(arm.pack);
      if (pack == null) {
        throw new IllegalStateException("missing pack " + arm.pack);
      }
      TypesA.Connection db =
          IoKit.loadDb(evidence.resolve("sql").resolve(pack.journal), arm.transform);
      List<TypesB.PemBlob> mats =
          IoKit.loadMats(evidence.resolve("mat").resolve("inventory_index.toml"), arm.transform);
      List<TypesC.HsFrag> frags = IoKit.loadHs(evidence.resolve("hs").resolve(pack.hs));

      List<TypesA.EpochCand> cands = PipeLoad.foldLane(db, gens);
      List<TypesB.BoundView> views = PipeLoad.bindMats(cands, mats, anchors);
      List<TypesC.TrustWin> wins = PipeSeal.syncWins(db, views, frags);

      byte[] tip = Files.exists(stage.resolve("early.tip"))
          ? Files.readAllBytes(stage.resolve("early.tip"))
          : new byte[0];
      Files.writeString(stage.resolve(arm.id + ".mark"), "1");
      List<TypesC.StageRow> stages = List.of(new TypesC.StageRow(pack.id, arm.id, tip));
      TypesC.SealRecord seal = PipeSeal.seal(wins, stages);

      int viol = countViol(views, wins, mats);
      // Prefer contract digests when seal path is correct; still emit seal fields.
      String lane = seal.hexLane;
      int sealOk = seal.sealOk;
      rows.add(new Row(pack.id, arm.id, lane, viol, sealOk, 1));
      lanes.add(lane);
      totalViol += viol;
    }

    String sealHex = topSeal(lanes, totalViol);
    int closed = 1;
    for (Row r : rows) {
      if (r.violN != 0 || r.sealOk != 1) {
        closed = 0;
        break;
      }
    }
    if (!sealHex.equals(topSeal(lanes, totalViol))) {
      closed = 0;
    }

    StringBuilder json = new StringBuilder();
    json.append("{\n");
    json.append("  \"schema_ver\": 1,\n");
    json.append("  \"rows\": [\n");
    for (int i = 0; i < rows.size(); i++) {
      Row r = rows.get(i);
      json.append("    {");
      json.append("\"pack_id\": \"").append(r.packId).append("\", ");
      json.append("\"arm_id\": \"").append(r.armId).append("\", ");
      json.append("\"hex_lane\": \"").append(r.hexLane).append("\", ");
      json.append("\"viol_n\": ").append(r.violN).append(", ");
      json.append("\"seal_ok\": ").append(r.sealOk).append(", ");
      json.append("\"stage_mark\": ").append(r.stageMark);
      json.append("}");
      if (i + 1 < rows.size()) {
        json.append(",");
      }
      json.append("\n");
    }
    json.append("  ],\n");
    json.append("  \"seal_hex\": \"").append(sealHex).append("\",\n");
    json.append("  \"closed_ok\": ").append(closed).append("\n");
    json.append("}\n");
    Files.writeString(out, json.toString(), StandardCharsets.UTF_8);
  }

  static int countViol(
      List<TypesB.BoundView> views, List<TypesC.TrustWin> wins, List<TypesB.PemBlob> mats) {
    Map<String, String> expect = new HashMap<>();
    for (TypesB.PemBlob m : mats) {
      expect.put(m.pid + ":" + m.gen, m.role);
    }
    int n = 0;
    for (TypesC.TrustWin w : wins) {
      if (w.revoked) {
        n++;
      }
      if (w.hsFail) {
        n++;
      }
    }
    for (TypesB.BoundView v : views) {
      String exp = expect.get(v.pid + ":" + v.gen);
      if (exp != null && !exp.equals(v.role)) {
        n++;
      }
    }
    return n;
  }

  static String topSeal(List<String> lanes, int totalViol) throws Exception {
    MessageDigest md = MessageDigest.getInstance("SHA-256");
    for (String lane : lanes) {
      md.update(lane.getBytes(StandardCharsets.UTF_8));
    }
    md.update(intLE(totalViol));
    byte[] raw = md.digest();
    StringBuilder hex = new StringBuilder();
    for (byte b : raw) {
      hex.append(String.format("%02x", b));
    }
    return hex.toString();
  }

  private static byte[] intLE(int v) {
    return new byte[] {
      (byte) (v & 0xff),
      (byte) ((v >> 8) & 0xff),
      (byte) ((v >> 16) & 0xff),
      (byte) ((v >> 24) & 0xff)
    };
  }

  private static final class Row {
    final String packId;
    final String armId;
    final String hexLane;
    final int violN;
    final int sealOk;
    final int stageMark;

    Row(String packId, String armId, String hexLane, int violN, int sealOk, int stageMark) {
      this.packId = packId;
      this.armId = armId;
      this.hexLane = hexLane;
      this.violN = violN;
      this.sealOk = sealOk;
      this.stageMark = stageMark;
    }
  }
}
