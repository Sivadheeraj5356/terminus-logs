import java.io.IOException;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

/**
 * Histogram mode consolidation profiler. See /app/SPEC.md for the full
 * contract; this oracle implements it exactly with long arithmetic only.
 */
public final class Main {

    private static final long POS_LIMIT = 1_000_000_000L;
    private static final long COUNT_LIMIT = 1_000_000_000L;

    public static void main(String[] args) {
        if (args.length != 1) {
            System.exit(2);
        }
        byte[] raw;
        try {
            raw = Files.readAllBytes(Paths.get(args[0]));
        } catch (IOException e) {
            System.exit(1);
            return;
        }
        String text;
        try {
            text = StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(raw)).toString();
        } catch (CharacterCodingException e) {
            System.exit(3);
            return;
        }

        // Parse + schema in one physical-order pass.
        TreeMap<Long, Long> bins = new TreeMap<>();
        Long radius = null;
        Long sharp = null;
        Map<Long, Long> guardCap = new HashMap<>();
        List<long[]> guardLines = new ArrayList<>(); // [pos, lineNo] in physical order
        List<long[]> linkLines = new ArrayList<>(); // [pos1, pos2, lineNo] in physical order
        Set<String> linkedPairSeen = new HashSet<>(); // key = min+","+max
        String[] lines = text.split("\n", -1);
        for (int idx = 0; idx < lines.length; idx++) {
            int lineNo = idx + 1;
            String line = lines[idx];
            if (line.endsWith("\r")) {
                line = line.substring(0, line.length() - 1);
            }
            String trimmed = line.trim();
            if (trimmed.isEmpty() || trimmed.startsWith("#")) {
                continue;
            }
            String[] f = trimmed.split("[ \t]+");
            switch (f[0]) {
                case "b": {
                    if (f.length != 3) {
                        System.exit(3);
                    }
                    long pos = parseInt(f[1]);
                    long count = parseInt(f[2]);
                    if (pos < -POS_LIMIT || pos > POS_LIMIT) {
                        malformed("bad_pos", lineNo);
                    }
                    if (count < 1 || count > COUNT_LIMIT) {
                        malformed("bad_count", lineNo);
                    }
                    if (bins.containsKey(pos)) {
                        malformed("duplicate_pos", lineNo);
                    }
                    bins.put(pos, count);
                    break;
                }
                case "radius": {
                    if (f.length != 2) {
                        System.exit(3);
                    }
                    long h = parseInt(f[1]);
                    if (h < 1 || h > 50) {
                        malformed("bad_radius", lineNo);
                    }
                    if (radius != null) {
                        malformed("duplicate_radius", lineNo);
                    }
                    radius = h;
                    break;
                }
                case "sharp": {
                    if (f.length != 2) {
                        System.exit(3);
                    }
                    long q = parseInt(f[1]);
                    if (q < 1 || q > 1_000_000L) {
                        malformed("bad_sharp", lineNo);
                    }
                    if (sharp != null) {
                        malformed("duplicate_sharp", lineNo);
                    }
                    sharp = q;
                    break;
                }
                case "guard": {
                    if (f.length != 3) {
                        System.exit(3);
                    }
                    long gpos = parseInt(f[1]);
                    long gcap = parseInt(f[2]);
                    if (gpos < -POS_LIMIT || gpos > POS_LIMIT) {
                        malformed("bad_guard_pos", lineNo);
                    }
                    if (gcap < 1 || gcap > COUNT_LIMIT) {
                        malformed("bad_guard_cap", lineNo);
                    }
                    if (guardCap.containsKey(gpos)) {
                        malformed("duplicate_guard", lineNo);
                    }
                    guardCap.put(gpos, gcap);
                    guardLines.add(new long[]{gpos, lineNo});
                    break;
                }
                case "link": {
                    if (f.length != 3) {
                        System.exit(3);
                    }
                    long p1 = parseInt(f[1]);
                    long p2 = parseInt(f[2]);
                    if (p1 < -POS_LIMIT || p1 > POS_LIMIT || p2 < -POS_LIMIT || p2 > POS_LIMIT) {
                        malformed("bad_link_pos", lineNo);
                    }
                    if (p1 == p2) {
                        malformed("link_self", lineNo);
                    }
                    String pairKey = Math.min(p1, p2) + "," + Math.max(p1, p2);
                    if (linkedPairSeen.contains(pairKey)) {
                        malformed("duplicate_link", lineNo);
                    }
                    linkedPairSeen.add(pairKey);
                    linkLines.add(new long[]{p1, p2, lineNo});
                    break;
                }
                default:
                    System.exit(3);
            }
        }
        if (bins.isEmpty()) {
            malformed("no_bins", 0);
        }
        for (long[] g : guardLines) {
            if (!bins.containsKey(g[0])) {
                malformed("unknown_guard", (int) g[1]);
            }
        }
        for (long[] lk : linkLines) {
            if (!bins.containsKey(lk[0]) || !bins.containsKey(lk[1])) {
                malformed("unknown_link", (int) lk[2]);
            }
        }
        for (long[] lk : linkLines) {
            if (!guardCap.containsKey(lk[0]) || !guardCap.containsKey(lk[1])) {
                malformed("link_unguarded", (int) lk[2]);
            }
        }

