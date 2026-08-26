package nxq.hazards;
import nxq.util.Io;
import java.nio.file.*;
import java.util.*;
import java.util.regex.*;
public final class Chambers {
  public final String generation;
  public final SortedSet<String> watches;
  public final SortedSet<String> leaks;

  private Chambers(String g, SortedSet<String> w, SortedSet<String> l) {
    this.generation = g; this.watches = w; this.leaks = l;
  }

  public static Chambers load(Path root) throws Exception {
    Path watch = root.resolve("traces/watch-chambers.log");
    Path scrub = root.resolve("traces/scrub-chambers.txt");
    SortedSet<String> watches = new TreeSet<>(scanWatch(Io.read(watch)));
    SortedSet<String> leaks = new TreeSet<>(scanScrub(Io.read(scrub)));
    byte[] a = Io.readBytes(watch);
    byte[] b = Io.readBytes(scrub);
    byte[] joined = new byte[a.length + 1 + b.length];
    System.arraycopy(a, 0, joined, 0, a.length);
    joined[a.length] = '\n';
    System.arraycopy(b, 0, joined, a.length + 1, b.length);
    return new Chambers(Io.sha16(joined), watches, leaks);
  }

  public static void clearCache() { /* no process cache */ }

  static Set<String> scanWatch(String text) {
    Map<String, Boolean> state = new LinkedHashMap<>();
    for (String line : text.split("\n", -1)) {
      if (line.contains("kind=\"watch\"") && line.contains("room=\"")) {
        Matcher rm = Pattern.compile("room=\"([a-z]+)\"").matcher(line);
        if (!rm.find()) continue;
        String room = rm.group(1);
        boolean primed = line.contains("primed=\"true\"");
        boolean unprimed = line.contains("primed=\"false\"");
        if (primed) state.put(room, Boolean.FALSE);
        else if (unprimed) state.put(room, Boolean.TRUE);
        else state.put(room, Boolean.TRUE);
      }
      Matcher prose = Pattern.compile("The ([a-z]+) room is watched").matcher(line);
      if (prose.find()) state.put(prose.group(1), Boolean.TRUE);
    }
    Set<String> out = new LinkedHashSet<>();
    for (Map.Entry<String, Boolean> e : state.entrySet()) {
      if (Boolean.TRUE.equals(e.getValue())) out.add(e.getKey());
    }
    return out;
  }

  static Set<String> scanScrub(String text) {
    Set<String> l = new LinkedHashSet<>();
    Matcher m = Pattern.compile("room=([a-z]+) requires=scrub").matcher(text);
    while (m.find()) l.add(m.group(1));
    return l;
  }
}
