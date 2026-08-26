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
    CaseRoster plan = new CaseRoster(hz);
    Path casesDir = root.resolve("cases");
    List<Path> files = new ArrayList<>();
    try (DirectoryStream<Path> ds = Files.newDirectoryStream(casesDir, "*.moves")) {
      for (Path p : ds) files.add(p);
    }
    files.sort(Comparator.comparing(p -> p.getFileName().toString()));
    Path transcripts = out.resolve("transcripts");
    for (Path moves : files) {
      String id = moves.getFileName().toString().replace(".moves", "");
      List<String> lines = Io.filteredMoves(moves);
      String fp = Io.movesFp(lines);
      CaseWork cw = new CaseWork(id, moves, fp);
      Path t = transcripts.resolve(id + ".json");
      cw.reuse = Files.exists(t);
      plan.cases.add(cw);
    }
    return plan;
  }
}
