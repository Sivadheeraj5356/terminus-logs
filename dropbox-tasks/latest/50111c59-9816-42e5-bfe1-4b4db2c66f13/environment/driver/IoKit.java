package drv;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import m8.q1.TypesB;
import n3.k2.TypesA;
import t5.r4.TypesC;

/** Load corp dump surfaces for the driver. */
public final class IoKit {
  private IoKit() {}

  public static final class Arm {
    public final String id;
    public final String pack;
    public final String transform;

    public Arm(String id, String pack, String transform) {
      this.id = id;
      this.pack = pack;
      this.transform = transform;
    }
  }

  public static final class Pack {
    public final String id;
    public final String journal;
    public final String hs;

    public Pack(String id, String journal, String hs) {
      this.id = id;
      this.journal = journal;
      this.hs = hs;
    }
  }

  public static TypesA.Connection loadDb(Path dbPath, String transform) throws Exception {
    List<TypesA.IssueRow> issue = new ArrayList<>();
    List<TypesA.RevRow> revoke = new ArrayList<>();
    String qIssue = "SELECT pid, gen, ts, scp, role FROM issue_rows;";
    String qRev = "SELECT pid, gen, revoked FROM revoke_rows;";
    for (String[] cols : sqlite(dbPath, qIssue)) {
      issue.add(
          new TypesA.IssueRow(
              cols[0],
              Integer.parseInt(cols[1]),
              Integer.parseInt(cols[2]),
              cols[3],
              cols[4]));
    }
    for (String[] cols : sqlite(dbPath, qRev)) {
      revoke.add(
          new TypesA.RevRow(cols[0], Integer.parseInt(cols[1]), Integer.parseInt(cols[2])));
    }
    if ("reorder_journals".equals(transform)) {
      issue.sort(Comparator.comparingInt((TypesA.IssueRow r) -> r.ts));
      List<TypesA.IssueRow> trimmed = new ArrayList<>();
      for (TypesA.IssueRow r : issue) {
        if (r.ts % 2 == 0 || r.gen > 0) {
          trimmed.add(r);
        }
      }
      issue = trimmed;
    } else if ("drop_redundant_snap".equals(transform)) {
      Map<String, TypesA.IssueRow> best = new HashMap<>();
      for (TypesA.IssueRow r : issue) {
        String k = r.pid;
        TypesA.IssueRow prev = best.get(k);
        if (prev == null || r.ts < prev.ts) {
          best.put(k, r);
        }
      }
      List<TypesA.IssueRow> collapsed = new ArrayList<>();
      for (TypesA.IssueRow r : best.values()) {
        collapsed.add(new TypesA.IssueRow(r.pid, r.gen, r.ts, r.scp, r.role));
      }
      for (TypesA.IssueRow r : issue) {
        if (r.gen >= 50) {
          collapsed.add(r);
        }
      }
      issue = collapsed;
    } else if ("perm_roles_a".equals(transform) || "perm_roles_b".equals(transform)) {
      issue.sort(Comparator.comparingInt((TypesA.IssueRow r) -> -r.gen));
    }
    return new TypesA.Connection(issue, revoke);
  }

  public static List<TypesA.GenKey> loadGens(Path anchors) throws Exception {
    List<TypesA.GenKey> out = new ArrayList<>();
    Map<String, String> cur = null;
    for (String line : Files.readAllLines(anchors, StandardCharsets.UTF_8)) {
      String s = line.trim();
      if (s.isEmpty() || s.startsWith("#")) {
        continue;
      }
      if (s.equals("[[anchor]]")) {
        if (cur != null && cur.containsKey("gen")) {
          out.add(new TypesA.GenKey(Integer.parseInt(cur.get("gen")), cur.getOrDefault("label", "")));
        }
        cur = new HashMap<>();
        continue;
      }
      if (cur == null || !s.contains("=")) {
        continue;
      }
      String[] parts = s.split("=", 2);
      cur.put(parts[0].trim(), unquote(parts[1].trim()));
    }
    if (cur != null && cur.containsKey("gen")) {
      out.add(new TypesA.GenKey(Integer.parseInt(cur.get("gen")), cur.getOrDefault("label", "")));
    }
    return out;
  }

