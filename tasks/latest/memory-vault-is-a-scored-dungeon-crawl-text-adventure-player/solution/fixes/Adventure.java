package nxq.play;
import nxq.graph.Rooms;
import nxq.hazards.Chambers;
import java.util.*;
public final class Adventure {
  public String room = "atrium";
  public final List<String> visited = new ArrayList<>();
  public final LinkedHashSet<String> inventory = new LinkedHashSet<>();
  public final List<String> violations = new ArrayList<>();
  public final Set<String> sealed = new HashSet<>();
  public final Set<String> scrubbed = new HashSet<>();
  public final Latch latch = new Latch();
  public boolean exited;
  public int applied;
  private final Chambers hz;

  public Adventure(Chambers hz) {
    this.hz = hz;
    visited.add("atrium");
  }

  public boolean apply(String cmd) {
    if (exited) return false;
    String[] p = cmd.split("\\s+");
    String op = p[0];
    if ("MOVE".equals(op) && p.length > 1) {
      applied++;
      String dest = p[1];
      if (!Rooms.edge(room, dest)) {
        violations.add("invalid:" + dest);
        return true;
      }
      if (hz.watches.contains(dest) && !sealed.contains(dest)) {
        violations.add("watch:" + dest);
        return true;
      }
      room = dest;
      visited.add(dest);
      return true;
    }
    if ("TAKE".equals(op) && p.length > 1) {
      applied++;
      String item = p[1];
      if ("torch".equals(item) && "atrium".equals(room)) inventory.add(item);
      else if ("patch".equals(item) && "buffer".equals(room)) inventory.add(item);
      else if ("key".equals(item) && "canary".equals(room) && !violations.contains("watch:canary")) inventory.add(item);
      return true;
    }
    if ("DROP".equals(op) && p.length > 1) {
      applied++;
      inventory.remove(p[1]);
      return true;
    }
    if ("WAIT".equals(op)) {
      applied++;
      latch.onWait(room, inventory);
      return true;
    }
    if ("SEAL".equals(op) && p.length > 1) {
      applied++;
      latch.trySeal(p[1], inventory, sealed);
      return true;
    }
    if ("SCRUB".equals(op) && p.length > 1) {
      applied++;
      if ("leak".equals(p[1]) && "leak".equals(room) && inventory.contains("torch")) scrubbed.add("leak");
      return true;
    }
    if ("EXIT".equals(op)) {
      applied++;
      List<String> unpaid = new ArrayList<>();
      for (String r : hz.leaks) {
        if (visited.contains(r) && !scrubbed.contains(r)) unpaid.add(r);
      }
      Collections.sort(unpaid);
      for (String r : unpaid) violations.add("leak:" + r);
      if ("vault".equals(room) && !inventory.contains("key")) violations.add("exit:key");
      exited = true;
      return true;
    }
    applied++;
    return true;
  }

  public String status() {
    boolean win = exited && "vault".equals(room) && inventory.contains("key") && violations.isEmpty();
    boolean lose = false;
    for (String v : violations) if (v.startsWith("watch:")) lose = true;
    if (violations.size() > 2) lose = true;
    if (win) return "WIN";
    if (lose) return "LOSE";
    return "PARTIAL";
  }

  public int score() {
    String st = status();
    int bonus = "WIN".equals(st) ? 25 : "PARTIAL".equals(st) ? 5 : -20;
    return 100 - applied * 2 - violations.size() * 17 + bonus;
  }
}
