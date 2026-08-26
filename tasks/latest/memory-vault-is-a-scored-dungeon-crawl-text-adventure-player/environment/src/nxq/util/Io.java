package nxq.util;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
public final class Io {
  private Io() {}
  public static String read(Path p) throws IOException {
    return Files.readString(p, StandardCharsets.UTF_8);
  }
  public static byte[] readBytes(Path p) throws IOException {
    return Files.readAllBytes(p);
  }
  public static void write(Path p, String s) throws IOException {
    Files.createDirectories(p.getParent());
    Files.writeString(p, s, StandardCharsets.UTF_8);
  }
  public static String sha16(byte[] data) throws Exception {
    MessageDigest md = MessageDigest.getInstance("SHA-256");
    byte[] d = md.digest(data);
    StringBuilder sb = new StringBuilder();
    for (int i = 0; i < 8; i++) sb.append(String.format("%02x", d[i]));
    return sb.toString();
  }
  public static String sha16(String s) throws Exception {
    return sha16(s.getBytes(StandardCharsets.UTF_8));
  }
  public static List<String> filteredMoves(Path moves) throws IOException {
    List<String> out = new ArrayList<>();
    for (String line : Files.readAllLines(moves, StandardCharsets.UTF_8)) {
      String t = line.trim();
      if (t.isEmpty() || t.startsWith("#")) continue;
      out.add(t);
    }
    return out;
  }
  public static String movesFp(List<String> lines) throws Exception {
    return sha16(String.join("\n", lines));
  }
}
