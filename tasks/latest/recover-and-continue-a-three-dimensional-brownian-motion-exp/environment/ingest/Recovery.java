package org.terminus.calc;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import static org.terminus.calc.Model.*;

final class Recovery {
    static StateData snapshot(Path spec) throws Validation {
        final List<String> lines;
        try { lines = Files.readAllLines(spec, StandardCharsets.UTF_8); }
        catch (Exception e) { throw new Validation("cannot read spec"); }
        Meta meta = null;
        List<Shard> shards = new ArrayList<>();
        String id = null;
        long generation = -1;
        List<String> records = null;
        for (String raw : lines) {
            String line = raw.trim();
            if (line.startsWith("@@META|")) {
                if (meta != null) throw new Validation("duplicate metadata");
                meta = parseMeta(line);
            } else if (line.startsWith("@@SHARD|")) {
                if (id != null) shards.add(StateStore.shard(id, generation, records));
                String[] parts = line.split("\\|", -1);
                if (parts.length != 3) throw new Validation("invalid shard header");
                id = parts[1].substring(parts[1].indexOf('=') + 1);
                generation = Long.parseLong(parts[2].substring(parts[2].indexOf('=') + 1));
                records = new ArrayList<>();
            } else if (line.equals("@@END_SHARD") && id != null) {
                shards.add(StateStore.shard(id, generation, records));
                id = null; records = null;
            } else if (line.startsWith("R|") && records != null) {
                records.add(line);
            }
        }
        if (id != null) shards.add(StateStore.shard(id, generation, records));
        if (meta == null || shards.isEmpty()) throw new Validation("missing metadata or shards");
        return StateStore.create(meta, shards);
    }

    static Recovered recover(StateData state) {
        Counts counts = new Counts();
        counts.shardsSeen = state.shards.size();
        for (Shard shard : state.shards) counts.recordsSeen += shard.records.size();
        return new Recovered(state, counts, List.of(), List.of(), List.of());
    }

    static Meta validateMeta(double dt, double box, List<String> particles, int fitStart, int fitEnd) throws Validation {
        if (!Double.isFinite(dt) || dt <= 0 || !Double.isFinite(box) || box <= 0) throw new Validation("invalid metadata numbers");
        if (particles.size() < 2 || new HashSet<>(particles).size() != particles.size()) throw new Validation("invalid particles");
        for (String particle : particles) if (!particle.matches("[A-Za-z0-9_.-]+")) throw new Validation("invalid particle id");
        if (fitStart < 1 || fitStart >= fitEnd) throw new Validation("invalid fit");
        return new Meta(dt, box, List.copyOf(particles), fitStart, fitEnd);
    }

    private static Meta parseMeta(String line) throws Validation {
        String[] parts = line.split("\\|", -1);
        if (parts.length != 6) throw new Validation("invalid metadata");
        Map<String,String> values = new HashMap<>();
        for (int i=1;i<parts.length;i++) {
            int eq=parts[i].indexOf('=');
            if (eq<=0 || values.put(parts[i].substring(0,eq),parts[i].substring(eq+1))!=null) throw new Validation("invalid metadata");
        }
        if (!values.keySet().equals(Set.of("dt","dimensions","box","particles","fit")) || !"3".equals(values.get("dimensions"))) throw new Validation("invalid metadata");
        try {
            String[] fit=values.get("fit").split(":",-1);
            return validateMeta(Double.parseDouble(values.get("dt")), Double.parseDouble(values.get("box")), Arrays.asList(values.get("particles").split(",",-1)), Integer.parseInt(fit[0]), Integer.parseInt(fit[1]));
        } catch (Exception e) { throw new Validation("invalid metadata"); }
    }

    private Recovery() {}
}
