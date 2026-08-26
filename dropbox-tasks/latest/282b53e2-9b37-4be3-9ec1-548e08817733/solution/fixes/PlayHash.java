package nxq.play;
import nxq.hazards.Chambers;
import nxq.util.Io;
import java.util.*;
public final class PlayHash {
  private PlayHash() {}
  public static String compute(String caseId, List<String> moves, Adventure adv, Chambers hz) throws Exception {
    List<String> inv = new ArrayList<>(adv.inventory);
    Collections.sort(inv);
    List<String> w = new ArrayList<>(hz.watches);
    Collections.sort(w);
    List<String> l = new ArrayList<>(hz.leaks);
    Collections.sort(l);
    String pre = String.join("\n",
        caseId,
        String.join("\n", moves),
        adv.status(),
        String.join(">", adv.visited),
        String.join(",", inv),
        String.join(",", adv.violations),
        "W:" + String.join(",", w),
        "L:" + String.join(",", l));
    return Io.sha16(pre);
  }
}
