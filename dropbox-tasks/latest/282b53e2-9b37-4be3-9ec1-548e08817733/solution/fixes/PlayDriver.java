package nxq.campaign;
import nxq.hazards.Chambers;
import nxq.roster.CaseRoster;
import nxq.savelog.SaveLog;
import nxq.model.Transcript;
import nxq.play.Adventure;
import nxq.scoreboard.BoardOut;
import nxq.scoreboard.Manifest;
import nxq.util.Io;
import java.nio.file.*;
import java.util.*;

public final class PlayDriver {
  public static void main(String[] args) throws Exception {
    if (args.length < 2) throw new IllegalArgumentException("root out required");
    Path root = Paths.get(args[0]);
    Path out = Paths.get(args[1]);
    Integer stopAfter = null;
    for (int i = 2; i < args.length; i++) {
      if ("--stop-after".equals(args[i]) && i + 1 < args.length) {
        stopAfter = Integer.parseInt(args[++i]);
      }
    }
    Files.createDirectories(out.resolve("transcripts"));
    Files.createDirectories(out.resolve("state"));

    Chambers.clearCache();
    Chambers hz = Chambers.load(root);
    SaveLog journal = new SaveLog(out.resolve("state/replay.journal"));
    try {
      journal.load();
      journal.validateCommittedHistory();
    } catch (IllegalStateException ex) {
      System.err.println(ex.getMessage());
      System.exit(2);
      return;
    }

    journal.rewrite(normalizeSaveLog(journal.lines(), hz.generation));
    CaseRoster plan = CaseRoster.build(root, out, hz, journal);
    BoardOut.writeEpoch(out, hz.generation);

    int events = 0;
    if (journal.lines().stream().noneMatch(l -> l.startsWith("GEN|"))) {
      events += append(journal, "GEN|" + hz.generation, stopAfter, events);
    }

    List<String> withoutEnd = new ArrayList<>();
    for (String l : journal.lines()) {
      if (!"END".equals(l)) withoutEnd.add(l);
    }
    if (withoutEnd.size() != journal.lines().size()) journal.rewrite(withoutEnd);

    Map<String, Map<String, String>> manifestMap = new LinkedHashMap<>();
    for (CaseRoster.CaseWork cw : plan.cases) {
      if (!cw.reuse) continue;
      String existing = Io.read(out.resolve("transcripts").resolve(cw.id + ".json"));
      Map<String, String> row = new LinkedHashMap<>();
      row.put("case_id", cw.id);
      row.put("moves_fp", cw.fp);
      row.put("generation", hz.generation);
      row.put("status", extract(existing, "status"));
      row.put("score", extractNum(existing, "score"));
      manifestMap.put(cw.id, row);
    }

    for (CaseRoster.CaseWork cw : plan.cases) {
      if (cw.reuse) continue;
      Files.deleteIfExists(out.resolve("transcripts").resolve(cw.id + ".json"));
      events += append(journal, "START|" + cw.id + "|" + cw.fp + "|" + hz.generation, stopAfter, events);

      List<String> moves = Io.filteredMoves(cw.moves);
      Adventure adv = new Adventure(hz);
      int seq = 0;
      for (String cmd : moves) {
        boolean counted = adv.apply(cmd);
        if (!counted) break;
        seq++;
        events += append(journal, "EVT|" + cw.id + "|" + seq + "|" + cmd, stopAfter, events);
        if (adv.exited) break;
      }
      String status = adv.status();
      int score = adv.score();
      events += append(
          journal,
          "FIN|" + cw.id + "|" + status + "|" + score + "|" + String.join(",", adv.violations),
          stopAfter,
          events);

      BoardOut.writeTranscript(out, cw.id, Transcript.json(cw.id, moves, adv, hz));
      events += append(journal, "COMMIT|" + cw.id, stopAfter, events);

      Map<String, String> row = new LinkedHashMap<>();
      row.put("case_id", cw.id);
      row.put("moves_fp", cw.fp);
      row.put("generation", hz.generation);
      row.put("status", status);
      row.put("score", Integer.toString(score));
      manifestMap.put(cw.id, row);
    }

    Set<String> keep = new LinkedHashSet<>();
    List<Map<String, String>> ordered = new ArrayList<>();
    for (CaseRoster.CaseWork cw : plan.cases) {
      keep.add(cw.id);
      if (!manifestMap.containsKey(cw.id)) {
        BoardOut.pruneTranscripts(out, existingIds(out));
        return;
      }
      ordered.add(manifestMap.get(cw.id));
    }
    journal.append("END");
    BoardOut.pruneTranscripts(out, keep);
    BoardOut.writeManifest(out, Manifest.render(hz.generation, ordered));
  }

  private static int append(SaveLog journal, String rec, Integer stopAfter, int events) throws Exception {
    journal.append(rec);
    int next = events + 1;
    if (stopAfter != null && next >= stopAfter) System.exit(0);
    return 1;
  }

  private static List<String> normalizeSaveLog(List<String> lines, String generation) {
    List<String> out = new ArrayList<>();
    String openCase = null;
    int openAt = -1;
    for (String line : lines) {
      String[] p = line.split("\\|", -1);
      if ("GEN".equals(p[0])) {
        if (!generation.equals(p[1])) {
          out.clear();
          openCase = null;
          openAt = -1;
          continue;
        }
        out.add(line);
      } else if ("START".equals(p[0])) {
        openCase = p[1];
        openAt = out.size();
        out.add(line);
      } else if ("COMMIT".equals(p[0])) {
        out.add(line);
        if (openCase != null && openCase.equals(p[1])) {
          openCase = null;
          openAt = -1;
        }
      } else {
        out.add(line);
      }
    }
    if (openCase != null && openAt >= 0) {
      return new ArrayList<>(out.subList(0, openAt));
    }
    return out;
  }

  private static Set<String> existingIds(Path out) throws Exception {
    Set<String> ids = new HashSet<>();
    Path dir = out.resolve("transcripts");
    if (!Files.isDirectory(dir)) return ids;
    try (DirectoryStream<Path> ds = Files.newDirectoryStream(dir, "*.json")) {
      for (Path p : ds) ids.add(p.getFileName().toString().replace(".json", ""));
    }
    return ids;
  }

  private static String extract(String json, String key) {
    String needle = "\"" + key + "\": \"";
    int i = json.indexOf(needle);
    if (i < 0) return "";
    int s = i + needle.length();
    return json.substring(s, json.indexOf('"', s));
  }

  private static String extractNum(String json, String key) {
    String needle = "\"" + key + "\": ";
    int i = json.indexOf(needle);
    if (i < 0) return "0";
    int s = i + needle.length();
    int e = s;
    while (e < json.length() && (Character.isDigit(json.charAt(e)) || json.charAt(e) == '-')) e++;
    return json.substring(s, e);
  }
}
