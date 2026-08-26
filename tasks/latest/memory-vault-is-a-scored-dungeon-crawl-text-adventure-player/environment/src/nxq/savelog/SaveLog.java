package nxq.savelog;
import nxq.util.Io;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
public final class SaveLog {
  private final Path path;
  private final List<String> lines = new ArrayList<>();

  public SaveLog(Path path) { this.path = path; }

  public void load() throws IOException {
    lines.clear();
    if (!Files.exists(path)) return;
    byte[] raw = Files.readAllBytes(path);
    String text = new String(raw, StandardCharsets.UTF_8);
    if (text.isEmpty()) return;
    boolean trailingNl = text.endsWith("\n");
    String[] parts = text.split("\n", -1);
    int n = parts.length;
    if (!trailingNl && n > 0) {
    }
    for (int i = 0; i < n; i++) {
      if (i == n - 1 && !trailingNl && parts[i].isEmpty()) continue;
      if (i == n - 1 && !trailingNl) { lines.add(parts[i]); continue; }
      if (!parts[i].isEmpty() || i < n - 1) {
        if (!(i == n - 1 && parts[i].isEmpty() && trailingNl)) lines.add(parts[i]);
      }
    }
    while (!lines.isEmpty() && lines.get(lines.size() - 1).isEmpty()) lines.remove(lines.size() - 1);
  }

  public void validateCommittedHistory() {
  }

  public List<String> lines() { return lines; }

  public void append(String rec) throws IOException {
    lines.add(rec);
    Files.createDirectories(path.getParent());
    try (BufferedWriter bw = Files.newBufferedWriter(path, StandardCharsets.UTF_8,
        StandardOpenOption.CREATE, StandardOpenOption.APPEND)) {
      bw.write(rec);
      bw.write('\n');
    }
  }

  public void rewrite(List<String> next) throws IOException {
    lines.clear();
    lines.addAll(next);
    Files.createDirectories(path.getParent());
    Files.write(path, String.join("\n", next).concat(next.isEmpty() ? "" : "\n").getBytes(StandardCharsets.UTF_8));
  }

  public int size() { return lines.size(); }

  public static boolean looksCorrupt(String line) {
    if (line == null || line.isEmpty()) return true;
    String[] p = line.split("\\|", -1);
    if (p.length < 1) return true;
    switch (p[0]) {
      case "GEN": return p.length != 2;
      case "START": return p.length != 4;
      case "EVT": return p.length != 4;
      case "FIN": return p.length != 5;
      case "COMMIT": return p.length != 2;
      case "END": return p.length != 1;
      default: return true;
    }
  }
}