  public static List<TypesB.AnchorGen> loadAnchors(Path anchors) throws Exception {
    List<TypesB.AnchorGen> out = new ArrayList<>();
    for (TypesA.GenKey g : loadGens(anchors)) {
      out.add(new TypesB.AnchorGen(g.gen, g.label));
    }
    return out;
  }

  public static List<TypesB.PemBlob> loadMats(Path inv, String transform) throws Exception {
    List<TypesB.PemBlob> out = new ArrayList<>();
    Map<String, String> cur = null;
    String mode = "";
    for (String line : Files.readAllLines(inv, StandardCharsets.UTF_8)) {
      String s = line.trim();
      if (s.isEmpty() || s.startsWith("#")) {
        continue;
      }
      if (s.equals("[[mat]]")) {
        if ("mat".equals(mode) && cur != null && cur.containsKey("pid")) {
          out.add(blobFrom(cur, transform));
        }
        cur = new HashMap<>();
        mode = "mat";
        continue;
      }
      if (s.equals("[[gen]]")) {
        if ("mat".equals(mode) && cur != null && cur.containsKey("pid")) {
          out.add(blobFrom(cur, transform));
        }
        cur = new HashMap<>();
        mode = "gen";
        continue;
      }
      if (cur == null || !s.contains("=")) {
        continue;
      }
      String[] parts = s.split("=", 2);
      cur.put(parts[0].trim(), unquote(parts[1].trim()));
    }
    if ("mat".equals(mode) && cur != null && cur.containsKey("pid")) {
      out.add(blobFrom(cur, transform));
    }
    if ("reencode_pem".equals(transform)) {
      // PEM bytes may change on disk; index fp/role remain authoritative.
      out.sort(Comparator.comparing((TypesB.PemBlob m) -> m.pid + ":" + m.gen));
    }
    return out;
  }

  private static TypesB.PemBlob blobFrom(Map<String, String> cur, String transform) {
    String pid = cur.get("pid");
    int gen = Integer.parseInt(cur.get("gen"));
    String role = cur.get("role");
    role = remapRole(pid, role, transform);
    return new TypesB.PemBlob(gen, pid, cur.get("fp"), role);
  }

  public static String remapRole(String pid, String role, String transform) {
    if ("perm_roles_a".equals(transform)) {
      Map<String, String> m = Map.of(
          "p_alpha", "svc.mesh.west",
          "p_beta", "svc.mesh.core",
          "p_gamma", "svc.mesh.east");
      return m.getOrDefault(pid, role);
    }
    if ("perm_roles_b".equals(transform)) {
      Map<String, String> m = Map.of(
          "p_alpha", "svc.mesh.core",
          "p_beta", "svc.mesh.east",
          "p_gamma", "svc.mesh.west");
      return m.getOrDefault(pid, role);
    }
    if ("hostile_role_widen".equals(transform) && "p_beta".equals(pid)) {
      return "svc.mesh.escalate";
    }
    return role;
  }

  public static List<TypesC.HsFrag> loadHs(Path hsFile) throws Exception {
    List<TypesC.HsFrag> out = new ArrayList<>();
    for (String line : Files.readAllLines(hsFile, StandardCharsets.UTF_8)) {
      String s = line.trim();
      if (s.isEmpty()) {
        continue;
      }
      String pid = extract(s, "pid");
      int gen = Integer.parseInt(extract(s, "gen"));
      boolean ok = Boolean.parseBoolean(extract(s, "ok"));
      String nonce = extract(s, "nonce");
      out.add(new TypesC.HsFrag(pid, gen, ok, nonce));
    }
    return out;
  }

