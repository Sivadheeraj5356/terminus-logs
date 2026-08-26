import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.math.BigInteger;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

public final class Main {

    private static final class Frac {
        final BigInteger n;
        final BigInteger d;

        static final Frac ZERO = new Frac(BigInteger.ZERO, BigInteger.ONE);

        private Frac(BigInteger n, BigInteger d) {
            this.n = n;
            this.d = d;
        }

        static Frac of(BigInteger num, BigInteger den) {
            if (den.signum() == 0) {
                throw new ArithmeticException("zero denominator");
            }
            if (den.signum() < 0) {
                num = num.negate();
                den = den.negate();
            }
            BigInteger g = num.gcd(den);
            if (g.signum() != 0 && !g.equals(BigInteger.ONE)) {
                num = num.divide(g);
                den = den.divide(g);
            }
            return new Frac(num, den);
        }

        static Frac of(BigInteger num) {
            return new Frac(num, BigInteger.ONE);
        }

        boolean isZero() {
            return n.signum() == 0;
        }

        Frac add(Frac o) {
            return of(n.multiply(o.d).add(o.n.multiply(d)), d.multiply(o.d));
        }

        Frac sub(Frac o) {
            return of(n.multiply(o.d).subtract(o.n.multiply(d)), d.multiply(o.d));
        }

        Frac mul(Frac o) {
            return of(n.multiply(o.n), d.multiply(o.d));
        }

        Frac div(Frac o) {
            return of(n.multiply(o.d), d.multiply(o.n));
        }

        @Override
        public String toString() {
            return n.toString() + "/" + d.toString();
        }
    }

    private static final class Pending {
        final Map<Integer, BigInteger> comp;
        final BigInteger y;

        Pending(Map<Integer, BigInteger> comp, BigInteger y) {
            this.comp = comp;
            this.y = y;
        }
    }

    private static final class Bundle {
        int grace;
        long lamNum;
        long lamDen;
        int scale;
        int delay;
        List<Integer> featIds = new ArrayList<>();
        List<Map<Integer, BigInteger>> events = new ArrayList<>();
        Map<Integer, BigInteger> targets = new HashMap<>();
        Set<Integer> targetPresent = new HashSet<>();
        List<int[]> queries = new ArrayList<>();
        List<int[]> checkpoints = new ArrayList<>();
    }

    public static void main(String[] args) throws IOException {
        if (args.length < 1) {
            System.err.println("usage: solver <bundle_dir>");
            System.exit(2);
        }
        Bundle b = read(Paths.get(args[0]));
        System.out.println(run(b));
    }

    private static long gramKey(int i, int j) {
        return ((long) i << 32) | (j & 0xffffffffL);
    }

    private static Map<Integer, Frac> solve(
            List<Integer> active, Map<Long, BigInteger> gram,
            Map<Integer, BigInteger> bvec, Frac lam) {
        int dim = active.size();
        Map<Integer, Frac> out = new HashMap<>();
        if (dim == 0) {
            return out;
        }
        Frac[][] mat = new Frac[dim][dim];
        Frac[] rhs = new Frac[dim];
        for (int i = 0; i < dim; i++) {
            for (int j = 0; j < dim; j++) {
                BigInteger a = gram.getOrDefault(gramKey(active.get(i), active.get(j)), BigInteger.ZERO);
                Frac cell = Frac.of(a);
                if (i == j) {
                    cell = cell.add(lam);
                }
                mat[i][j] = cell;
            }
            rhs[i] = Frac.of(bvec.getOrDefault(active.get(i), BigInteger.ZERO));
        }
        for (int col = 0; col < dim; col++) {
            int piv = -1;
            for (int r = col; r < dim; r++) {
                if (!mat[r][col].isZero()) {
                    piv = r;
                    break;
                }
            }
            if (piv < 0) {
                continue;
            }
            Frac[] tmp = mat[col];
            mat[col] = mat[piv];
            mat[piv] = tmp;
            Frac t = rhs[col];
            rhs[col] = rhs[piv];
            rhs[piv] = t;
            Frac p = mat[col][col];
            for (int r = 0; r < dim; r++) {
                if (r != col && !mat[r][col].isZero()) {
                    Frac factor = mat[r][col].div(p);
                    for (int c = col; c < dim; c++) {
                        mat[r][c] = mat[r][c].sub(factor.mul(mat[col][c]));
                    }
                    rhs[r] = rhs[r].sub(factor.mul(rhs[col]));
                }
            }
        }
        for (int i = 0; i < dim; i++) {
            Frac w = mat[i][i].isZero() ? Frac.ZERO : rhs[i].div(mat[i][i]);
            out.put(active.get(i), w);
        }
        return out;
    }

