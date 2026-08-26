package nxq.roster;
import nxq.hazards.Chambers;
import nxq.savelog.SaveLog;
import nxq.util.Io;
import java.nio.file.*;
import java.util.*;
public final class CaseRoster {
  public static final class CaseWork {
    public final String id;
    public final Path moves;
    public final String fp;
    public boolean reuse;
    public CaseWork(String id, Path moves, String fp) {
      this.id = id; this.moves = moves; this.fp = fp;
    }
  }

  public final List<CaseWork> cases = new ArrayList<>();
  public final Chambers hz;

  public CaseRoster(Chambers hz) { this.hz = hz; }

  public static CaseRoster build(Path root, Path out, Chambers hz, SaveLog journal) throws Exception {
    Map<String, String[]> open = new HashMap<>();
    Map<String, String[]> meta = new HashMap<>();
    Set<String> ok = new HashSet<>();
    String journalGen = null;
    for (String line : journal.lines()) {
      String[] p = line.split("\\|", -1);
      if ("GEN".equals(p[0])) journalGen = p[1];
      else if ("START".equals(p[0])) open.put(p[1], new String[]{p[2], p[3]});
      else if ("COMMIT".equals(p[0])) {
        String id = p[1];
        if (open.containsKey(id)) {
          meta.put(id, open.remove(id));
          ok.add(id);
        }
      }
    }

    CaseRoster plan = new CaseRoster(hz);
    Path casesDir = root.resolve("cases");
    List<Path> files = new ArrayList<>();
    try (DirectoryStream<Path> ds = Files.newDirectoryStream(casesDir, "*.moves")) {
      for (Path p : ds) files.add(p);
    }
    files.sort(Comparator.comparing(p -> p.getFileName().toString()));
    for (Path moves : files) {
      String id = moves.getFileName().toString().replace(".moves", "");
      List<String> lines = Io.filteredMoves(moves);
      String fp = Io.movesFp(lines);
      CaseWork cw = new CaseWork(id, moves, fp);
      Path t = out.resolve("transcripts").resolve(id + ".json");
      String[] m = meta.get(id);
      cw.reuse = ok.contains(id)
          && journalGen != null
          && hz.generation.equals(journalGen)
          && m != null
          && fp.equals(m[0])
          && hz.generation.equals(m[1])
          && Files.exists(t)
          && Io.read(t).contains("\"generation\": \"" + hz.generation + "\"");
      plan.cases.add(cw);
    }
    return plan;
  }
}
