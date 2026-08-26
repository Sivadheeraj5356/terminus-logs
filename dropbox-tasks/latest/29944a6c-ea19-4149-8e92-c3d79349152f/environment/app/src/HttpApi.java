package gate;

import com.sun.net.httpserver.HttpExchange;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Instant;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public final class HttpApi {

    private static final byte[] HEALTH_BODY =
        "{\"status\":\"ok\"}".getBytes(StandardCharsets.UTF_8);

    private final String dbUrl;
    private final String standardPath;
    private final String standardSha256;

    public HttpApi(String dbUrl, String standardPath) throws Exception {
        this.dbUrl = dbUrl;
        this.standardPath = standardPath;
        this.standardSha256 = sha256Hex(Files.readAllBytes(Path.of(standardPath)));
    }

    public void health(HttpExchange ex) throws IOException {
        ex.getResponseHeaders().set("Content-Type", "application/json");
        ex.sendResponseHeaders(200, HEALTH_BODY.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(HEALTH_BODY);
        }
    }

    public void evaluate(HttpExchange ex) throws IOException {
        if (!"POST".equalsIgnoreCase(ex.getRequestMethod())) {
            respond(ex, 405, "{\"error\":\"method not allowed\"}");
            return;
        }
        String body;
        try (InputStream is = ex.getRequestBody()) {
            body = new String(is.readAllBytes(), StandardCharsets.UTF_8);
        }
        Map<String, Object> req;
        try {
            req = parseObject(body);
        } catch (Exception e) {
            respond(ex, 400, "{\"error\":\"malformed request\"}");
            return;
        }
        String repo = str(req.get("repo"));
        String tag = str(req.get("tag"));
        String evalStr = str(req.get("evaluationTime"));
        if (repo == null || tag == null || evalStr == null
            || req.size() != 3) {
            respond(ex, 400, "{\"error\":\"malformed request\"}");
            return;
        }
        Instant evaluationTime;
        try {
            evaluationTime = Instant.parse(evalStr);
        } catch (DateTimeParseException e) {
            respond(ex, 400, "{\"error\":\"malformed request\"}");
            return;
        }

        List<PolicyEngine.Reason> reasons = new ArrayList<>();

        // 1. Load compose model from the two files at the repo root.
        Map<String, Map<String, Object>> services;
        try {
            services = ComposeLoader.load(Path.of(repo));
        } catch (Exception e) {
            respond(ex, 500, "{\"error\":\"compose load failed: " + escape(e.getMessage()) + "\"}");
            return;
        }
        if (services.isEmpty()) {
            reasons.add(new PolicyEngine.Reason(
                "§24.9", "CDSS-SVC-024", ""));
        }

        // 2. Read approvals DB (read-only per request).
        Db.Data dbData;
        try (Db db = Db.open(dbUrl)) {
            dbData = db.readAll();
        } catch (Exception e) {
            respond(ex, 500, "{\"error\":\"db read failed: " + escape(e.getMessage()) + "\"}");
            return;
        }

        // 3. Read tag signature evidence.
        TagEvidence.Result tagResult = TagEvidence.forTag(Path.of(repo), tag);

        // 4. Read hook check.
        HookCheck.Result hookResult = HookCheck.check(Path.of(repo), standardSha256);

        // 5. Run policy engine over the full compose model.
        if (!services.isEmpty()) {
            reasons.addAll(PolicyEngine.evaluate(services, dbData, evaluationTime));
        }

        // 6. Hook reason (repository-level, empty service field).
        if (!hookResult.ok()) {
            reasons.add(new PolicyEngine.Reason(
                "§22.4", "CDSS-HOOK-022", ""));
        }

        // 7. Key approval.
        PolicyEngine.Reason keyReason = TagEvidence.approve(tagResult, dbData.keys());
        if (keyReason != null) {
            reasons.add(keyReason);
        }

        String json = Decision.render(reasons);
        respond(ex, 200, json);
    }

    private static void respond(HttpExchange ex, int status, String body) throws IOException {
        byte[] out = body.getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", "application/json");
        ex.sendResponseHeaders(status, out.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(out);
        }
    }

    private static String str(Object o) { return o instanceof String s ? s : null; }

    private static String sha256Hex(byte[] bytes) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] d = md.digest(bytes);
        StringBuilder sb = new StringBuilder(d.length * 2);
        for (byte b : d) sb.append(String.format(Locale.ROOT, "%02x", b & 0xff));
        return sb.toString();
    }

    private static String escape(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    // Minimal JSON parser sufficient for request bodies (objects containing
    // string / number / bool / null values). Rejects anything more elaborate.
    @SuppressWarnings("unchecked")
    static Map<String, Object> parseObject(String s) {
        int[] p = {0};
        skip(s, p);
        Object v = readValue(s, p);
        skip(s, p);
        if (p[0] != s.length()) throw new IllegalArgumentException("trailing garbage");
        if (!(v instanceof Map)) throw new IllegalArgumentException("expected object");
        return (Map<String, Object>) v;
    }

    private static Object readValue(String s, int[] p) {
        skip(s, p);
        if (p[0] >= s.length()) throw new IllegalArgumentException("truncated");
        char c = s.charAt(p[0]);
        if (c == '{') return readObject(s, p);
        if (c == '[') return readArray(s, p);
        if (c == '"') return readString(s, p);
        if (c == 't' || c == 'f') return readBool(s, p);
        if (c == 'n') { expect(s, p, "null"); return null; }
        return readNumber(s, p);
    }

    private static Map<String, Object> readObject(String s, int[] p) {
        Map<String, Object> out = new LinkedHashMap<>();
        p[0]++; // {
        skip(s, p);
        if (peek(s, p) == '}') { p[0]++; return out; }
        while (true) {
            skip(s, p);
            String key = readString(s, p);
            skip(s, p);
            if (peek(s, p) != ':') throw new IllegalArgumentException("expected :");
            p[0]++;
            Object v = readValue(s, p);
            out.put(key, v);
            skip(s, p);
            char c = peek(s, p);
            if (c == ',') { p[0]++; continue; }
            if (c == '}') { p[0]++; return out; }
            throw new IllegalArgumentException("expected , or }");
        }
    }

    private static List<Object> readArray(String s, int[] p) {
        List<Object> out = new ArrayList<>();
        p[0]++;
        skip(s, p);
        if (peek(s, p) == ']') { p[0]++; return out; }
        while (true) {
            out.add(readValue(s, p));
            skip(s, p);
            char c = peek(s, p);
            if (c == ',') { p[0]++; continue; }
            if (c == ']') { p[0]++; return out; }
            throw new IllegalArgumentException("expected , or ]");
        }
    }

    private static String readString(String s, int[] p) {
        if (peek(s, p) != '"') throw new IllegalArgumentException("expected \"");
        p[0]++;
        StringBuilder sb = new StringBuilder();
        while (p[0] < s.length()) {
            char c = s.charAt(p[0]++);
            if (c == '"') return sb.toString();
            if (c == '\\') {
                if (p[0] >= s.length()) throw new IllegalArgumentException("truncated escape");
                char e = s.charAt(p[0]++);
                switch (e) {
                    case '"' -> sb.append('"');
                    case '\\' -> sb.append('\\');
                    case '/' -> sb.append('/');
                    case 'n' -> sb.append('\n');
                    case 't' -> sb.append('\t');
                    case 'r' -> sb.append('\r');
                    case 'b' -> sb.append('\b');
                    case 'f' -> sb.append('\f');
                    case 'u' -> {
                        if (p[0] + 4 > s.length()) throw new IllegalArgumentException("bad \\u");
                        sb.append((char) Integer.parseInt(s.substring(p[0], p[0] + 4), 16));
                        p[0] += 4;
                    }
                    default -> throw new IllegalArgumentException("bad escape");
                }
            } else {
                sb.append(c);
            }
        }
        throw new IllegalArgumentException("unterminated string");
    }

    private static Object readNumber(String s, int[] p) {
        int start = p[0];
        while (p[0] < s.length() && "-+0123456789.eE".indexOf(s.charAt(p[0])) >= 0) p[0]++;
        String t = s.substring(start, p[0]);
        if (t.contains(".") || t.contains("e") || t.contains("E")) return Double.parseDouble(t);
        return Long.parseLong(t);
    }

    private static Object readBool(String s, int[] p) {
        if (s.startsWith("true", p[0])) { p[0] += 4; return Boolean.TRUE; }
        if (s.startsWith("false", p[0])) { p[0] += 5; return Boolean.FALSE; }
        throw new IllegalArgumentException("expected bool");
    }

    private static void skip(String s, int[] p) {
        while (p[0] < s.length() && Character.isWhitespace(s.charAt(p[0]))) p[0]++;
    }

    private static char peek(String s, int[] p) {
        return p[0] < s.length() ? s.charAt(p[0]) : '\0';
    }

    private static void expect(String s, int[] p, String want) {
        if (!s.startsWith(want, p[0])) throw new IllegalArgumentException("expected " + want);
        p[0] += want.length();
    }
}