    private static String run(Bundle b) {
        Map<Integer, List<Integer>> queriesAt = new HashMap<>();
        for (int[] q : b.queries) {
            queriesAt.computeIfAbsent(q[1], x -> new ArrayList<>()).add(q[0]);
        }
        Map<Integer, List<Integer>> ckptAt = new HashMap<>();
        for (int[] c : b.checkpoints) {
            ckptAt.computeIfAbsent(c[1], x -> new ArrayList<>()).add(c[0]);
        }
        Frac lam = Frac.of(BigInteger.valueOf(b.lamNum), BigInteger.valueOf(b.lamDen));

        List<Integer> active = new ArrayList<>();
        Set<Integer> activeSet = new HashSet<>();
        Map<Long, BigInteger> gram = new HashMap<>();
        Map<Integer, BigInteger> bvec = new HashMap<>();
        Map<Integer, Integer> absent = new HashMap<>();
        Map<Integer, Pending> pending = new HashMap<>();

        Map<Integer, Frac> predictions = new TreeMap<>();
        Map<Integer, String> checkpoints = new TreeMap<>();

        int n = b.events.size();
        for (int eid = 0; eid < n; eid++) {
            Map<Integer, BigInteger> present = b.events.get(eid);

            List<Integer> presentSorted = new ArrayList<>(present.keySet());
            presentSorted.sort(null);
            for (int fid : presentSorted) {
                if (!activeSet.contains(fid)) {
                    active.add(fid);
                    activeSet.add(fid);
                    bvec.put(fid, BigInteger.ZERO);
                    gram.put(gramKey(fid, fid), BigInteger.ZERO);
                    absent.put(fid, 0);
                }
            }

            for (int fid : new ArrayList<>(active)) {
                if (present.containsKey(fid)) {
                    absent.put(fid, 0);
                } else {
                    int a = absent.get(fid) + 1;
                    absent.put(fid, a);
                    if (a > b.grace) {
                        active.remove(Integer.valueOf(fid));
                        activeSet.remove(fid);
                        bvec.remove(fid);
                        absent.remove(fid);
                        List<Long> dead = new ArrayList<>();
                        for (long key : gram.keySet()) {
                            int ki = (int) (key >> 32);
                            int kj = (int) (key & 0xffffffffL);
                            if (ki == fid || kj == fid) {
                                dead.add(key);
                            }
                        }
                        for (long key : dead) {
                            gram.remove(key);
                        }
                        for (Pending rec : pending.values()) {
                            rec.comp.remove(fid);
                        }
                    }
                }
            }

            Map<Integer, BigInteger> x = new HashMap<>();
            for (int fid : presentSorted) {
                if (activeSet.contains(fid)) {
                    x.put(fid, present.get(fid));
                }
            }

            List<Integer> qs = queriesAt.get(eid);
            if (qs != null) {
                Map<Integer, Frac> w = solve(active, gram, bvec, lam);
                Frac yhat = Frac.ZERO;
                for (Map.Entry<Integer, BigInteger> e : x.entrySet()) {
                    Frac wf = w.getOrDefault(e.getKey(), Frac.ZERO);
                    yhat = yhat.add(wf.mul(Frac.of(e.getValue())));
                }
                for (int qid : qs) {
                    predictions.put(qid, yhat);
                }
            }

            Pending due = pending.remove(eid - b.delay);
            if (due != null) {
                List<Map.Entry<Integer, BigInteger>> items = new ArrayList<>(due.comp.entrySet());
                for (Map.Entry<Integer, BigInteger> ei : items) {
                    int fi = ei.getKey();
                    BigInteger xi = ei.getValue();
                    bvec.put(fi, bvec.getOrDefault(fi, BigInteger.ZERO).add(due.y.multiply(xi)));
                    for (Map.Entry<Integer, BigInteger> ej : items) {
                        int fj = ej.getKey();
                        long key = gramKey(fi, fj);
                        gram.put(key, gram.getOrDefault(key, BigInteger.ZERO).add(xi.multiply(ej.getValue())));
                    }
                }
            }

            if (b.targetPresent.contains(eid)) {
                pending.put(eid, new Pending(new HashMap<>(x), b.targets.get(eid)));
            }

            List<Integer> cs = ckptAt.get(eid);
            if (cs != null) {
                List<Integer> act = new ArrayList<>(active);
                act.sort(null);
                Map<Integer, Frac> w = solve(active, gram, bvec, lam);
                StringBuilder body = new StringBuilder();
                body.append("\"active\":[");
                for (int i = 0; i < act.size(); i++) {
                    if (i > 0) {
                        body.append(',');
                    }
                    body.append(act.get(i));
                }
                body.append("],\"gram\":[");
                boolean first = true;
                for (int i = 0; i < act.size(); i++) {
                    for (int j = i; j < act.size(); j++) {
                        if (!first) {
                            body.append(',');
                        }
                        first = false;
                        BigInteger v = gram.getOrDefault(gramKey(act.get(i), act.get(j)), BigInteger.ZERO);
                        body.append('[').append(act.get(i)).append(',').append(act.get(j))
                            .append(',').append(v.toString()).append(']');
                    }
                }
                body.append("],\"b\":[");
                for (int i = 0; i < act.size(); i++) {
                    if (i > 0) {
                        body.append(',');
                    }
                    BigInteger v = bvec.getOrDefault(act.get(i), BigInteger.ZERO);
                    body.append('[').append(act.get(i)).append(',').append(v.toString()).append(']');
                }
                body.append("],\"weights\":[");
                for (int i = 0; i < act.size(); i++) {
                    if (i > 0) {
                        body.append(',');
                    }
                    Frac wf = w.getOrDefault(act.get(i), Frac.ZERO);
                    body.append('[').append(act.get(i)).append(",\"").append(wf.toString()).append("\"]");
                }
                body.append(']');
                String snap = body.toString();
                for (int cid : cs) {
                    checkpoints.put(cid, snap);
                }
            }
        }

        StringBuilder sb = new StringBuilder();
        sb.append("{\"n_events\":").append(n);
        sb.append(",\"predictions\":[");
        boolean first = true;
        for (Map.Entry<Integer, Frac> e : predictions.entrySet()) {
            if (!first) {
                sb.append(',');
            }
            first = false;
            sb.append('[').append(e.getKey()).append(",\"").append(e.getValue().toString()).append("\"]");
        }
        sb.append("],\"checkpoints\":[");
        first = true;
        for (Map.Entry<Integer, String> e : checkpoints.entrySet()) {
            if (!first) {
                sb.append(',');
            }
            first = false;
            sb.append("{\"id\":").append(e.getKey()).append(',').append(e.getValue()).append('}');
        }
        sb.append("]}");
        return sb.toString();
    }

