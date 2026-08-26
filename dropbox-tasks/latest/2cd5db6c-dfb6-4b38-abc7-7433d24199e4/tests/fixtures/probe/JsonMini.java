package probe;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Minimal JSON helpers for fixture ingest and report emit.
 * Sufficient for object/array/string/number/bool shapes used by this evaluator.
 */
public final class JsonMini {
    private JsonMini() {}

    public static Map<String, Object> parseObject(String text) {
        Parser p = new Parser(text.trim());
        Object v = p.parseValue();
        if (!(v instanceof Map)) {
            throw new IllegalArgumentException("expected object");
        }
        @SuppressWarnings("unchecked")
        Map<String, Object> m = (Map<String, Object>) v;
        return m;
    }

    public static String canonicalSessions(Map<String, String> sessions) {
        TreeMap<String, String> sorted = new TreeMap<>(sessions);
        StringBuilder sb = new StringBuilder();
        sb.append('{');
        boolean first = true;
        for (Map.Entry<String, String> e : sorted.entrySet()) {
            if (!first) {
                sb.append(',');
            }
            first = false;
            sb.append(quote(e.getKey()));
            sb.append(':');
            sb.append(quote(e.getValue()));
        }
        sb.append('}');
        return sb.toString();
    }

    public static String stringifyPretty(Object value) {
        StringBuilder sb = new StringBuilder();
        writePretty(sb, value, 0);
        sb.append('\n');
        return sb.toString();
    }

    @SuppressWarnings("unchecked")
    private static void writePretty(StringBuilder sb, Object value, int indent) {
        if (value == null) {
            sb.append("null");
        } else if (value instanceof Boolean || value instanceof Number) {
            sb.append(value.toString());
        } else if (value instanceof String) {
            sb.append(quote((String) value));
        } else if (value instanceof Map) {
            Map<String, Object> map = (Map<String, Object>) value;
            sb.append("{\n");
            boolean first = true;
            for (Map.Entry<String, Object> e : map.entrySet()) {
                if (!first) {
                    sb.append(",\n");
                }
                first = false;
                pad(sb, indent + 2);
                sb.append(quote(e.getKey()));
                sb.append(": ");
                writePretty(sb, e.getValue(), indent + 2);
            }
            sb.append('\n');
            pad(sb, indent);
            sb.append('}');
        } else if (value instanceof List) {
            List<Object> list = (List<Object>) value;
            sb.append("[\n");
            boolean first = true;
            for (Object item : list) {
                if (!first) {
                    sb.append(",\n");
                }
                first = false;
                pad(sb, indent + 2);
                writePretty(sb, item, indent + 2);
            }
            sb.append('\n');
            pad(sb, indent);
            sb.append(']');
        } else {
            sb.append(quote(String.valueOf(value)));
        }
    }

    private static void pad(StringBuilder sb, int n) {
        for (int i = 0; i < n; i++) {
            sb.append(' ');
        }
    }

    private static String quote(String s) {
        StringBuilder sb = new StringBuilder();
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\' -> sb.append("\\\\");
                case '"' -> sb.append("\\\"");
                case '\n' -> sb.append("\\n");
                case '\r' -> sb.append("\\r");
                case '\t' -> sb.append("\\t");
                default -> sb.append(c);
            }
        }
        sb.append('"');
        return sb.toString();
    }

    private static final class Parser {
        private final String s;
        private int i;

        Parser(String s) {
            this.s = s;
        }

        Object parseValue() {
            skipWs();
            if (i >= s.length()) {
                throw new IllegalArgumentException("unexpected end");
            }
            char c = s.charAt(i);
            if (c == '{') {
                return parseObj();
            }
            if (c == '[') {
                return parseArr();
            }
            if (c == '"') {
                return parseStr();
            }
            if (c == 't' || c == 'f') {
                return parseBool();
            }
            if (c == 'n') {
                return parseNull();
            }
            return parseNum();
        }

        private Map<String, Object> parseObj() {
            expect('{');
            Map<String, Object> m = new LinkedHashMap<>();
            skipWs();
            if (peek('}')) {
                i++;
                return m;
            }
            while (true) {
                skipWs();
                String key = parseStr();
                skipWs();
                expect(':');
                Object val = parseValue();
                m.put(key, val);
                skipWs();
                if (peek('}')) {
                    i++;
                    break;
                }
                expect(',');
            }
            return m;
        }

        private List<Object> parseArr() {
            expect('[');
            List<Object> list = new ArrayList<>();
            skipWs();
            if (peek(']')) {
                i++;
                return list;
            }
            while (true) {
                list.add(parseValue());
                skipWs();
                if (peek(']')) {
                    i++;
                    break;
                }
                expect(',');
            }
            return list;
        }

        private String parseStr() {
            expect('"');
            StringBuilder sb = new StringBuilder();
            while (i < s.length()) {
                char c = s.charAt(i++);
                if (c == '"') {
                    return sb.toString();
                }
                if (c == '\\') {
                    if (i >= s.length()) {
                        throw new IllegalArgumentException("bad escape");
                    }
                    char e = s.charAt(i++);
                    switch (e) {
                        case '"' -> sb.append('"');
                        case '\\' -> sb.append('\\');
                        case '/' -> sb.append('/');
                        case 'n' -> sb.append('\n');
                        case 'r' -> sb.append('\r');
                        case 't' -> sb.append('\t');
                        default -> sb.append(e);
                    }
                } else {
                    sb.append(c);
                }
            }
            throw new IllegalArgumentException("unterminated string");
        }

        private Object parseBool() {
            if (s.startsWith("true", i)) {
                i += 4;
                return Boolean.TRUE;
            }
            if (s.startsWith("false", i)) {
                i += 5;
                return Boolean.FALSE;
            }
            throw new IllegalArgumentException("bad bool");
        }

        private Object parseNull() {
            if (s.startsWith("null", i)) {
                i += 4;
                return null;
            }
            throw new IllegalArgumentException("bad null");
        }

        private Number parseNum() {
            int start = i;
            if (peek('-')) {
                i++;
            }
            while (i < s.length() && Character.isDigit(s.charAt(i))) {
                i++;
            }
            if (peek('.')) {
                i++;
                while (i < s.length() && Character.isDigit(s.charAt(i))) {
                    i++;
                }
                return Double.parseDouble(s.substring(start, i));
            }
            return Long.parseLong(s.substring(start, i));
        }

        private void skipWs() {
            while (i < s.length() && Character.isWhitespace(s.charAt(i))) {
                i++;
            }
        }

        private boolean peek(char c) {
            return i < s.length() && s.charAt(i) == c;
        }

        private void expect(char c) {
            skipWs();
            if (i >= s.length() || s.charAt(i) != c) {
                throw new IllegalArgumentException("expected " + c);
            }
            i++;
        }
    }
}
