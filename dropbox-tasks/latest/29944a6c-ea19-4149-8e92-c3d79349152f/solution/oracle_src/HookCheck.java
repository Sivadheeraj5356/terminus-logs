package gate;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class HookCheck {

    private static final Pattern MARKER =
        Pattern.compile("^#\\s*CDSS-STANDARD-SHA256:\\s*([0-9a-fA-F]{64})\\s*$");

    private HookCheck() { }

    public static Result check(Path repoRoot, String standardSha256) {
        String hooksPath = readHooksPath(repoRoot.resolve(".git/config"));
        if (!".githooks".equals(hooksPath)) return new Result(false);

        Path prePush = repoRoot.resolve(hooksPath).resolve("pre-push");
        if (!Files.exists(prePush) || !Files.isExecutable(prePush)) {
            return new Result(false);
        }

        try {
            for (String line : Files.readAllLines(prePush)) {
                Matcher m = MARKER.matcher(line);
                if (m.matches()) {
                    return new Result(m.group(1).equalsIgnoreCase(standardSha256));
                }
            }
        } catch (Exception ignore) { }
        return new Result(false);
    }

    private static String readHooksPath(Path config) {
        if (!Files.exists(config)) return null;
        try {
            String section = null;
            for (String raw : Files.readAllLines(config)) {
                String line = raw.trim();
                if (line.isEmpty() || line.startsWith("#") || line.startsWith(";")) continue;
                if (line.startsWith("[") && line.endsWith("]")) {
                    section = line.substring(1, line.length() - 1).trim().toLowerCase();
                    continue;
                }
                if ("core".equals(section)) {
                    int eq = line.indexOf('=');
                    if (eq > 0) {
                        String key = line.substring(0, eq).trim().toLowerCase();
                        String val = line.substring(eq + 1).trim();
                        if (val.startsWith("\"") && val.endsWith("\"") && val.length() >= 2) {
                            val = val.substring(1, val.length() - 1);
                        }
                        if ("hookspath".equals(key)) return val;
                    }
                }
            }
        } catch (Exception ignore) { }
        return null;
    }

    public record Result(boolean ok) { }
}
