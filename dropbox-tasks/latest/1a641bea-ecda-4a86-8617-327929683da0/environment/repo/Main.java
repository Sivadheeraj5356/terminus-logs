// Feature-bundle install-set resolver.
//
// Reads a JSON array of resolution cases from standard input and writes a JSON
// array of install-set results to standard output, one per case in order. A case
// is {"registry": {name: [{version, yanked?, deps?}, ...]}, "requirements":
// {name: constraint}} and a result is {"install": [{name, version}, ...],
// "conflicts": [{packages, dependency}, ...]}. See README.md for the resolution
// contract this program must follow.
//
// This starter is an early sketch: it walks the top-level requirements of a case
// with a rough reading of the constraint syntax and skips yanked and pre-release
// versions outright. Its output does not meet the contract in README.md.

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class Main {

    // ---- data model ----

    static final class Entry {
        String version;
        boolean yanked;
        Map<String, String> deps; // null when absent
    }

    static final class Case {
        Map<String, List<Entry>> registry = new LinkedHashMap<>();
        Map<String, String> requirements = new LinkedHashMap<>();
    }

    static final class Install {
        String name;
        String version;
    }

    static final class Conflict {
        List<String> packages;
        String dependency;
    }

    static final class Result {
        List<Install> install = new ArrayList<>();
        List<Conflict> conflicts = new ArrayList<>();
    }

    // ---- hand-rolled JSON reader ----

    static final class JsonParser {
        private final String s;
        private int i;

        JsonParser(String text) {
            this.s = text;
            this.i = 0;
        }

        Object parse() {
            skipWs();
            Object v = parseValue();
            skipWs();
            if (i < s.length()) {
                throw new RuntimeException("trailing data after JSON value");
            }
            return v;
        }

        private void skipWs() {
            while (i < s.length()) {
                char c = s.charAt(i);
                if (c == ' ' || c == '\t' || c == '\n' || c == '\r') {
                    i++;
                } else {
                    break;
                }
            }
        }

        private Object parseValue() {
            skipWs();
            if (i >= s.length()) {
                throw new RuntimeException("unexpected end of input");
            }
            char c = s.charAt(i);
            switch (c) {
                case '{':
                    return parseObject();
                case '[':
                    return parseArray();
                case '"':
                    return parseString();
                case 't':
                case 'f':
                    return parseBool();
                case 'n':
                    return parseNull();
                default:
                    return parseNumber();
            }
        }

        private Map<String, Object> parseObject() {
            Map<String, Object> m = new LinkedHashMap<>();
            i++; // consume '{'
            skipWs();
            if (i < s.length() && s.charAt(i) == '}') {
                i++;
                return m;
            }
            while (true) {
                skipWs();
                String k = parseString();
                skipWs();
                expect(':');
                Object v = parseValue();
                m.put(k, v);
                skipWs();
                char c = next();
                if (c == '}') {
                    break;
                }
                if (c != ',') {
                    throw new RuntimeException("expected ',' or '}' in object");
                }
            }
            return m;
        }

        private List<Object> parseArray() {
            List<Object> a = new ArrayList<>();
            i++; // consume '['
            skipWs();
            if (i < s.length() && s.charAt(i) == ']') {
                i++;
                return a;
            }
            while (true) {
                Object v = parseValue();
                a.add(v);
                skipWs();
                char c = next();
                if (c == ']') {
                    break;
                }
                if (c != ',') {
                    throw new RuntimeException("expected ',' or ']' in array");
                }
            }
            return a;
        }

        private String parseString() {
            expect('"');
            StringBuilder sb = new StringBuilder();
            while (true) {
                if (i >= s.length()) {
                    throw new RuntimeException("unterminated string");
                }
                char c = s.charAt(i++);
                if (c == '"') {
                    break;
                }
                if (c == '\\') {
                    char e = s.charAt(i++);
                    switch (e) {
                        case '"': sb.append('"'); break;
                        case '\\': sb.append('\\'); break;
                        case '/': sb.append('/'); break;
                        case 'b': sb.append('\b'); break;
                        case 'f': sb.append('\f'); break;
                        case 'n': sb.append('\n'); break;
                        case 'r': sb.append('\r'); break;
                        case 't': sb.append('\t'); break;
                        case 'u':
                            String hex = s.substring(i, i + 4);
                            i += 4;
                            sb.append((char) Integer.parseInt(hex, 16));
                            break;
                        default:
                            throw new RuntimeException("bad escape \\" + e);
                    }
                } else {
                    sb.append(c);
                }
            }
            return sb.toString();
        }

        private Boolean parseBool() {
            if (s.startsWith("true", i)) {
                i += 4;
                return Boolean.TRUE;
            }
            if (s.startsWith("false", i)) {
                i += 5;
                return Boolean.FALSE;
            }
            throw new RuntimeException("bad literal");
        }

        private Object parseNull() {
            if (s.startsWith("null", i)) {
                i += 4;
                return null;
            }
            throw new RuntimeException("bad literal");
        }

        private Object parseNumber() {
            int start = i;
            while (i < s.length()) {
                char c = s.charAt(i);
                if ((c >= '0' && c <= '9') || c == '-' || c == '+' || c == '.' || c == 'e' || c == 'E') {
                    i++;
                } else {
                    break;
                }
            }
            String num = s.substring(start, i);
            if (num.isEmpty()) {
                throw new RuntimeException("invalid number");
            }
            if (num.contains(".") || num.contains("e") || num.contains("E")) {
                return Double.parseDouble(num);
            }
            return Long.parseLong(num);
        }

        private void expect(char c) {
            skipWs();
            if (i >= s.length() || s.charAt(i) != c) {
                throw new RuntimeException("expected '" + c + "'");
            }
            i++;
        }

        private char next() {
            if (i >= s.length()) {
                throw new RuntimeException("unexpected end of input");
            }
            return s.charAt(i++);
        }
    }

    // ---- input extraction ----

    @SuppressWarnings("unchecked")
    static Case toCase(Map<String, Object> m) {
        Case c = new Case();
        Object reg = m.get("registry");
        if (reg instanceof Map<?, ?> rm) {
            for (Map.Entry<?, ?> e : rm.entrySet()) {
                List<Entry> list = new ArrayList<>();
                for (Object o : (List<Object>) e.getValue()) {
                    Map<?, ?> em = (Map<?, ?>) o;
                    Entry en = new Entry();
                    en.version = (String) em.get("version");
                    Object y = em.get("yanked");
                    en.yanked = (y instanceof Boolean b) && b;
                    Object d = em.get("deps");
                    if (d instanceof Map<?, ?> dm) {
                        en.deps = new LinkedHashMap<>();
                        for (Map.Entry<?, ?> de : dm.entrySet()) {
                            en.deps.put((String) de.getKey(), (String) de.getValue());
                        }
                    }
                    list.add(en);
                }
                c.registry.put((String) e.getKey(), list);
            }
        }
        Object req = m.get("requirements");
        if (req instanceof Map<?, ?> qm) {
            for (Map.Entry<?, ?> e : qm.entrySet()) {
                c.requirements.put((String) e.getKey(), (String) e.getValue());
            }
        }
        return c;
    }

    // ---- hand-rolled JSON writer ----

    static void writeString(StringBuilder sb, String s) {
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        sb.append('"');
    }

    static String serialize(List<Result> results) {
        StringBuilder sb = new StringBuilder();
        sb.append('[');
        for (int i = 0; i < results.size(); i++) {
            if (i > 0) {
                sb.append(',');
            }
            Result r = results.get(i);
            sb.append("{\"install\":[");
            for (int j = 0; j < r.install.size(); j++) {
                if (j > 0) {
                    sb.append(',');
                }
                Install ins = r.install.get(j);
                sb.append("{\"name\":");
                writeString(sb, ins.name);
                sb.append(",\"version\":");
                writeString(sb, ins.version);
                sb.append('}');
            }
            sb.append("],\"conflicts\":[");
            for (int j = 0; j < r.conflicts.size(); j++) {
                if (j > 0) {
                    sb.append(',');
                }
                Conflict cf = r.conflicts.get(j);
                sb.append("{\"packages\":[");
                for (int k = 0; k < cf.packages.size(); k++) {
                    if (k > 0) {
                        sb.append(',');
                    }
                    writeString(sb, cf.packages.get(k));
                }
                sb.append("],\"dependency\":");
                writeString(sb, cf.dependency);
                sb.append('}');
            }
            sb.append("]}");
        }
        sb.append(']');
        return sb.toString();
    }

    // ---- naive resolver (starter) ----

    // naiveVer parses "maj.min.patch" ignoring any pre-release tag; the returned
    // fourth slot is 1 when the version is a plain three-part release string.
    static int[] naiveVer(String s) {
        if (s.indexOf('-') >= 0) {
            return new int[]{0, 0, 0, 0};
        }
        String[] parts = s.split("\\.", -1);
        if (parts.length != 3) {
            return new int[]{0, 0, 0, 0};
        }
        int[] out = new int[]{0, 0, 0, 1};
        for (int i = 0; i < 3; i++) {
            try {
                out[i] = Integer.parseInt(parts[i]);
            } catch (NumberFormatException e) {
                return new int[]{0, 0, 0, 0};
            }
        }
        return out;
    }

    static int cmp3(int[] a, int[] b) {
        for (int i = 0; i < 3; i++) {
            if (a[i] != b[i]) {
                return a[i] < b[i] ? -1 : 1;
            }
        }
        return 0;
    }

    // naiveSat matches a version against the "*", "=x.y.z" and ">=x.y.z" forms.
    static boolean naiveSat(int[] v, String constraint) {
        String c = constraint.strip();
        if (c.isEmpty() || c.equals("*")) {
            return true;
        }
        if (c.startsWith(">=")) {
            int[] b = naiveVer(c.substring(2).strip());
            if (b[3] == 1) {
                return cmp3(v, b) >= 0;
            }
            return true;
        }
        if (c.startsWith("=")) {
            int[] b = naiveVer(c.substring(1).strip());
            if (b[3] == 1) {
                return cmp3(v, b) == 0;
            }
            return true;
        }
        return true;
    }

    static Result resolve(Case c) {
        Result res = new Result();
        List<String> names = new ArrayList<>(c.requirements.keySet());
        Collections.sort(names);
        for (String name : names) {
            String constraint = c.requirements.get(name);
            int[] best = {0, 0, 0};
            String bestVer = null;
            boolean have = false;
            List<Entry> entries = c.registry.get(name);
            if (entries != null) {
                for (Entry e : entries) {
                    if (e.yanked) {
                        continue;
                    }
                    int[] v = naiveVer(e.version);
                    if (v[3] != 1) {
                        continue;
                    }
                    if (!naiveSat(v, constraint)) {
                        continue;
                    }
                    if (!have || cmp3(v, best) > 0) {
                        best = new int[]{v[0], v[1], v[2]};
                        bestVer = e.version;
                        have = true;
                    }
                }
            }
            if (have) {
                Install ins = new Install();
                ins.name = name;
                ins.version = bestVer;
                res.install.add(ins);
            }
        }
        return res;
    }

    // ---- entry point ----

    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws IOException {
        byte[] data = System.in.readAllBytes();
        String text = new String(data, StandardCharsets.UTF_8);
        List<Result> results = new ArrayList<>();
        try {
            Object parsed = new JsonParser(text).parse();
            for (Object o : (List<Object>) parsed) {
                Case c = toCase((Map<String, Object>) o);
                results.add(resolve(c));
            }
        } catch (RuntimeException ex) {
            System.err.println("invalid json input: " + ex.getMessage());
            System.exit(1);
            return;
        }
        System.out.println(serialize(results));
    }
}
