package m4;

import common.Io;
import java.nio.file.*;
import java.util.*;

public final class FoldAux {
  private FoldAux() {}

  public static double minDensifyFloor(Path profilesDir) throws Exception {
    double min = Double.POSITIVE_INFINITY;
    for (Path p : Io.listJson(profilesDir)) {
      String body = Io.read(p);
      min = Math.min(min, Io.jqNumber(body, "densify_floor"));
    }
    return min;
  }
}
