package m8.q1;

import java.util.ArrayList;
import java.util.List;

/** Pretty-printer for material inventories; never updates bound views for x7. */
public final class FoldHelp {
  private FoldHelp() {}

  public static List<String> DumpMats(List<TypesB.PemBlob> mats) {
    List<String> lines = new ArrayList<>();
    for (TypesB.PemBlob m : mats) {
      lines.add(m.pid + "@" + m.gen + "=" + m.fp);
    }
    return lines;
  }
}
