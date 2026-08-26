package nxq.savelog;
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
    int limit = parts.length;
    if (!trailingNl) {
      // Discard truncated final line.
      limit = Math.max(0, parts.length - 1);
    }
    for (int i = 0; i < limit; i++) {
      if (!parts[i].isEmpty()) lines.add(parts[i]);
    }
  }

  public void validateCommittedHistory() {
    for (int i = 0; i < lines.size(); i++) {
      if (looksCorrupt(lines.get(i))) {
        throw new IllegalStateException("journal corruption at line " + (i + 1));
      }
    }
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
    if (next.isEmpty()) {
      Files.write(path, new byte[0]);
    } else {
      Files.write(path, (String.join("\n", next) + "\n").getBytes(StandardCharsets.UTF_8));
    }
  }

  public int size() { return lines.size(); }

  public static boolean looksCorrupt(String line) {
    if (line == null || line.isEmpty()) return true;
    String[] p = line.split("\\|", -1);
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
