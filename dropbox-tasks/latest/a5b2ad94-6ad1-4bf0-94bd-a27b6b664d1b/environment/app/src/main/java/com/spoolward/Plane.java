package com.spoolward;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

public final class Plane {

    static final String[] KINDS = {"ROUTE", "DETACH", "HOLD", "RELEASE", "PIN",
        "UNPIN", "QUIESCE", "RESUME", "DECOMMISSION", "RETUNE", "FLUSH"};
    static final String[] DISPOSITIONS = {"APPLIED", "DENIED", "NOOP",
        "UNAUTHORIZED", "VOID"};
    static final String[] STATES = {"LIVE", "DORMANT", "DETACHED", "PURGED",
        "FLUSHED", "DECOMMISSIONED"};

    static final class Rec {
        String channel;
        String source;
        long granted;
        boolean pinned;
        String state;
        Long hold;
        long ord;
    }

    private final Path root;
    private long revision;
    private long defaultBudget;
    private long holdTerm;
    private final Set<String> collectors = new HashSet<>();
    private final Set<String> deadCollectors = new HashSet<>();
    private final List<String> indices = new ArrayList<>();
    private final Map<String, String> indexCollector = new HashMap<>();
    private final Map<String, String> indexStanding = new HashMap<>();
    private final Map<String, Long> indexBudget = new HashMap<>();
    private final Map<String, List<String>> indexChannels = new HashMap<>();
    private final Map<String, String> channelIndex = new HashMap<>();
    private final Set<String> sources = new HashSet<>();
    private final Map<String, Long> sourceVolume = new HashMap<>();
    private final Map<String, String> sourceClass = new HashMap<>();
    private final Map<String, Set<String>> curators = new HashMap<>();
    private final Map<String, Set<String>> operators = new HashMap<>();
    private final List<Rec> records = new ArrayList<>();
    private final Set<String> barred = new HashSet<>();
    private final Map<String, Long> dispositions = new LinkedHashMap<>();
    private final List<Object> journal = new ArrayList<>();
    private long seen;
    private long term;

    public Plane(Path root) {
        this.root = root;
        for (String d : DISPOSITIONS) {
            dispositions.put(d, 0L);
        }
    }

    private static boolean isInt(Object v) {
        return v instanceof Long;
    }

    private static boolean isStr(Object v) {
        return v instanceof String;
    }

    private String read(Path p) throws IOException {
        return new String(Files.readAllBytes(p), StandardCharsets.UTF_8);
    }

