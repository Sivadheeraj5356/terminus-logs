package com.spoolward;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

public final class Wire {

    public static final class BadWire extends RuntimeException {
        public BadWire(String m) {
            super(m);
        }
    }

    private final String s;
    private int i;

    private Wire(String s) {
        this.s = s;
        this.i = 0;
    }

    public static Object parse(String text) {
        Wire j = new Wire(text);
        j.ws();
        Object v = j.value();
        j.ws();
        if (j.i != text.length()) {
            throw new BadWire("tail");
        }
        return v;
    }

    private void ws() {
        while (i < s.length()) {
            char c = s.charAt(i);
            if (c == ' ' || c == '\t' || c == '\n' || c == '\r') {
                i++;
            } else {
                break;
            }
        }
    }

    private char peek() {
        if (i >= s.length()) {
            throw new BadWire("end");
        }
        return s.charAt(i);
    }

    private Object value() {
        char c = peek();
        if (c == '{') {
            return obj();
        }
        if (c == '[') {
            return arr();
        }
        if (c == '"') {
            return str();
        }
        if (c == 't') {
            lit("true");
            return Boolean.TRUE;
        }
        if (c == 'f') {
            lit("false");
            return Boolean.FALSE;
        }
        if (c == 'n') {
            lit("null");
            return null;
        }
        return num();
    }

    private void lit(String w) {
        if (!s.startsWith(w, i)) {
            throw new BadWire(w);
        }
        i += w.length();
    }

    private Map<String, Object> obj() {
        Map<String, Object> m = new TreeMap<>();
        i++;
        ws();
        if (peek() == '}') {
            i++;
            return m;
        }
        while (true) {
            ws();
            String k = str();
            ws();
            if (peek() != ':') {
                throw new BadWire("colon");
            }
            i++;
            ws();
            m.put(k, value());
            ws();
            char c = peek();
            if (c == ',') {
                i++;
                continue;
            }
            if (c == '}') {
                i++;
                return m;
            }
            throw new BadWire("obj");
        }
    }

    private List<Object> arr() {
        List<Object> a = new ArrayList<>();
        i++;
        ws();
        if (peek() == ']') {
            i++;
            return a;
        }
        while (true) {
            ws();
            a.add(value());
            ws();
            char c = peek();
            if (c == ',') {
                i++;
                continue;
            }
            if (c == ']') {
                i++;
                return a;
            }
            throw new BadWire("arr");
        }
    }

    private String str() {
        if (peek() != '"') {
            throw new BadWire("quote");
        }
        i++;
        StringBuilder b = new StringBuilder();
        while (true) {
            if (i >= s.length()) {
                throw new BadWire("string");
            }
            char c = s.charAt(i++);
            if (c == '"') {
                return b.toString();
            }
            if (c == '\\') {
                char e = s.charAt(i++);
                switch (e) {
                    case '"': b.append('"'); break;
                    case '\\': b.append('\\'); break;
                    case '/': b.append('/'); break;
                    case 'b': b.append('\b'); break;
                    case 'f': b.append('\f'); break;
                    case 'n': b.append('\n'); break;
                    case 'r': b.append('\r'); break;
                    case 't': b.append('\t'); break;
                    case 'u':
                        b.append((char) Integer.parseInt(s.substring(i, i + 4), 16));
                        i += 4;
                        break;
                    default: throw new BadWire("escape");
                }
            } else {
                b.append(c);
            }
        }
    }

    private Object num() {
        int start = i;
        boolean fp = false;
        if (i < s.length() && s.charAt(i) == '-') {
            i++;
        }
        while (i < s.length()) {
            char c = s.charAt(i);
            if (c >= '0' && c <= '9') {
                i++;
            } else if (c == '.' || c == 'e' || c == 'E' || c == '+' || c == '-') {
                fp = true;
                i++;
            } else {
                break;
            }
        }
        String t = s.substring(start, i);
        if (t.isEmpty() || t.equals("-")) {
            throw new BadWire("number");
        }
        if (fp) {
            return Double.parseDouble(t);
        }
        return Long.parseLong(t);
    }

    public static void write(Object v, StringBuilder b) {
        if (v == null) {
            b.append("null");
            return;
        }
        if (v instanceof String) {
            b.append('"');
            String t = (String) v;
            for (int k = 0; k < t.length(); k++) {
                char c = t.charAt(k);
                if (c == '"') {
                    b.append("\\\"");
                } else if (c == '\\') {
                    b.append("\\\\");
                } else if (c == '\n') {
                    b.append("\\n");
                } else if (c == '\r') {
                    b.append("\\r");
                } else if (c == '\t') {
                    b.append("\\t");
                } else if (c < 0x20) {
                    b.append(String.format("\\u%04x", (int) c));
                } else {
                    b.append(c);
                }
            }
            b.append('"');
            return;
        }
        if (v instanceof Long || v instanceof Boolean) {
            b.append(v.toString());
            return;
        }
        if (v instanceof Map) {
            Map<?, ?> m = (Map<?, ?>) v;
            TreeMap<String, Object> t = new TreeMap<>();
            for (Map.Entry<?, ?> e : m.entrySet()) {
                t.put((String) e.getKey(), e.getValue());
            }
            b.append('{');
            boolean first = true;
            for (Map.Entry<String, Object> e : t.entrySet()) {
                if (!first) {
                    b.append(',');
                }
                first = false;
                write(e.getKey(), b);
                b.append(':');
                write(e.getValue(), b);
            }
            b.append('}');
            return;
        }
        if (v instanceof List) {
            b.append('[');
            boolean first = true;
            for (Object e : (List<?>) v) {
                if (!first) {
                    b.append(',');
                }
                first = false;
                write(e, b);
            }
            b.append(']');
            return;
        }
        throw new BadWire("kind");
    }

    public static String canonical(Object v) {
        StringBuilder b = new StringBuilder();
        write(v, b);
        return b.toString();
    }

    public static String sha16(byte[] data) {
        try {
            MessageDigest d = MessageDigest.getInstance("SHA-256");
            byte[] h = d.digest(data);
            StringBuilder b = new StringBuilder();
            for (int k = 0; k < 8; k++) {
                b.append(String.format("%02x", h[k]));
            }
            return b.toString();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    public static String treeDigest(Path root) throws IOException {
        List<Path> files = new ArrayList<>();
        try (var stream = Files.walk(root)) {
            stream.filter(Files::isRegularFile).forEach(files::add);
        }
        files.sort(Comparator.comparing(p -> root.relativize(p).toString().replace('\\', '/')));
        try {
            MessageDigest d = MessageDigest.getInstance("SHA-256");
            for (Path p : files) {
                String rel = root.relativize(p).toString().replace('\\', '/');
                d.update(rel.getBytes(StandardCharsets.UTF_8));
                d.update((byte) 0);
                d.update(Files.readAllBytes(p));
                d.update((byte) 0);
            }
            byte[] h = d.digest();
            StringBuilder b = new StringBuilder();
            for (int k = 0; k < 8; k++) {
                b.append(String.format("%02x", h[k]));
            }
            return b.toString();
        } catch (IOException e) {
            throw e;
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
