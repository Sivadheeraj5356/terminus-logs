package q7;

import common.Io;
import java.nio.file.*;
import java.util.*;

public final class SepAux {
  private SepAux() {}

  public static List<Path> instancePaths(Path annexRoot) throws Exception {
    Path man = annexRoot.resolve("manifest.tsv");
    List<Path> out = new ArrayList<>();
    for (String line : Io.read(man).split("\n")) {
      if (line.startsWith("id") || line.isBlank()) continue;
      String[] parts = line.split("\t");
      out.add(annexRoot.resolve(parts[1]));
    }
    return out;
  }
}
