// Full reference feature-bundle install-set resolver.
//
// Reads a JSON array of resolution cases from standard input and writes a JSON
// array of install-set results to standard output, one per case in order. Each
// case is {"registry": {name: [{version, yanked?, deps?}, ...]}, "requirements":
// {name: constraint}}. A result is {"install": [{name, version}, ...],
// "conflicts": [{packages, dependency}, ...]}. See README.md for the full
// resolution contract.

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

    // ---- version model ----

    static final class Ver {
        final int maj;
        final int min;
        final int pat;
        final String[] pre; // null => release

        Ver(int maj, int min, int pat, String[] pre) {
            this.maj = maj;
            this.min = min;
            this.pat = pat;
            this.pre = pre;
        }
    }

    static int atoi(String s) {
        try {
            return Integer.parseInt(s);
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    static Ver parseVersion(String s) {
        String core = s;
        String[] pre = null;
        int i = s.indexOf('-');
        if (i >= 0) {
            core = s.substring(0, i);
            pre = s.substring(i + 1).split("\\.", -1);
        }
        String[] parts = core.split("\\.", -1);
        return new Ver(atoi(parts[0]), atoi(parts[1]), atoi(parts[2]), pre);
    }

    static boolean isNum(String s) {
        if (s.isEmpty()) {
            return false;
        }
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c < '0' || c > '9') {
                return false;
            }
        }
        return true;
    }

    static int cmpPre(String[] a, String[] b) {
        int n = Math.max(a.length, b.length);
        for (int i = 0; i < n; i++) {
            if (i >= a.length) {
                return -1;
            }
            if (i >= b.length) {
                return 1;
            }
            String x = a[i];
            String y = b[i];
            boolean xn = isNum(x);
            boolean yn = isNum(y);
            if (xn && yn) {
                int xi = Integer.parseInt(x);
                int yi = Integer.parseInt(y);
                if (xi != yi) {
                    return xi < yi ? -1 : 1;
                }
            } else if (xn) {
                return -1;
            } else if (yn) {
                return 1;
            } else if (!x.equals(y)) {
                return x.compareTo(y) < 0 ? -1 : 1;
            }
        }
        return 0;
    }

    static int cmpVersion(Ver a, Ver b) {
        if (a.maj != b.maj) {
            return a.maj < b.maj ? -1 : 1;
        }
        if (a.min != b.min) {
            return a.min < b.min ? -1 : 1;
        }
        if (a.pat != b.pat) {
            return a.pat < b.pat ? -1 : 1;
        }
        String[] ap = a.pre;
        String[] bp = b.pre;
        if (ap == null && bp == null) {
            return 0;
        }
        if (ap == null) {
            return 1;
        }
        if (bp == null) {
            return -1;
        }
        return cmpPre(ap, bp);
    }

    static boolean coreEq(Ver a, Ver b) {
        return a.maj == b.maj && a.min == b.min && a.pat == b.pat;
    }

    // ---- constraints ----

    static final class Prim {
        final String op; // GTE GT LTE LT EQ
        final Ver v;

        Prim(String op, Ver v) {
            this.op = op;
            this.v = v;
        }
    }

    static final class Filled {
        final Ver v;
        final int arity;

        Filled(Ver v, int arity) {
            this.v = v;
            this.arity = arity;
        }
    }

    // fill parses 1-3 numeric components with an optional pre-release suffix.
    static Filled fill(String raw) {
        String[] pre = null;
        int i = raw.indexOf('-');
        if (i >= 0) {
            pre = raw.substring(i + 1).split("\\.", -1);
            raw = raw.substring(0, i);
        }
        String[] parts = raw.split("\\.", -1);
        int arity = parts.length;
        int[] full = {0, 0, 0};
        for (int k = 0; k < 3 && k < parts.length; k++) {
            full[k] = atoi(parts[k]);
        }
        return new Filled(new Ver(full[0], full[1], full[2], pre), arity);
    }

    static List<Prim> parseConstraint(String s) {
        s = s.strip();
        if (s.equals("*") || s.isEmpty() || s.equals("x")) {
            return List.of(new Prim("GTE", new Ver(0, 0, 0, null)));
        }
        char c0 = s.charAt(0);
        if (c0 == '^') {
            Filled f = fill(s.substring(1));
            Ver lo = f.v;
            Ver hi;
            switch (f.arity) {
                case 1:
                    hi = new Ver(lo.maj + 1, 0, 0, null);
                    break;
                case 2:
                    hi = (lo.maj == 0)
                        ? new Ver(0, lo.min + 1, 0, null)
                        : new Ver(lo.maj + 1, 0, 0, null);
                    break;
                default:
                    if (lo.maj == 0) {
                        hi = (lo.min == 0)
                            ? new Ver(0, 0, lo.pat + 1, null)
                            : new Ver(0, lo.min + 1, 0, null);
                    } else {
                        hi = new Ver(lo.maj + 1, 0, 0, null);
                    }
            }
            return List.of(new Prim("GTE", lo), new Prim("LT", hi));
        }
        if (c0 == '~') {
            Filled f = fill(s.substring(1));
            Ver lo = f.v;
            Ver hi = (f.arity == 1)
                ? new Ver(lo.maj + 1, 0, 0, null)
                : new Ver(lo.maj, lo.min + 1, 0, null);
            return List.of(new Prim("GTE", lo), new Prim("LT", hi));
        }
        String op;
        String rest;
        if (s.startsWith(">=")) {
            op = "GTE";
            rest = s.substring(2);
        } else if (s.startsWith("<=")) {
            op = "LTE";
            rest = s.substring(2);
        } else if (s.startsWith(">")) {
            op = "GT";
            rest = s.substring(1);
        } else if (s.startsWith("<")) {
            op = "LT";
            rest = s.substring(1);
        } else if (s.startsWith("=")) {
            op = "EQ";
            rest = s.substring(1);
        } else {
            throw new RuntimeException("bad constraint " + s);
        }
        if (rest.isEmpty()) {
            throw new RuntimeException("bad constraint " + s);
        }
        Ver v = fill(rest.strip()).v;
        return List.of(new Prim(op, v));
    }

    static boolean rangeNamesCore(List<Prim> rng, Ver v) {
        for (Prim p : rng) {
            if (p.v.pre != null && coreEq(p.v, v)) {
                return true;
            }
        }
        return false;
    }

    static boolean satPrim(Ver v, Prim p) {
        int c = cmpVersion(v, p.v);
        switch (p.op) {
            case "GTE":
                return c >= 0;
            case "GT":
                return c > 0;
            case "LTE":
                return c <= 0;
            case "LT":
                return c < 0;
            default:
                return c == 0;
        }
    }

    static boolean satRange(Ver v, List<Prim> rng) {
        if (v.pre != null && !rangeNamesCore(rng, v)) {
            return false;
        }
        for (Prim p : rng) {
            if (!satPrim(v, p)) {
                return false;
            }
        }
        return true;
    }

    static boolean isExactPin(List<Prim> rng, Ver v) {
        return rng.size() == 1 && rng.get(0).op.equals("EQ") && cmpVersion(rng.get(0).v, v) == 0;
    }

    // ---- selection ----

    static String selectVersion(String pkg, List<List<Prim>> ranges, Map<String, List<Entry>> reg) {
        Ver best = null;
        String bestVer = null;
        boolean have = false;
        List<Entry> entries = reg.get(pkg);
        if (entries != null) {
            for (Entry e : entries) {
                Ver v = parseVersion(e.version);
                boolean ok = true;
                for (List<Prim> r : ranges) {
                    if (!satRange(v, r)) {
                        ok = false;
                        break;
                    }
                }
                if (!ok) {
                    continue;
                }
                if (e.yanked) {
                    boolean pinned = false;
                    for (List<Prim> r : ranges) {
                        if (isExactPin(r, v)) {
                            pinned = true;
                            break;
                        }
                    }
                    if (!pinned) {
                        continue;
                    }
                }
                if (!have || cmpVersion(v, best) > 0) {
                    best = v;
                    bestVer = e.version;
                    have = true;
                }
            }
        }
        return have ? bestVer : null;
    }

    // ---- resolution ----

    static final class SrcRange {
        final String src;
        final boolean isTop;
        final List<Prim> rng;

        SrcRange(String src, boolean isTop, List<Prim> rng) {
            this.src = src;
            this.isTop = isTop;
            this.rng = rng;
        }
    }

    static Map<String, String> depsOf(String pkg, String version, Map<String, List<Entry>> reg) {
        List<Entry> entries = reg.get(pkg);
        if (entries != null) {
            for (Entry e : entries) {
                if (e.version.equals(version)) {
                    return e.deps;
                }
            }
        }
        return null;
    }

    static List<SrcRange> active(String pkg, Map<String, String> assignment,
                                 Map<String, String> requirements, Map<String, List<Entry>> reg) {
        List<SrcRange> out = new ArrayList<>();
        if (requirements.containsKey(pkg)) {
            out.add(new SrcRange("", true, parseConstraint(requirements.get(pkg))));
        }
        List<String> qs = new ArrayList<>(assignment.keySet());
        Collections.sort(qs);
        for (String q : qs) {
            Map<String, String> deps = depsOf(q, assignment.get(q), reg);
            if (deps == null) {
                continue;
            }
            List<String> dks = new ArrayList<>(deps.keySet());
            Collections.sort(dks);
            for (String dp : dks) {
                if (dp.equals(pkg)) {
                    out.add(new SrcRange(q, false, parseConstraint(deps.get(dp))));
                }
            }
        }
        return out;
    }

    static List<List<Prim>> rangesOf(List<SrcRange> acts) {
        List<List<Prim>> out = new ArrayList<>();
        for (SrcRange a : acts) {
            out.add(a.rng);
        }
        return out;
    }

    static List<String> requiredSet(Map<String, String> assignment, Map<String, Boolean> conflicted,
                                    Map<String, String> requirements, Map<String, List<Entry>> reg) {
        Set<String> set = new HashSet<>(requirements.keySet());
        for (String q : assignment.keySet()) {
            Map<String, String> deps = depsOf(q, assignment.get(q), reg);
            if (deps != null) {
                set.addAll(deps.keySet());
            }
        }
        List<String> out = new ArrayList<>();
        for (String k : set) {
            if (!Boolean.TRUE.equals(conflicted.get(k))) {
                out.add(k);
            }
        }
        Collections.sort(out);
        return out;
    }

    static boolean validAssigned(String pkg, String version, List<List<Prim>> ranges,
                                 Map<String, List<Entry>> reg) {
        Ver v = parseVersion(version);
        for (List<Prim> r : ranges) {
            if (!satRange(v, r)) {
                return false;
            }
        }
        List<Entry> entries = reg.get(pkg);
        if (entries != null) {
            for (Entry e : entries) {
                if (e.version.equals(version) && e.yanked) {
                    for (List<Prim> r : ranges) {
                        if (isExactPin(r, v)) {
                            return true;
                        }
                    }
                    return false;
                }
            }
        }
        return true;
    }

    static List<String> candidates(String pkg, List<List<Prim>> ranges, Map<String, List<Entry>> reg) {
        List<String> cs = new ArrayList<>();
        List<Entry> entries = reg.get(pkg);
        if (entries != null) {
            for (Entry e : entries) {
                Ver v = parseVersion(e.version);
                boolean ok = true;
                for (List<Prim> r : ranges) {
                    if (!satRange(v, r)) {
                        ok = false;
                        break;
                    }
                }
                if (!ok) {
                    continue;
                }
                if (e.yanked) {
                    boolean pinned = false;
                    for (List<Prim> r : ranges) {
                        if (isExactPin(r, v)) {
                            pinned = true;
                            break;
                        }
                    }
                    if (!pinned) {
                        continue;
                    }
                }
                cs.add(e.version);
            }
        }
        cs.sort((x, y) -> cmpVersion(parseVersion(y), parseVersion(x)));
        return cs;
    }

    static Map<String, String> copyStr(Map<String, String> m) {
        return new HashMap<>(m);
    }

    static Map<String, Boolean> copyBool(Map<String, Boolean> m) {
        return new HashMap<>(m);
    }

    static final class Outcome {
        final Map<String, String> assignment;
        final Map<String, Boolean> conflicted;

        Outcome(Map<String, String> assignment, Map<String, Boolean> conflicted) {
            this.assignment = assignment;
            this.conflicted = conflicted;
        }
    }

    // dfs looks for a fully consistent assignment (no conflicts). It returns the
    // first complete assignment found under highest-version-first ordering, i.e.
    // the max-version consistent install set, or null when no conflict-free
    // assignment exists.
    static Outcome dfs(Map<String, String> assignment, Map<String, Boolean> conflicted,
                       Map<String, String> requirements, Map<String, List<Entry>> reg, int[] budget) {
        budget[0]--;
        if (budget[0] < 0) {
            throw new RuntimeException("resolution budget exhausted");
        }
        List<String> req = requiredSet(assignment, conflicted, requirements, reg);
        String frontier = null;
        List<List<Prim>> frRanges = null;
        boolean found = false;
        for (String p : req) {
            List<List<Prim>> ranges = rangesOf(active(p, assignment, requirements, reg));
            if (assignment.containsKey(p) && validAssigned(p, assignment.get(p), ranges, reg)) {
                continue;
            }
            frontier = p;
            frRanges = ranges;
            found = true;
            break;
        }
        if (!found) {
            return new Outcome(copyStr(assignment), copyBool(conflicted));
        }
        List<String> cs = candidates(frontier, frRanges, reg);
        Map<String, String> base = copyStr(assignment);
        base.remove(frontier);
        for (String cv : cs) {
            Map<String, String> na = copyStr(base);
            na.put(frontier, cv);
            Outcome res = dfs(na, conflicted, requirements, reg, budget);
            if (res != null) {
                return res;
            }
        }
        return null;
    }

    // dfsMin runs only when no conflict-free assignment exists. It searches the
    // whole space of assignments, marking a bundle conflicted exactly when it has
    // no admissible satisfying version under its currently active constraints, and
    // keeps the outcome with the FEWEST conflicts. A greedy higher version of an
    // earlier bundle can introduce an avoidable second conflict that a lower
    // version of that same bundle would remove; because this explores every
    // version choice instead of returning at the first branch that marks something
    // conflicted, it backtracks those earlier choices and reports only the
    // conflicts that are truly unavoidable, yielding the maximal valid install
    // set. Among equally-minimal outcomes it keeps the first found under
    // highest-version-first ordering, so free choices still prefer higher versions.
    static void dfsMin(Map<String, String> assignment, Map<String, Boolean> conflicted,
                       Map<String, String> requirements, Map<String, List<Entry>> reg,
                       int[] budget, Outcome[] best) {
        budget[0]--;
        if (budget[0] < 0) {
            throw new RuntimeException("resolution budget exhausted");
        }
        // The conflict set only grows as the search descends, so a branch that has
        // already accumulated at least as many conflicts as the best complete
        // outcome can never improve on it.
        if (best[0] != null && conflicted.size() >= best[0].conflicted.size()) {
            return;
        }
        List<String> req = requiredSet(assignment, conflicted, requirements, reg);
        String frontier = null;
        List<List<Prim>> frRanges = null;
        boolean found = false;
        for (String p : req) {
            List<List<Prim>> ranges = rangesOf(active(p, assignment, requirements, reg));
            if (assignment.containsKey(p) && validAssigned(p, assignment.get(p), ranges, reg)) {
                continue;
            }
            frontier = p;
            frRanges = ranges;
            found = true;
            break;
        }
        if (!found) {
            Outcome cand = new Outcome(copyStr(assignment), copyBool(conflicted));
            if (best[0] == null || cand.conflicted.size() < best[0].conflicted.size()) {
                best[0] = cand;
            }
            return;
        }
        List<String> cs = candidates(frontier, frRanges, reg);
        Map<String, String> base = copyStr(assignment);
        base.remove(frontier);
        for (String cv : cs) {
            Map<String, String> na = copyStr(base);
            na.put(frontier, cv);
            dfsMin(na, conflicted, requirements, reg, budget, best);
        }
        if (cs.isEmpty()) {
            Map<String, Boolean> nc = copyBool(conflicted);
            nc.put(frontier, true);
            dfsMin(base, nc, requirements, reg, budget, best);
        }
    }

    // reachableClosure returns the set of bundles that must actually be installed:
    // starting from the top-level requirements and following the deps declared by
    // each chosen version transitively. A conflicted dependency is not installed
    // and does not activate its own deps, so it stops the traversal. Bundles
    // assigned by an abandoned search branch are never reached and are therefore
    // dropped.
    static Set<String> reachableClosure(Map<String, String> assignment, Map<String, String> requirements,
                                        Map<String, List<Entry>> reg, Map<String, Boolean> conflicted) {
        Set<String> reachable = new HashSet<>();
        List<String> stack = new ArrayList<>(requirements.keySet());
        while (!stack.isEmpty()) {
            String p = stack.remove(stack.size() - 1);
            if (reachable.contains(p) || Boolean.TRUE.equals(conflicted.get(p))) {
                continue;
            }
            String v = assignment.get(p);
            if (v == null) {
                continue;
            }
            reachable.add(p);
            Map<String, String> deps = depsOf(p, v, reg);
            if (deps != null) {
                for (String dp : deps.keySet()) {
                    if (!reachable.contains(dp)) {
                        stack.add(dp);
                    }
                }
            }
        }
        return reachable;
    }

    static List<String> conflictPair(String dep, Set<String> reachable,
                                     Map<String, String> assignment, Map<String, List<Entry>> reg) {
        Map<String, List<List<Prim>>> bySrc = new HashMap<>();
        List<String> srcs = new ArrayList<>();
        List<String> pkgs = new ArrayList<>(assignment.keySet());
        Collections.sort(pkgs);
        for (String p : pkgs) {
            if (!reachable.contains(p)) {
                continue;
            }
            Map<String, String> deps = depsOf(p, assignment.get(p), reg);
            if (deps != null && deps.containsKey(dep)) {
                if (!bySrc.containsKey(p)) {
                    srcs.add(p);
                }
                bySrc.computeIfAbsent(p, k -> new ArrayList<>()).add(parseConstraint(deps.get(dep)));
            }
        }
        Collections.sort(srcs);
        // A lone requiring bundle whose own constraint admits no version is itself
        // the jointly-unsatisfiable set: the conflict names just that one bundle.
        if (srcs.size() == 1) {
            if (selectVersion(dep, bySrc.get(srcs.get(0)), reg) == null) {
                List<String> one = new ArrayList<>();
                one.add(srcs.get(0));
                return one;
            }
            return new ArrayList<>();
        }
        for (int i = 0; i < srcs.size(); i++) {
            for (int j = i + 1; j < srcs.size(); j++) {
                List<List<Prim>> combined = new ArrayList<>(bySrc.get(srcs.get(i)));
                combined.addAll(bySrc.get(srcs.get(j)));
                if (selectVersion(dep, combined, reg) == null) {
                    List<String> pair = new ArrayList<>();
                    pair.add(srcs.get(i));
                    pair.add(srcs.get(j));
                    return pair;
                }
            }
        }
        if (srcs.size() >= 2) {
            List<String> pair = new ArrayList<>();
            pair.add(srcs.get(0));
            pair.add(srcs.get(1));
            return pair;
        }
        return srcs;
    }

    static Result resolve(Case c) {
        int[] budget = {200000};
        Outcome res = dfs(new HashMap<>(), new HashMap<>(), c.requirements, c.registry, budget);
        Map<String, String> assignment;
        Map<String, Boolean> conflicted = new HashMap<>();
        if (res == null) {
            budget[0] = 200000;
            Outcome[] best = new Outcome[1];
            dfsMin(new HashMap<>(), new HashMap<>(), c.requirements, c.registry, budget, best);
            assignment = best[0].assignment;
            conflicted = best[0].conflicted;
        } else {
            assignment = res.assignment;
        }

        // The install set is the reachable dependency closure of the requirements,
        // not every key that lingers in the final assignment map. Orphans left by
        // an abandoned branch are excluded here.
        Set<String> reachable = reachableClosure(assignment, c.requirements, c.registry, conflicted);

        Result out = new Result();
        List<String> names = new ArrayList<>(reachable);
        Collections.sort(names);
        for (String n : names) {
            Install ins = new Install();
            ins.name = n;
            ins.version = assignment.get(n);
            out.install.add(ins);
        }

        // A conflict record is emitted for each still-reachable dependency that
        // cannot be satisfied: its packages list names the requiring bundles whose
        // declared constraints cannot be jointly satisfied (one when a lone
        // requirer's own constraint is unsatisfiable, two when two requirers
        // conflict).
        List<String> deps = new ArrayList<>(conflicted.keySet());
        Collections.sort(deps);
        for (String d : deps) {
            List<String> pair = conflictPair(d, reachable, assignment, c.registry);
            if (pair.size() < 1) {
                continue;
            }
            Collections.sort(pair);
            Conflict cf = new Conflict();
            cf.packages = pair;
            cf.dependency = d;
            out.conflicts.add(cf);
        }
        out.conflicts.sort((x, y) -> {
            if (!x.dependency.equals(y.dependency)) {
                return x.dependency.compareTo(y.dependency);
            }
            return String.join(",", x.packages).compareTo(String.join(",", y.packages));
        });
        return out;
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
