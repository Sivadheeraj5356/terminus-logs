package v9;

import java.nio.file.*;

public final class TieMain {
  public static void main(String[] args) throws Exception {
    if (args.length != 3) {
      System.err.println("usage: tie_tool <annexRoot> <workDir> <outPath>");
      System.exit(2);
    }
    TieW.tieW(Paths.get(args[0]), Paths.get(args[1]), Paths.get(args[2]));
  }
}
