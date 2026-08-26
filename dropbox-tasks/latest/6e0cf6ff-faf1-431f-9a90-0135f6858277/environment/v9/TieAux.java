package v9;

import common.Io;
import java.nio.file.*;
import java.util.*;

public final class TieAux {
  private TieAux() {}

  public static String annexConcat(Path annexRoot) throws Exception {
    Path man = annexRoot.resolve("manifest.tsv");
    StringBuilder sb = new StringBuilder();
    for (String line : Io.read(man).split("\n")) {
      if (line.startsWith("id") || line.isBlank()) continue;
      String[] parts = line.split("\t");
      sb.append(Io.read(annexRoot.resolve(parts[1])));
    }
    return sb.toString();
  }
}
