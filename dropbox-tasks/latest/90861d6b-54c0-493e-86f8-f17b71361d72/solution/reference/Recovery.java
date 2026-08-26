package org.terminus.calc;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.zip.CRC32;
import static org.terminus.calc.Model.*;

final class Recovery {
    static StateData snapshot(Path spec) throws Validation {
        final List<String> lines;
        try {
            lines = Files.readAllLines(spec, StandardCharsets.UTF_8);
        } catch (Exception e) {
            throw new Validation("cannot read spec");
        }
        Meta meta = null;
        String shardId = null;
        long generation = -1;
        List<String> records = null;
        List<Shard> shards = new ArrayList<>();
        for (String raw : lines) {
            String line = raw.trim();
            if (line.startsWith("@@META|")) {
                if (meta != null || shardId != null) throw new Validation("duplicate or misplaced metadata");
                meta = parseMeta(line);
            } else if (line.startsWith("@@SHARD|")) {
                if (shardId != null) shards.add(StateStore.shard(shardId, generation, records));
                Map<String, String> values = parseFields(line, "@@SHARD", 2);
                if (!values.keySet().equals(Set.of("id", "generation"))) throw new Validation("invalid shard header");
                shardId = values.get("id");
                try {
                    generation = Long.parseLong(values.get("generation"));
                } catch (Exception e) {
                    throw new Validation("invalid shard header");
                }
                records = new ArrayList<>();
            } else if (line.equals("@@END_SHARD")) {
                if (shardId == null) throw new Validation("orphan shard terminator");
                shards.add(StateStore.shard(shardId, generation, records));
                shardId = null;
                generation = -1;
                records = null;
            } else if (line.startsWith("R|")) {
                if (shardId == null) throw new Validation("record outside shard");
                records.add(line);
            }
        }
        if (shardId != null) shards.add(StateStore.shard(shardId, generation, records));
        if (meta == null || shards.isEmpty()) throw new Validation("missing metadata or shards");
        return StateStore.create(meta, shards);
    }

    static Recovered recover(StateData state) {
        Counts counts = new Counts();
        counts.shardsSeen = state.shards.size();
        List<Row> valid = new ArrayList<>();
        Set<Long> knownTicks = new TreeSet<>();
        for (Shard shard : state.shards) {
            for (String line : shard.records) {
                counts.recordsSeen++;
                String[] parts = line.split("\\|", -1);
                if (parts.length != 7 || !parts[0].equals("R") || !parts[6].matches("[0-9a-f]{8}")) {
                    counts.malformed++;
                    continue;
                }
                long tick;
                double x;
                double y;
                double z;
                try {
                    tick = Long.parseLong(parts[1]);
                    x = Double.parseDouble(parts[3]);
                    y = Double.parseDouble(parts[4]);
                    z = Double.parseDouble(parts[5]);
                } catch (Exception e) {
                    counts.malformed++;
                    continue;
                }
                if (tick < 0 || !coordinate(x, state.meta.box) || !coordinate(y, state.meta.box) || !coordinate(z, state.meta.box)) {
                    counts.malformed++;
                    continue;
                }
                String preimage = String.join("|", Arrays.copyOfRange(parts, 1, 6));
                if (!crc32(preimage).equals(parts[6])) {
                    counts.crc++;
                    continue;
                }
                if (!state.meta.particles.contains(parts[2])) {
                    counts.unknown++;
                    continue;
                }
                counts.recordsValid++;
                knownTicks.add(tick);
                valid.add(new Row(tick, parts[2], x, y, z, shard.generation, shard.id));
            }
        }

        Map<String, List<Row>> grouped = new LinkedHashMap<>();
        for (Row row : valid) grouped.computeIfAbsent(key(row.tick, row.particle), ignored -> new ArrayList<>()).add(row);
        Map<String, Row> selected = new HashMap<>();
        Set<String> conflicting = new HashSet<>();
        for (Map.Entry<String, List<Row>> entry : grouped.entrySet()) {
            long highest = entry.getValue().stream().mapToLong(row -> row.generation).max().orElseThrow();
            List<Row> high = new ArrayList<>();
            for (Row row : entry.getValue()) {
                if (row.generation == highest) high.add(row);
                else counts.superseded++;
            }
            Row first = high.get(0);
            boolean same = true;
            for (Row row : high) {
                if (row.x != first.x || row.y != first.y || row.z != first.z) {
                    same = false;
                    break;
                }
            }
            if (!same) {
                counts.conflicts++;
                conflicting.add(entry.getKey());
                continue;
            }
            high.sort(Comparator.comparing(row -> row.shard));
            selected.put(entry.getKey(), high.get(0));
            counts.duplicates += high.size() - 1;
        }

        List<Row> selectedRows = new ArrayList<>(selected.values());
        selectedRows.sort(Comparator.comparingLong((Row row) -> row.tick).thenComparing(row -> row.particle));
        List<Long> complete = new ArrayList<>();
        List<Reject> rejected = new ArrayList<>();
        for (long tick : knownTicks) {
            boolean conflict = false;
            boolean missing = false;
            for (String particle : state.meta.particles) {
                String key = key(tick, particle);
                conflict |= conflicting.contains(key);
                missing |= !selected.containsKey(key);
            }
            if (!conflict && !missing) complete.add(tick);
            else rejected.add(new Reject(tick, conflict ? "conflicting-record" : "missing-particle"));
        }
        return new Recovered(state, counts, List.copyOf(selectedRows), List.copyOf(complete), List.copyOf(rejected));
    }

