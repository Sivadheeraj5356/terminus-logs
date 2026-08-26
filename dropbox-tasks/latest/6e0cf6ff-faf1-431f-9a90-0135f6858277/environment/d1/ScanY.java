package d1;
import common.Io;
import java.nio.file.*;
import java.util.*;
public final class ScanY {
  public static List<String> scan(Path annex) throws Exception {
    List<String> ids = new ArrayList<>();
    for (Path p : Io.listJson(annex.resolve("instances"))) ids.add(p.getFileName().toString());
    return ids;
  }
}
