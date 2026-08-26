package cx;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Minimal JSON read/write for maps, lists, numbers, strings, booleans, null. */
public final class Jio {
    private Jio() {}

    public static Object load(Path path) throws IOException {
        String raw = Files.readString(path, StandardCharsets.UTF_8);
        return new Parser(raw).parseValue();
    }

    public static void save(Path path, Object value) throws IOException {
        Files.createDirectories(path.getParent());
        Files.writeString(path, stringify(value), StandardCharsets.UTF_8);
    }

    @SuppressWarnings("unchecked")
    public static Map<String, Object> asMap(Object o) {
        return (Map<String, Object>) o;
    }

    @SuppressWarnings("unchecked")
    public static List<Object> asList(Object o) {
        return (List<Object>) o;
    }

    public static String stringify(Object value) {
        StringBuilder sb = new StringBuilder();
        write(sb, value);
        return sb.toString();
    }

    private static void write(StringBuilder sb, Object value) {
        if (value == null) {
            sb.append("null");
        } else if (value instanceof String) {
            sb.append('"');
            for (char c : ((String) value).toCharArray()) {
                if (c == '"' || c == '\\') {
                    sb.append('\\').append(c);
                } else if (c == '\n') {
                    sb.append("\\n");
                } else {
                    sb.append(c);
                }
            }
            sb.append('"');
        } else if (value instanceof Boolean || value instanceof Number) {
            sb.append(value);
        } else if (value instanceof Map<?, ?> map) {
            sb.append('{');
            boolean first = true;
            for (Map.Entry<?, ?> e : map.entrySet()) {
                if (!first) {
                    sb.append(',');
                }
                first = false;
                write(sb, String.valueOf(e.getKey()));
                sb.append(':');
                write(sb, e.getValue());
            }
            sb.append('}');
        } else if (value instanceof List<?> list) {
            sb.append('[');
            boolean first = true;
            for (Object item : list) {
                if (!first) {
                    sb.append(',');
                }
                first = false;
                write(sb, item);
            }
            sb.append(']');
        } else {
            write(sb, String.valueOf(value));
        }
    }

    private static final class Parser {
        private final String s;
        private int i;

        Parser(String s) {
            this.s = s.trim();
        }

        Object parseValue() {
            skipWs();
            char c = s.charAt(i);
            if (c == '{') {
                return parseObject();
            }
            if (c == '[') {
                return parseArray();
            }
            if (c == '"') {
                return parseString();
            }
            if (c == 't' || c == 'f') {
                return parseBool();
            }
            if (c == 'n') {
                i += 4;
                return null;
            }
            return parseNumber();
        }

        private Map<String, Object> parseObject() {
            Map<String, Object> out = new LinkedHashMap<>();
            i++;
            skipWs();
            if (s.charAt(i) == '}') {
                i++;
                return out;
            }
            while (true) {
                skipWs();
                String key = parseString();
                skipWs();
                expect(':');
                Object val = parseValue();
                out.put(key, val);
                skipWs();
                if (s.charAt(i) == '}') {
                    i++;
                    break;
                }
                expect(',');
            }
            return out;
        }

        private List<Object> parseArray() {
            List<Object> out = new ArrayList<>();
            i++;
            skipWs();
            if (s.charAt(i) == ']') {
                i++;
                return out;
            }
            while (true) {
                out.add(parseValue());
                skipWs();
                if (s.charAt(i) == ']') {
                    i++;
                    break;
                }
                expect(',');
            }
            return out;
        }

        private String parseString() {
            expect('"');
            StringBuilder sb = new StringBuilder();
            while (i < s.length()) {
                char c = s.charAt(i++);
                if (c == '"') {
                    break;
                }
                if (c == '\\') {
                    char n = s.charAt(i++);
                    if (n == 'n') {
                        sb.append('\n');
                    } else {
                        sb.append(n);
                    }
                } else {
                    sb.append(c);
                }
            }
            return sb.toString();
        }

        private Object parseBool() {
            if (s.startsWith("true", i)) {
                i += 4;
                return Boolean.TRUE;
            }
            i += 5;
            return Boolean.FALSE;
        }

        private Number parseNumber() {
            int start = i;
            if (s.charAt(i) == '-') {
                i++;
            }
            while (i < s.length() && Character.isDigit(s.charAt(i))) {
                i++;
            }
            boolean frac = false;
            if (i < s.length() && s.charAt(i) == '.') {
                frac = true;
                i++;
                while (i < s.length() && Character.isDigit(s.charAt(i))) {
                    i++;
                }
            }
            String raw = s.substring(start, i);
            if (frac) {
                return Double.parseDouble(raw);
            }
            long v = Long.parseLong(raw);
            if (v >= Integer.MIN_VALUE && v <= Integer.MAX_VALUE) {
                return (int) v;
            }
            return v;
        }

        private void skipWs() {
            while (i < s.length() && Character.isWhitespace(s.charAt(i))) {
                i++;
            }
        }

        private void expect(char c) {
            if (s.charAt(i) != c) {
                throw new IllegalArgumentException("expected " + c + " at " + i);
            }
            i++;
        }
    }
}