    private static BigInteger scaledInt(String text, int scale) {
        int digits = 0;
        int s = scale;
        while (s > 1) {
            s /= 10;
            digits++;
        }
        boolean negative = text.startsWith("-");
        if (negative) {
            text = text.substring(1);
        }
        int dot = text.indexOf('.');
        String intPart;
        String fracPart;
        if (dot < 0) {
            intPart = text;
            fracPart = "";
        } else {
            intPart = text.substring(0, dot);
            fracPart = text.substring(dot + 1);
        }
        if (fracPart.length() > digits) {
            throw new IllegalArgumentException("value " + text + " exceeds scale " + scale);
        }
        StringBuilder frac = new StringBuilder(fracPart);
        while (frac.length() < digits) {
            frac.append('0');
        }
        if (intPart.isEmpty()) {
            intPart = "0";
        }
        BigInteger value = new BigInteger(intPart + frac);
        return negative ? value.negate() : value;
    }

    private static Bundle read(Path dir) throws IOException {
        Bundle b = new Bundle();
        Map<String, String> cfg = new HashMap<>();
        for (String[] r : rows(dir.resolve("config.csv"))) {
            cfg.put(r[0], r[1]);
        }
        b.grace = Integer.parseInt(cfg.get("grace_G"));
        b.lamNum = Long.parseLong(cfg.get("ridge_lambda_num"));
        b.lamDen = Long.parseLong(cfg.get("ridge_lambda_den"));
        b.scale = Integer.parseInt(cfg.get("value_scale"));
        b.delay = Integer.parseInt(cfg.get("label_delay"));

        List<String[]> eventRows = rowsWithHeader(dir.resolve("events.csv"));
        String[] header = eventRows.get(0);
        for (int c = 2; c < header.length; c++) {
            b.featIds.add(Integer.parseInt(header[c].trim()));
        }
        for (int i = 1; i < eventRows.size(); i++) {
            String[] r = eventRows.get(i);
            Map<Integer, BigInteger> present = new HashMap<>();
            for (int c = 2; c < header.length; c++) {
                String cell = c < r.length ? r[c] : "";
                if (!cell.isEmpty()) {
                    present.put(b.featIds.get(c - 2), scaledInt(cell, b.scale));
                }
            }
            b.events.add(present);
        }

        for (String[] r : rows(dir.resolve("targets.csv"))) {
            int eid = Integer.parseInt(r[0]);
            if (r.length > 1 && !r[1].isEmpty()) {
                b.targets.put(eid, scaledInt(r[1], b.scale));
                b.targetPresent.add(eid);
            }
        }
        for (String[] r : rows(dir.resolve("queries.csv"))) {
            b.queries.add(new int[] {Integer.parseInt(r[0]), Integer.parseInt(r[1])});
        }
        for (String[] r : rows(dir.resolve("checkpoints.csv"))) {
            b.checkpoints.add(new int[] {Integer.parseInt(r[0]), Integer.parseInt(r[1])});
        }
        return b;
    }

    private static List<String[]> rows(Path p) throws IOException {
        List<String[]> out = new ArrayList<>();
        try (BufferedReader br = new BufferedReader(new FileReader(p.toFile()))) {
            String line = br.readLine();
            while ((line = br.readLine()) != null) {
                out.add(splitRow(line));
            }
        }
        return out;
    }

    private static List<String[]> rowsWithHeader(Path p) throws IOException {
        List<String[]> out = new ArrayList<>();
        try (BufferedReader br = new BufferedReader(new FileReader(p.toFile()))) {
            String line;
            while ((line = br.readLine()) != null) {
                out.add(splitRow(line));
            }
        }
        return out;
    }

    private static String[] splitRow(String line) {
        return line.split(",", -1);
    }

    private Main() {
    }
}