    static Meta validateMeta(double dt, double box, List<String> particles, int fitStart, int fitEnd) throws Validation {
        if (!Double.isFinite(dt) || dt <= 0 || !Double.isFinite(box) || box <= 0) throw new Validation("invalid metadata numbers");
        if (particles.size() < 2 || new HashSet<>(particles).size() != particles.size()) throw new Validation("invalid particles");
        for (String particle : particles) {
            if (!particle.matches("[A-Za-z0-9_.-]+")) throw new Validation("invalid particle id");
        }
        if (fitStart < 1 || fitStart >= fitEnd) throw new Validation("invalid fit");
        return new Meta(dt, box, List.copyOf(particles), fitStart, fitEnd);
    }

    private static Meta parseMeta(String line) throws Validation {
        Map<String, String> values = parseFields(line, "@@META", 5);
        if (!values.keySet().equals(Set.of("dt", "dimensions", "box", "particles", "fit"))
            || !"3".equals(values.get("dimensions"))) {
            throw new Validation("invalid metadata fields");
        }
        double dt;
        double box;
        int fitStart;
        int fitEnd;
        List<String> particles;
        try {
            dt = Double.parseDouble(values.get("dt"));
            box = Double.parseDouble(values.get("box"));
            particles = Arrays.asList(values.get("particles").split(",", -1));
            String[] fit = values.get("fit").split(":", -1);
            if (fit.length != 2) throw new NumberFormatException();
            fitStart = Integer.parseInt(fit[0]);
            fitEnd = Integer.parseInt(fit[1]);
        } catch (Exception e) {
            throw new Validation("invalid metadata");
        }
        return validateMeta(dt, box, particles, fitStart, fitEnd);
    }

    private static Map<String, String> parseFields(String line, String prefix, int count) throws Validation {
        String[] parts = line.split("\\|", -1);
        if (parts.length != count + 1 || !parts[0].equals(prefix)) throw new Validation("invalid fields");
        Map<String, String> values = new HashMap<>();
        for (int i = 1; i < parts.length; i++) {
            int equals = parts[i].indexOf('=');
            if (equals <= 0 || values.put(parts[i].substring(0, equals), parts[i].substring(equals + 1)) != null) {
                throw new Validation("invalid fields");
            }
        }
        return values;
    }

    private static boolean coordinate(double value, double box) {
        return Double.isFinite(value) && value >= 0 && value < box;
    }

    private static String crc32(String value) {
        CRC32 crc = new CRC32();
        crc.update(value.getBytes(StandardCharsets.UTF_8));
        return String.format("%08x", crc.getValue());
    }

    private static String key(long tick, String particle) {
        return tick + "\u0000" + particle;
    }

    private Recovery() {}
}
