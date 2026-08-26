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

    Chambers hz = Chambers.load(root);
    SaveLog journal = new SaveLog(out.resolve("state/replay.journal"));
    journal.load();
    journal.validateCommittedHistory();

    CaseRoster plan = CaseRoster.build(root, out, hz, journal);
    BoardOut.writeEpoch(out, hz.generation);

    int events = 0;
    List<Map<String, String>> manifestCases = new ArrayList<>();

    // Always rewrite GEN without reconciling prior commits.
    if (journal.size() == 0) {
      journal.append("GEN|" + hz.generation);
      events++;
      if (stopAfter != null && events >= stopAfter) return;
    }

    for (CaseRoster.CaseWork cw : plan.cases) {
      if (cw.reuse) {
        String existing = Io.read(out.resolve("transcripts").resolve(cw.id + ".json"));
        String status = existing.contains("\"status\": \"WIN\"") ? "WIN"
            : existing.contains("\"status\": \"LOSE\"") ? "LOSE" : "PARTIAL";
        String score = "0";
        int si = existing.indexOf("\"score\": ");
        if (si >= 0) {
          int e = existing.indexOf(",", si);
          score = existing.substring(si + 9, e).trim();
        }
        Map<String, String> row = new LinkedHashMap<>();
        row.put("case_id", cw.id);
        row.put("moves_fp", cw.fp);
        row.put("generation", hz.generation);
        row.put("status", status);
        row.put("score", score);
        manifestCases.add(row);
        continue;
      }

      journal.append("START|" + cw.id + "|" + cw.fp + "|" + hz.generation);
      events++;
      if (stopAfter != null && events >= stopAfter) return;

      List<String> moves = Io.filteredMoves(cw.moves);
      Adventure adv = new Adventure(hz);
      int seq = 0;
      for (String cmd : moves) {
        adv.apply(cmd);
        seq++;
        journal.append("EVT|" + cw.id + "|" + seq + "|" + cmd);
        events++;
        if (stopAfter != null && events >= stopAfter) return;
      }
      String status = adv.status();
      int score = adv.score();
      journal.append("FIN|" + cw.id + "|" + status + "|" + score + "|" + String.join(",", adv.violations));
      events++;
      if (stopAfter != null && events >= stopAfter) return;

      String json = Transcript.json(cw.id, moves, adv, hz);
      BoardOut.writeTranscript(out, cw.id, json);
      journal.append("COMMIT|" + cw.id);
      events++;
      if (stopAfter != null && events >= stopAfter) return;

      Map<String, String> row = new LinkedHashMap<>();
      row.put("case_id", cw.id);
      row.put("moves_fp", cw.fp);
      row.put("generation", hz.generation);
      row.put("status", status);
      row.put("score", Integer.toString(score));
      manifestCases.add(row);
    }

    journal.append("END");
    BoardOut.writeManifest(out, Manifest.render(hz.generation, manifestCases));
    BoardOut.pruneTranscripts(out, Set.of());
  }
}
