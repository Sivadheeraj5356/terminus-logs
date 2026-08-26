package common;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

public final class Io {
  private Io() {}

  public static String read(Path p) throws IOException {
    return Files.readString(p, StandardCharsets.UTF_8);
  }

  public static void write(Path p, String body) throws IOException {
    Files.createDirectories(p.getParent());
    Files.writeString(p, body, StandardCharsets.UTF_8);
  }

  public static String sha16(String s) throws Exception {
    MessageDigest md = MessageDigest.getInstance("SHA-256");
    byte[] dig = md.digest(s.getBytes(StandardCharsets.UTF_8));
    StringBuilder sb = new StringBuilder();
    for (int i = 0; i < 8; i++) sb.append(String.format("%02x", dig[i]));
    return sb.toString();
  }

  public static String fmt6(double x) {
    return String.format(Locale.US, "%.6f", x);
  }

  public static String fmt12(double x) {
    return String.format(Locale.US, "%.12f", x);
  }

  public static List<Path> listJson(Path dir) throws IOException {
    List<Path> out = new ArrayList<>();
    try (DirectoryStream<Path> ds = Files.newDirectoryStream(dir, "*.json")) {
      for (Path p : ds) out.add(p);
    }
    out.sort(Comparator.comparing(p -> p.getFileName().toString()));
    return out;
  }

  public static String jqString(String json, String key) {
    String needle = "\"" + key + "\"";
    int p = json.indexOf(needle);
    if (p < 0) return "";
    p = json.indexOf(':', p);
    p = json.indexOf('"', p);
    int e = json.indexOf('"', p + 1);
    return json.substring(p + 1, e);
  }

  public static double jqNumber(String json, String key) {
    String needle = "\"" + key + "\"";
    int p = json.indexOf(needle);
    if (p < 0) return 0.0;
    p = json.indexOf(':', p) + 1;
    while (p < json.length() && Character.isWhitespace(json.charAt(p))) p++;
    int e = p;
    while (e < json.length() && "0123456789.+-eE".indexOf(json.charAt(e)) >= 0) e++;
    return Double.parseDouble(json.substring(p, e));
  }
}