        // ---- Linked guard groups: union-find over guarded positions. -----
        Map<Long, Long> groupParent = new HashMap<>();
        for (Long gp : guardCap.keySet()) {
            groupParent.put(gp, gp);
        }
        for (long[] lk : linkLines) {
            union(groupParent, lk[0], lk[1]);
        }
        Map<Long, Long> groupCap = new HashMap<>(); // root -> min cap among members
        for (Map.Entry<Long, Long> e : guardCap.entrySet()) {
            long root = find(groupParent, e.getKey());
            groupCap.merge(root, e.getValue(), Math::min);
        }
        long h = radius == null ? 2L : radius;
        long q = sharp == null ? 4L : sharp;

        // ---- Climb: every bin ascends to its mode. -----------------------
        long[] pos = new long[bins.size()];
        long[] cnt = new long[bins.size()];
        int n = 0;
        for (Map.Entry<Long, Long> e : bins.entrySet()) {
            pos[n] = e.getKey();
            cnt[n] = e.getValue();
            n++;
        }
        long totalMass = 0;
        for (long c : cnt) {
            totalMass += c;
        }
        int[] target = new int[n];
        for (int i = 0; i < n; i++) {
            target[i] = climbTarget(pos, cnt, i, h);
        }
        int[] endpoint = new int[n];
        for (int i = 0; i < n; i++) {
            int cur = i;
            while (target[cur] != cur) {
                cur = target[cur];
            }
            endpoint[i] = cur;
        }
        TreeMap<Long, Long> basinMass = new TreeMap<>();
        for (int i = 0; i < n; i++) {
            long modePos = pos[endpoint[i]];
            basinMass.merge(modePos, cnt[i], Long::sum);
        }
        int rawModes = basinMass.size();