  public static List<Arm> loadArms(Path armsToml) throws Exception {
    List<Arm> out = new ArrayList<>();
    Map<String, String> cur = null;
    String mode = "";
    for (String line : Files.readAllLines(armsToml, StandardCharsets.UTF_8)) {
      String s = line.trim();
      if (s.isEmpty() || s.startsWith("#")) {
        continue;
      }
      if (s.equals("[[arm]]")) {
        if ("arm".equals(mode) && cur != null && cur.containsKey("id")) {
          out.add(new Arm(cur.get("id"), cur.getOrDefault("pack", "base"), cur.getOrDefault("transform", "none")));
        }
        cur = new HashMap<>();
        mode = "arm";
        continue;
      }
      if (s.equals("[[pack]]")) {
        if ("arm".equals(mode) && cur != null && cur.containsKey("id")) {
          out.add(new Arm(cur.get("id"), cur.getOrDefault("pack", "base"), cur.getOrDefault("transform", "none")));
        }
        cur = new HashMap<>();
        mode = "pack";
        continue;
      }
      if (cur == null || !s.contains("=")) {
        continue;
      }
      String[] parts = s.split("=", 2);
      cur.put(parts[0].trim(), unquote(parts[1].trim()));
    }
    if ("arm".equals(mode) && cur != null && cur.containsKey("id")) {
      out.add(new Arm(cur.get("id"), cur.getOrDefault("pack", "base"), cur.getOrDefault("transform", "none")));
    }
    return out;
  }

  public static Map<String, Pack> loadPacks(Path armsToml) throws Exception {
    Map<String, Pack> out = new HashMap<>();
    Map<String, String> cur = null;
    String mode = "";
    for (String line : Files.readAllLines(armsToml, StandardCharsets.UTF_8)) {
      String s = line.trim();
      if (s.isEmpty() || s.startsWith("#")) {
        continue;
      }
      if (s.equals("[[pack]]")) {
        if ("pack".equals(mode) && cur != null && cur.containsKey("id")) {
          out.put(cur.get("id"), new Pack(cur.get("id"), cur.get("journal"), cur.get("hs")));
        }
        cur = new HashMap<>();
        mode = "pack";
        continue;
      }
      if (s.equals("[[arm]]")) {
        if ("pack".equals(mode) && cur != null && cur.containsKey("id")) {
          out.put(cur.get("id"), new Pack(cur.get("id"), cur.get("journal"), cur.get("hs")));
        }
        cur = new HashMap<>();
        mode = "arm";
        continue;
      }
      if (cur == null || !s.contains("=")) {
        continue;
      }
      String[] parts = s.split("=", 2);
      cur.put(parts[0].trim(), unquote(parts[1].trim()));
    }
    if ("pack".equals(mode) && cur != null && cur.containsKey("id")) {
      out.put(cur.get("id"), new Pack(cur.get("id"), cur.get("journal"), cur.get("hs")));
    }
    return out;
  }

  private static List<String[]> sqlite(Path db, String sql) throws Exception {
    ProcessBuilder pb = new ProcessBuilder("sqlite3", "-separator", "\t", db.toString(), sql);
    pb.redirectErrorStream(true);
    Process p = pb.start();
    List<String[]> rows = new ArrayList<>();
    try (BufferedReader br =
        new BufferedReader(new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
      String line;
      while ((line = br.readLine()) != null) {
        if (line.isEmpty()) {
          continue;
        }
        rows.add(line.split("\t", -1));
      }
    }
    int rc = p.waitFor();
    if (rc != 0) {
      throw new IllegalStateException("sqlite3 failed rc=" + rc + " sql=" + sql);
    }
    return rows;
  }

  private static String unquote(String v) {
    if (v.length() >= 2 && ((v.charAt(0) == '"' && v.charAt(v.length() - 1) == '"')
        || (v.charAt(0) == '\'' && v.charAt(v.length() - 1) == '\''))) {
      return v.substring(1, v.length() - 1);
    }
    return v;
  }

  private static String extract(String jsonLine, String key) {
    String needle = "\"" + key + "\"";
    int i = jsonLine.indexOf(needle);
    if (i < 0) {
      throw new IllegalArgumentException("missing " + key);
    }
    int colon = jsonLine.indexOf(':', i + needle.length());
    int start = colon + 1;
    while (start < jsonLine.length() && Character.isWhitespace(jsonLine.charAt(start))) {
      start++;
    }
    if (jsonLine.charAt(start) == '"') {
      int end = jsonLine.indexOf('"', start + 1);
      return jsonLine.substring(start + 1, end);
    }
    int end = start;
    while (end < jsonLine.length()
        && jsonLine.charAt(end) != ','
        && jsonLine.charAt(end) != '}') {
      end++;
    }
    return jsonLine.substring(start, end).trim();
  }
}
