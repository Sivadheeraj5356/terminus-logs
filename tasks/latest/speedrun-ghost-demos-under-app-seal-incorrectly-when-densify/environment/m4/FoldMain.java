package m4;

import java.nio.file.*;
import java.util.*;

public final class FoldMain {
  public static void main(String[] args) throws Exception {
    if (args.length != 3) {
      System.err.println("usage: fold_tool <annexRoot> <profilesDir> <packOut>");
      System.exit(2);
    }
    Path annex = Paths.get(args[0]);
    Path bands = Paths.get(args[1]);
    Path out = Paths.get(args[2]);
    List<FoldG.PackRow> rows = FoldG.foldG(annex, bands);
    String echo = FoldG.echoHex(rows);
    FoldG.writePack(out, rows, echo);
  }
}