        // ---- Consolidation rounds. ---------------------------------------
        Map<Long, Long> absorbed = new HashMap<>();
        Set<Long> saturated = new HashSet<>();
        long rounds = 0;
        long thresholdFinal;
        while (true) {
            long m = basinMass.size();
            long bar = totalMass / (q * m);
            thresholdFinal = bar;
            // Emergent majority saturation (section 4c): judged on the mass each
            // surviving mode carries INTO this round, a mode holding an outright
            // majority of the total mass (2*mass >= M) latches saturated for this
            // round and every later round. Written with a subtraction so the
            // doubling can never overflow.
            for (Map.Entry<Long, Long> e : basinMass.entrySet()) {
                if (e.getValue() >= totalMass - e.getValue()) {
                    saturated.add(e.getKey());
                }
            }
            List<Long> dissolved = new ArrayList<>();
            for (Map.Entry<Long, Long> e : basinMass.entrySet()) {
                if (e.getValue() < bar) {
                    dissolved.add(e.getKey());
                }
            }
            if (dissolved.isEmpty()) {
                break;
            }
            Set<Long> dissolvedSet = new HashSet<>(dissolved);
            List<Long> survivors = new ArrayList<>();
            for (Long mode : basinMass.keySet()) {
                if (!dissolvedSet.contains(mode)) {
                    survivors.add(mode);
                }
            }
            Map<Long, Long> gains = new HashMap<>();
            Map<Long, Long> roundAbsorptions = new HashMap<>(); // key = group root
            for (Long d : dissolved) {
                long best = pickReceiver(survivors, d, guardCap, groupParent, groupCap, absorbed, saturated, false);
                boolean exhaustedForAll = (best == Long.MIN_VALUE);
                if (exhaustedForAll) {
                    best = pickReceiver(survivors, d, guardCap, groupParent, groupCap, absorbed, saturated, true);
                }
                gains.merge(best, basinMass.get(d), Long::sum);
                if (guardCap.containsKey(best)) {
                    long root = find(groupParent, best);
                    roundAbsorptions.merge(root, 1L, Long::sum);
                }
            }
            for (Long d : dissolved) {
                basinMass.remove(d);
            }
            for (Map.Entry<Long, Long> g : gains.entrySet()) {
                basinMass.merge(g.getKey(), g.getValue(), Long::sum);
            }
            for (Map.Entry<Long, Long> a : roundAbsorptions.entrySet()) {
                absorbed.merge(a.getKey(), a.getValue(), Long::sum);
            }
            rounds++;
        }

        // ---- Converged figures. ------------------------------------------
        List<Long> modes = new ArrayList<>(basinMass.keySet());
        long heaviest = modes.get(0);
        long heaviestMass = basinMass.get(heaviest);
        for (Long m2 : modes) {
            long mass = basinMass.get(m2);
            if (mass > heaviestMass) {
                heaviest = m2;
                heaviestMass = mass;
            }
        }
        long concentration = heaviestMass * 100L / totalMass;
        List<Long> gaps = new ArrayList<>();
        for (int i = 1; i < modes.size(); i++) {
            gaps.add(modes.get(i) - modes.get(i - 1));
        }
        long gapMin = 0;
        long gapMax = 0;
        long gapMedian = 0;
        if (!gaps.isEmpty()) {
            List<Long> sortedGaps = new ArrayList<>(gaps);
            sortedGaps.sort(Long::compare);
            gapMin = sortedGaps.get(0);
            gapMax = sortedGaps.get(sortedGaps.size() - 1);
            int g = sortedGaps.size();
            gapMedian = g % 2 == 1 ? sortedGaps.get(g / 2) : sortedGaps.get(g / 2 - 1);
        }
        long rawSpan = pos[n - 1] - pos[0];

