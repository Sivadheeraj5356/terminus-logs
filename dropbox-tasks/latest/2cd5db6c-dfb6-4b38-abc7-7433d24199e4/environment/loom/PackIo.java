package loom;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Shared helpers for packaging stage I/O. */
public final class PackIo {
    private PackIo() {}

    private static final Pattern NUM = Pattern.compile("\"(\\w+)\"\\s*:\\s*(\\d+)");
    private static final Pattern STR = Pattern.compile("\"(\\w+)\"\\s*:\\s*\"([^\"]*)\"");

    public static long num(String text, String key) {
        Matcher m = NUM.matcher(text);
        while (m.find()) {
            if (key.equals(m.group(1))) {
                return Long.parseLong(m.group(2));
            }
        }
        return 0L;
    }

    public static String str(String text, String key) {
        Matcher m = STR.matcher(text);
        while (m.find()) {
            if (key.equals(m.group(1))) {
                return m.group(2);
            }
        }
        return "";
    }

    public static void write(Path p, String s) throws IOException {
        Files.writeString(p, s, StandardCharsets.UTF_8);
    }

    public static String read(Path p) throws IOException {
        return Files.readString(p, StandardCharsets.UTF_8);
    }

    public static String readTrim(Path p) throws IOException {
        return Files.readString(p, StandardCharsets.UTF_8).trim();
    }

    public static void ensureDir(Path p) throws IOException {
        Files.createDirectories(p);
    }
}
