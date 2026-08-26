package nxq.hazards;
import nxq.util.Io;
import java.nio.file.*;
import java.util.*;
import java.util.regex.*;
public final class Chambers {
  public final String generation;
  public final SortedSet<String> watches;
  public final SortedSet<String> leaks;
  private static Chambers CACHED;

  private Chambers(String g, SortedSet<String> w, SortedSet<String> l) {
    this.generation = g; this.watches = w; this.leaks = l;
  }

  public static Chambers load(Path root) throws Exception {
    if (CACHED != null) return CACHED;
    Path watch = root.resolve("traces/watch-chambers.log");
    Path scrub = root.resolve("traces/scrub-chambers.txt");
    Path policy = root.resolve("policy/packaging-note.txt");
    String pol = Files.exists(policy) ? Io.read(policy) : "";
    SortedSet<String> watches = new TreeSet<>();
    SortedSet<String> leaks = new TreeSet<>();
    if (!pol.contains("IGNORE_SENSOR_HAZARDS=1")) {
      watches.addAll(scanWatch(Io.read(watch)));
    }
    leaks.addAll(scanScrub(Io.read(scrub)));
    byte[] a = Io.readBytes(watch);
    byte[] b = Io.readBytes(scrub);
    byte[] joined = new byte[a.length + 1 + b.length];
    System.arraycopy(a, 0, joined, 0, a.length);
    joined[a.length] = '\n';
    System.arraycopy(b, 0, joined, a.length + 1, b.length);
    String gen = Io.sha16(joined);
    CACHED = new Chambers(gen, watches, leaks);
    return CACHED;
  }

  public static void clearCache() { CACHED = null; }

  static Set<String> scanWatch(String text) {
    Set<String> w = new LinkedHashSet<>();
    for (String line : text.split("\n")) {
      if (line.contains("kind=\"watch\"") && line.contains("room=\"")) {
        Matcher m = Pattern.compile("room=\"([a-z]+)\"").matcher(line);
        if (m.find()) w.add(m.group(1));
      }
      Matcher prose = Pattern.compile("The ([a-z]+) room is watched").matcher(line);
      if (prose.find()) w.add(prose.group(1));
    }
    return w;
  }

  static Set<String> scanScrub(String text) {
    Set<String> l = new LinkedHashSet<>();
    Matcher m = Pattern.compile("room=([a-z]+) requires=scrub").matcher(text);
    while (m.find()) l.add(m.group(1));
    return l;
  }
}