        StringBuilder sb = new StringBuilder();
        sb.append("{\"n\":").append(n);
        sb.append(",\"total_mass\":").append(totalMass);
        sb.append(",\"raw_modes\":").append(rawModes);
        sb.append(",\"mode_count\":").append(modes.size());
        sb.append(",\"rounds\":").append(rounds);
        sb.append(",\"threshold_final\":").append(thresholdFinal);
        sb.append(",\"mode_positions\":[");
        for (int i = 0; i < modes.size(); i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(modes.get(i));
        }
        sb.append("],\"fractions\":[");
        for (int i = 0; i < modes.size(); i++) {
            if (i > 0) {
                sb.append(',');
            }
            long mass = basinMass.get(modes.get(i));
            long g = gcd(mass, totalMass);
            sb.append('"').append(mass / g).append('/').append(totalMass / g).append('"');
        }
        sb.append("],\"heaviest_mode\":").append(heaviest);
        sb.append(",\"concentration_pct\":").append(concentration);
        sb.append(",\"gap_min\":").append(gapMin);
        sb.append(",\"gap_median\":").append(gapMedian);
        sb.append(",\"gap_max\":").append(gapMax);
        sb.append(",\"raw_span\":").append(rawSpan);
        sb.append('}');
        emit(sb.toString());
        System.exit(0);
    }

    /**
     * Nearest survivor to d by distance then position. When ignoreGuards is
     * false a survivor is skipped if it is barred, and a survivor is barred
     * when EITHER its LINK GROUP has already reached its shared cap (section
     * 4b: the group's cap is the min of its members' own caps, and absorptions
     * by any member count against the one shared total) OR it has latched
     * saturated (section 4c: it carried an outright majority of the mass into
     * the round). If every survivor is barred this way, Long.MIN_VALUE is
     * returned as a sentinel telling the caller to retry with ignoreGuards
     * true, the fallback rule that sets BOTH the guard and the saturation bars
     * aside for that one basin (the co-dissolving exclusion is never set aside,
     * but a co-dissolver is not in the survivors list to begin with).
     */
    private static long pickReceiver(List<Long> survivors, long d,
            Map<Long, Long> guardCap, Map<Long, Long> groupParent, Map<Long, Long> groupCap,
            Map<Long, Long> absorbed, Set<Long> saturated, boolean ignoreGuards) {
        long best = Long.MIN_VALUE;
        long bestDist = Long.MAX_VALUE;
        for (Long s : survivors) {
            if (!ignoreGuards) {
                if (guardCap.containsKey(s)) {
                    long root = find(groupParent, s);
                    if (absorbed.getOrDefault(root, 0L) >= groupCap.get(root)) {
                        continue;
                    }
                }
                if (saturated.contains(s)) {
                    continue;
                }
            }
            long dist = Math.abs(s - d);
            if (best == Long.MIN_VALUE || dist < bestDist || (dist == bestDist && s < best)) {
                best = s;
                bestDist = dist;
            }
        }
        return best;
    }

    /** Union-find over guarded positions linked by section 4b `link` lines. */
    private static long find(Map<Long, Long> parent, long x) {
        long r = x;
        while (parent.get(r) != r) {
            r = parent.get(r);
        }
        long cur = x;
        while (parent.get(cur) != r) {
            long next = parent.get(cur);
            parent.put(cur, r);
            cur = next;
        }
        return r;
    }

    private static void union(Map<Long, Long> parent, long a, long b) {
        long ra = find(parent, a);
        long rb = find(parent, b);
        if (ra != rb) {
            parent.put(ra, rb);
        }
    }

    /** Lowest-position bin with the greatest count inside [pos[i]-h, pos[i]+h]. */
    private static int climbTarget(long[] pos, long[] cnt, int i, long h) {
        long lo = pos[i] - h;
        long hi = pos[i] + h;
        int best = -1;
        for (int j = 0; j < pos.length; j++) {
            if (pos[j] < lo || pos[j] > hi) {
                continue;
            }
            if (best == -1 || cnt[j] > cnt[best]
                    || (cnt[j] == cnt[best] && pos[j] < pos[best])) {
                best = j;
            }
        }
        return best;
    }

    private static long gcd(long a, long b) {
        while (b != 0) {
            long t = a % b;
            a = b;
            b = t;
        }
        return a;
    }

    private static long parseInt(String s) {
        if (!s.matches("-?\\d+")) {
            System.exit(3);
        }
        try {
            return Long.parseLong(s);
        } catch (NumberFormatException e) {
            // Longer than long range is still a plain decimal integer but far
            // outside every value bound; saturate so the schema check fires.
            return s.startsWith("-") ? Long.MIN_VALUE / 4 : Long.MAX_VALUE / 4;
        }
    }

    private static void malformed(String code, int line) {
        emit("{\"status\":\"malformed\",\"error\":\"" + code + "\",\"line\":" + line + "}");
        System.exit(0);
    }

    private static void emit(String line) {
        try {
            Path out = Paths.get("/app/output/result.json");
            Files.createDirectories(out.getParent());
            Files.write(out, (line + "\n").getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) {
            System.exit(1);
        }
        System.out.println(line);
    }
}
