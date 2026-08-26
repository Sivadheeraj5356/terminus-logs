package q7;

import java.nio.file.*;
import java.util.*;

public final class SepMain {
  public static void main(String[] args) throws Exception {
    if (args.length != 3) {
      System.err.println("usage: sep_tool <annexRoot> <profilesDir> <cutOut>");
      System.exit(2);
    }
    Path annex = Paths.get(args[0]);
    Path bands = Paths.get(args[1]);
    Path out = Paths.get(args[2]);
    List<SepH.CutRow> rows = SepH.sepH(annex, bands);
    SepH.writeCut(out, rows);
  }
}
