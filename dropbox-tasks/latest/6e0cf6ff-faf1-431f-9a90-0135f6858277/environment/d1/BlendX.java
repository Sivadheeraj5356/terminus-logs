package d1;
import common.Io;
import java.nio.file.*;
public final class BlendX {
  public static String blend(Path annex) throws Exception {
    return Io.sha16("blend|" + annex.toString());
  }
}