    private void load() throws IOException {
        String section = null;
        for (String raw : read(root.resolve("plane.ini")).split("\n", -1)) {
            String line = raw.trim();
            if (line.isEmpty() || line.startsWith("#")) {
                continue;
            }
            if (line.startsWith("[") && line.endsWith("]")) {
                section = line.substring(1, line.length() - 1);
                continue;
            }
            int eq = line.indexOf('=');
            if (eq < 0) {
                continue;
            }
            String key = line.substring(0, eq).trim();
            String val = line.substring(eq + 1).trim();
            if ("plane".equals(section)) {
                if (key.equals("plane_revision")) {
                    revision = Long.parseLong(val);
                } else if (key.equals("index_budget")) {
                    defaultBudget = Long.parseLong(val);
                } else if (key.equals("hold_term")) {
                    holdTerm = Long.parseLong(val);
                }
            } else if ("collectors".equals(section)) {
                collectors.add(key);
            } else if ("indices".equals(section)) {
                indices.add(key);
                indexCollector.put(key, val);
                indexStanding.put(key, "SERVING");
                indexBudget.put(key, null);
            }
        }
        for (String raw : read(root.resolve("sources.tsv")).split("\n", -1)) {
            if (raw.trim().isEmpty()) {
                continue;
            }
            String[] parts = raw.split("\t", -1);
            sources.add(parts[0]);
            sourceVolume.put(parts[0], Long.parseLong(parts[1]));
            sourceClass.put(parts[0], parts[2]);
        }
        for (String raw : read(root.resolve("operators.tsv")).split("\n", -1)) {
            if (raw.trim().isEmpty()) {
                continue;
            }
            String[] parts = raw.split("\t", -1);
            Set<String> held = new HashSet<>();
            if (!parts[2].equals("-")) {
                for (String s : parts[2].split(";", -1)) {
                    held.add(s);
                }
            }
            if (parts[1].equals("curator")) {
                curators.put(parts[0], held);
            } else {
                operators.put(parts[0], held);
            }
        }
        for (String index : indices) {
            List<String> owned = new ArrayList<>();
            Path roster = root.resolve("indices").resolve(index + ".tsv");
            for (String raw : read(roster).split("\n", -1)) {
                if (raw.trim().isEmpty()) {
                    continue;
                }
                String[] parts = raw.split("\t", -1);
                owned.add(parts[0]);
                channelIndex.put(parts[0], index);
            }
            indexChannels.put(index, owned);
        }
        for (String raw : read(root.resolve("streams.ndjson")).split("\n", -1)) {
            if (raw.trim().isEmpty()) {
                continue;
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> rec = (Map<String, Object>) Wire.parse(raw);
            Rec r = new Rec();
            r.channel = (String) rec.get("channel");
            r.source = (String) rec.get("source");
            r.granted = (Long) rec.get("opened");
            r.pinned = Boolean.TRUE.equals(rec.get("pinned"));
            r.state = "LIVE";
            r.hold = null;
            r.ord = records.size();
            records.add(r);
        }
    }

    private Rec standingOnChannel(String channel) {
        for (Rec r : records) {
            if (r.state.equals("LIVE") && r.channel.equals(channel)) {
                return r;
            }
        }
        return null;
    }

    private Rec standingOnSource(String source) {
        for (Rec r : records) {
            if (r.state.equals("LIVE") && r.source.equals(source)) {
                return r;
            }
        }
        return null;
    }

    private long budgetOf(String index) {
        return defaultBudget;
    }

    private long indexVolume(String index) {
        long total = 0;
        for (Rec r : records) {
            if (r.state.equals("LIVE")
                    && channelIndex.get(r.channel).equals(index)) {
                total += sourceVolume.get(r.source);
            }
        }
        return total;
    }

    private boolean betterPurge(Rec x, Rec y) {
        long dx = sourceVolume.get(x.source);
        long dy = sourceVolume.get(y.source);
        if (dx != dy) {
            return dx < dy;
        }
        if (x.granted != y.granted) {
            return x.granted < y.granted;
        }
        return x.ord < y.ord;
    }

    private boolean grants(String by, String index) {
        Set<String> held = curators.get(by);
        return held != null && held.contains(index);
    }

    private boolean charges(String by, String collector) {
        Set<String> held = operators.get(by);
        return held != null && held.contains(collector);
    }

    private static boolean isKind(String v) {
        for (String k : KINDS) {
            if (k.equals(v)) {
                return true;
            }
        }
        return false;
    }

    public void run() throws IOException {
        load();
        Path rdir = root.resolve("cycles");
        List<Path> shards = new ArrayList<>();
        try (var stream = Files.list(rdir)) {
            stream.forEach(shards::add);
        }
        shards.sort((a, b) -> a.getFileName().toString()
                .compareTo(b.getFileName().toString()));
        term = shards.size();
        long cycle = 0;
        for (Path shard : shards) {
            cycle++;
            long lastSeq = 0;
            for (String raw : read(shard).split("\n", -1)) {
                if (raw.trim().isEmpty()) {
                    continue;
                }
                seen++;
                Object[] out = judge(raw, cycle, lastSeq);
                String disposition = (String) out[0];
                dispositions.put(disposition, dispositions.get(disposition) + 1);
                if (!disposition.equals("VOID")) {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> entry = (Map<String, Object>) out[1];
                    lastSeq = (Long) entry.get("seq");
                    journal.add(entry);
                }
            }
            close(cycle);
        }
    }

    private Object[] judge(String raw, long cycle, long lastSeq) {
        Object parsed;
        try {
            parsed = Wire.parse(raw);
        } catch (RuntimeException e) {
            return new Object[]{"VOID", null, null};
        }
        if (!(parsed instanceof Map)) {
            return new Object[]{"VOID", null, null};
        }
        @SuppressWarnings("unchecked")
        Map<String, Object> rec = (Map<String, Object>) parsed;
        Object seqV = rec.get("seq");
        if (!isInt(seqV)) {
            return new Object[]{"VOID", null, null};
        }
        long seq = (Long) seqV;
        if (seq <= 0 || seq <= lastSeq) {
            return new Object[]{"VOID", null, seq};
        }
        Object kindV = rec.get("kind");
        if (!isStr(kindV) || !isKind((String) kindV)) {
            return new Object[]{"VOID", null, seq};
        }
        String kind = (String) kindV;
        Object actorV = rec.get("actor");
        if (!isStr(actorV)) {
            return new Object[]{"VOID", null, seq};
        }
        String actor = (String) actorV;
        if (!curators.containsKey(actor) && !operators.containsKey(actor)) {
            return new Object[]{"VOID", null, seq};
        }
        String[] out = judgeKind(rec, kind, actor, cycle);
        if (out == null) {
            return new Object[]{"VOID", null, seq};
        }
        Map<String, Object> entry = new TreeMap<>();
        entry.put("cycle", cycle);
        entry.put("seq", seq);
        entry.put("kind", kind);
        entry.put("subject", out[1]);
        entry.put("disposition", out[0]);
        return new Object[]{out[0], entry, seq};
    }

    private String getStr(Map<String, Object> rec, String key) {
        Object v = rec.get(key);
        return isStr(v) ? (String) v : null;
    }

    private String[] judgeKind(Map<String, Object> rec, String kind,
            String actor, long cycle) {
        if (kind.equals("ROUTE")) {
            return doRoute(rec, actor, cycle);
        }
        if (kind.equals("DETACH") || kind.equals("PIN") || kind.equals("UNPIN")) {
            String channel = getStr(rec, "channel");
            if (channel == null || !channelIndex.containsKey(channel)) {
                return null;
            }
            String index = channelIndex.get(channel);
            if (!grants(actor, index)) {
                return new String[]{"UNAUTHORIZED", channel};
            }
            if (kind.equals("DETACH")) {
                return new String[]{doDetach(channel), channel};
            }
            if (kind.equals("PIN")) {
                return new String[]{doPin(channel), channel};
            }
            return new String[]{doUnpin(channel), channel};
        }
        if (kind.equals("HOLD") || kind.equals("RELEASE")) {
            return doHoldRelease(rec, kind, actor, cycle);
        }
        if (kind.equals("FLUSH")) {
            String channel = getStr(rec, "channel");
            if (channel == null || !channelIndex.containsKey(channel)) {
                return null;
            }
            String index = channelIndex.get(channel);
            if (!charges(actor, indexCollector.get(index))) {
                return new String[]{"UNAUTHORIZED", channel};
            }
            return new String[]{doFlush(channel), channel};
        }
        if (kind.equals("QUIESCE") || kind.equals("RESUME")
                || kind.equals("RETUNE")) {
            String index = getStr(rec, "index");
            if (index == null || !indexCollector.containsKey(index)) {
                return null;
            }
            if (kind.equals("RETUNE")) {
                Object val = rec.get("budget");
                if (!isInt(val) || (Long) val < 0) {
                    return null;
                }
            }
            if (!charges(actor, indexCollector.get(index))) {
                return new String[]{"UNAUTHORIZED", index};
            }
            if (kind.equals("QUIESCE")) {
                return new String[]{doQuiesce(index), index};
            }
            if (kind.equals("RESUME")) {
                return new String[]{doResume(index), index};
            }
            return new String[]{doRetune(index, (Long) rec.get("budget")),
                index};
        }
        String collector = getStr(rec, "collector");
        if (collector == null || !collectors.contains(collector)) {
            return null;
        }
        if (!charges(actor, collector)) {
            return new String[]{"UNAUTHORIZED", collector};
        }
        return new String[]{doDecommission(collector), collector};
    }

    private String[] doRoute(Map<String, Object> rec, String actor,
            long cycle) {
        String channel = getStr(rec, "channel");
        if (channel == null || !channelIndex.containsKey(channel)) {
            return null;
        }
        String source = getStr(rec, "source");
        if (source == null || !sources.contains(source)) {
            return null;
        }
        String index = channelIndex.get(channel);
        if (!grants(actor, index)) {
            return new String[]{"UNAUTHORIZED", channel};
        }
        Rec cur = standingOnChannel(channel);
        if (cur != null && cur.source.equals(source)) {
            return new String[]{"NOOP", channel};
        }
        if (!indexStanding.get(index).equals("SERVING")) {
            return new String[]{"DENIED", channel};
        }
        if (cur != null) {
            return new String[]{"DENIED", channel};
        }
        Rec bound = null;
        for (Rec r : records) {
            if (r.state.equals("LIVE") && r.source.equals(source)
                    && channelIndex.get(r.channel).equals(index)) {
                bound = r;
                break;
            }
        }
        if (bound != null) {
            return new String[]{"DENIED", channel};
        }
        Rec fresh = new Rec();
        fresh.channel = channel;
        fresh.source = source;
        fresh.granted = cycle;
        fresh.pinned = false;
        fresh.state = "LIVE";
        fresh.hold = null;
        fresh.ord = records.size();
        records.add(fresh);
        return new String[]{"APPLIED", channel};
    }

    private String doDetach(String channel) {
        Rec rec = standingOnChannel(channel);
        if (rec == null) {
            return "NOOP";
        }
        if (rec.hold != null) {
            return "DENIED";
        }
        rec.state = "DETACHED";
        rec.pinned = false;
        return "APPLIED";
    }

    private String doFlush(String channel) {
        Rec rec = standingOnChannel(channel);
        if (rec == null) {
            return "NOOP";
        }
        if (rec.hold != null) {
            return "DENIED";
        }
        rec.state = "FLUSHED";
        rec.pinned = false;
        rec.hold = null;
        barred.add(rec.source + "|" + rec.channel);
        return "APPLIED";
    }

    private String[] doHoldRelease(Map<String, Object> rec, String kind,
            String actor, long cycle) {
        boolean hasDevice = rec.containsKey("source");
        boolean hasOutlet = rec.containsKey("channel");
        if (hasDevice == hasOutlet) {
            return null;
        }
        String subject;
        Rec target;
        if (hasOutlet) {
            String channel = getStr(rec, "channel");
            if (channel == null || !channelIndex.containsKey(channel)) {
                return null;
            }
            subject = channel;
            target = standingOnChannel(channel);
        } else {
            String source = getStr(rec, "source");
            if (source == null || !sources.contains(source)) {
                return null;
            }
            subject = source;
            target = standingOnChannel(source);
        }
        if (target == null) {
            return new String[]{"NOOP", subject};
        }
        String index = channelIndex.get(target.channel);
        if (!grants(actor, index)) {
            return new String[]{"UNAUTHORIZED", subject};
        }
        if (kind.equals("HOLD")) {
            if (target.hold != null) {
                return new String[]{"NOOP", subject};
            }
            target.hold = cycle;
            return new String[]{"APPLIED", subject};
        }
        if (target.hold == null) {
            return new String[]{"NOOP", subject};
        }
        target.hold = null;
        return new String[]{"APPLIED", subject};
    }

    private String doPin(String channel) {
        Rec rec = standingOnChannel(channel);
        if (rec == null) {
            return "NOOP";
        }
        if (rec.pinned) {
            return "NOOP";
        }
        rec.pinned = true;
        return "APPLIED";
    }

    private String doUnpin(String channel) {
        Rec rec = standingOnChannel(channel);
        if (rec == null || !rec.pinned) {
            return "NOOP";
        }
        rec.pinned = false;
        return "APPLIED";
    }

    private String doQuiesce(String index) {
        String st = indexStanding.get(index);
        if (st.equals("DECOMMISSIONED")) {
            return "DENIED";
        }
        if (st.equals("QUIESCED")) {
            return "NOOP";
        }
        indexStanding.put(index, "QUIESCED");
        for (Rec rec : records) {
            if (rec.state.equals("LIVE")
                    && channelIndex.get(rec.channel).equals(index)) {
                rec.pinned = false;
            }
        }
        return "APPLIED";
    }

    private String doResume(String index) {
        String st = indexStanding.get(index);
        if (st.equals("DECOMMISSIONED")) {
            return "DENIED";
        }
        if (st.equals("SERVING")) {
            return "NOOP";
        }
        indexStanding.put(index, "SERVING");
        return "APPLIED";
    }

    private String doDecommission(String collector) {
        if (deadCollectors.contains(collector)) {
            return "NOOP";
        }
        deadCollectors.add(collector);
        for (String index : indices) {
            if (!indexCollector.get(index).equals(collector)) {
                continue;
            }
            indexStanding.put(index, "DECOMMISSIONED");
        }
        return "APPLIED";
    }

    private String doRetune(String index, long val) {
        if (indexStanding.get(index).equals("DECOMMISSIONED")) {
            return "DENIED";
        }
        Long cur = indexBudget.get(index);
        long eff = cur == null ? defaultBudget : cur;
        if (eff == val) {
            return "NOOP";
        }
        indexBudget.put(index, val);
        return "APPLIED";
    }

    private void expireHolds(long cycle) {
        for (Rec rec : records) {
            if (rec.hold != null && rec.hold + holdTerm == cycle) {
                rec.hold = null;
            }
        }
    }

    private void purgeOverflows() {
        for (String index : indices) {
            if (!indexStanding.get(index).equals("SERVING")) {
                continue;
            }
            while (indexVolume(index) > budgetOf(index)) {
                Rec best = null;
                for (Rec rec : records) {
                    if (!rec.state.equals("LIVE")) {
                        continue;
                    }
                    if (!channelIndex.get(rec.channel).equals(index)) {
                        continue;
                    }
                    if (rec.pinned) {
                        continue;
                    }
                    if (rec.hold != null) {
                        continue;
                    }
                    if (best == null || betterPurge(rec, best)) {
                        best = rec;
                    }
                }
                if (best == null) {
                    break;
                }
                best.state = "PURGED";
                best.pinned = false;
                best.hold = null;
            }
        }
    }

    private void close(long cycle) {
        purgeOverflows();
        expireHolds(cycle);
    }

    public Map<String, Object> report() throws IOException {
        Map<String, Object> byState = new TreeMap<>();
        for (String s : STATES) {
            byState.put(s, 0L);
        }
        for (Rec rec : records) {
            String s = rec.state;
            byState.put(s, (Long) byState.get(s) + 1);
        }
        Map<String, Object> byCircuit = new TreeMap<>();
        for (String index : indices) {
            String st = indexStanding.get(index);
            long live = 0;
            long volume = 0;
            if (!st.equals("DECOMMISSIONED")) {
                for (Rec rec : records) {
                    if (rec.state.equals("LIVE")
                            && channelIndex.get(rec.channel).equals(index)) {
                        live++;
                        volume += sourceVolume.get(rec.source);
                    }
                }
            }
            Map<String, Object> cell = new TreeMap<>();
            cell.put("standing", st.equals("DECOMMISSIONED") ? "QUIESCED" : st);
            cell.put("live", live);
            cell.put("volume", volume);
            byCircuit.put(index, cell);
        }
        Map<String, Object> rep = new TreeMap<>();
        rep.put("plane_revision", revision);
        rep.put("cycles_run", term);
        rep.put("orders_seen", seen);
        rep.put("by_disposition", new TreeMap<>(dispositions));
        rep.put("by_state", byState);
        rep.put("by_index", byCircuit);
        rep.put("journal", journal);
        rep.put("data_digest", Wire.treeDigest(root));
        String canon = Wire.canonical(rep);
        rep.put("report_digest", Wire.sha16(canon.getBytes(StandardCharsets.UTF_8)));
        return rep;
    }
}
