package org.terminus.calc;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import static org.terminus.calc.Model.*;

final class StateStore {
    private static final Comparator<Shard> SHARD_ORDER =
        Comparator.comparingLong((Shard shard) -> shard.generation).thenComparing(shard -> shard.id);

    static Shard shard(String id, long generation, List<String> rawRecords) throws Validation {
        if (id == null || !id.matches("[A-Za-z0-9_.-]+") || generation < 0) {
            throw new Validation("invalid shard header");
        }
        List<String> records = new ArrayList<>(rawRecords);
        records.sort(String::compareTo);
        StringBuilder preimage = new StringBuilder();
        for (String record : records) preimage.append(record).append('\n');
        return new Shard(id, generation, List.copyOf(records), sha256(preimage.toString().getBytes(StandardCharsets.UTF_8)));
    }

    static StateData create(Meta meta, List<Shard> supplied) throws Validation {
        List<Shard> shards = new ArrayList<>(supplied);
        shards.sort(SHARD_ORDER);
        Set<String> ids = new HashSet<>();
        for (Shard shard : shards) {
            if (!ids.add(shard.id)) throw new Validation("duplicate shard id");
        }
        String body = sourceBody(meta, shards);
        String sourceHash = sha256(body.getBytes(StandardCharsets.UTF_8));
        String prefix = "schema|" + STATE_SCHEMA + "\n" + body + "sourceSha256|" + sourceHash + "\n";
        String stateHash = sha256(prefix.getBytes(StandardCharsets.UTF_8));
        String text = prefix + "stateSha256|" + stateHash + "\n";
        return new StateData(meta, List.copyOf(shards), sourceHash, stateHash, text);
    }

    static StateData read(Path path) throws StateMismatch {
        final String text;
        try {
            text = Files.readString(path, StandardCharsets.UTF_8);
        } catch (Exception e) {
            throw new StateMismatch("checkpoint not found or unreadable");
        }
        try {
            if (!text.endsWith("\n") || text.contains("\r")) throw new IllegalArgumentException();
            List<String> lines = new ArrayList<>(Arrays.asList(text.substring(0, text.length() - 1).split("\n", -1)));
            if (lines.size() < 4 || !lines.get(0).equals("schema|" + STATE_SCHEMA)) throw new IllegalArgumentException();
            Meta meta = parseMetaLine(lines.get(1));
            List<Shard> shards = new ArrayList<>();
            int index = 2;
            while (index < lines.size() && lines.get(index).startsWith("shard|")) {
                String header = lines.get(index++);
                Map<String, String> fields = fields(header, "shard", 4);
                String id = fields.get("id");
                long generation = Long.parseLong(fields.get("generation"));
                int count = Integer.parseInt(fields.get("records"));
                String expectedSha = fields.get("sha256");
                if (count < 0 || expectedSha == null || !expectedSha.matches("[0-9a-f]{64}")) throw new IllegalArgumentException();
                List<String> records = new ArrayList<>();
                for (int i = 0; i < count; i++) {
                    if (index >= lines.size() || !lines.get(index).startsWith("record|")) throw new IllegalArgumentException();
                    String encoded = lines.get(index++).substring("record|".length());
                    String record = new String(Base64.getUrlDecoder().decode(encoded), StandardCharsets.UTF_8);
                    if (!record.startsWith("R|") || record.indexOf('\n') >= 0 || record.indexOf('\r') >= 0) throw new IllegalArgumentException();
                    records.add(record);
                }
                Shard shard = shard(id, generation, records);
                if (!shard.sha256.equals(expectedSha)) throw new IllegalArgumentException();
                shards.add(shard);
            }
            if (index + 2 != lines.size()) throw new IllegalArgumentException();
            String sourceLine = lines.get(index++);
            String stateLine = lines.get(index);
            if (!sourceLine.matches("sourceSha256\\|[0-9a-f]{64}") || !stateLine.matches("stateSha256\\|[0-9a-f]{64}")) {
                throw new IllegalArgumentException();
            }
            StateData canonical = create(meta, shards);
            if (!canonical.sourceHash.equals(sourceLine.substring(sourceLine.indexOf('|') + 1))
                || !canonical.stateHash.equals(stateLine.substring(stateLine.indexOf('|') + 1))
                || !canonical.text.equals(text)) {
                throw new IllegalArgumentException();
            }
            return canonical;
        } catch (Exception e) {
            throw new StateMismatch("checkpoint integrity mismatch");
        }
    }

    static void requireExtension(StateData previous, StateData current) throws StateMismatch {
        if (!sameMeta(previous.meta, current.meta)) throw new StateMismatch("checkpoint metadata mismatch");
        Map<String, Shard> currentById = new HashMap<>();
        for (Shard shard : current.shards) currentById.put(shard.id, shard);
        for (Shard old : previous.shards) {
            Shard now = currentById.get(old.id);
            if (now == null) throw new StateMismatch("checkpoint shard missing");
            if (now.generation != old.generation || !now.sha256.equals(old.sha256) || !now.records.equals(old.records)) {
                throw new StateMismatch("checkpoint shard changed");
            }
        }
    }

    static String canonicalNumber(double value) {
        if (value == 0.0d) return "0";
        return BigDecimal.valueOf(value).stripTrailingZeros().toPlainString();
    }

    static String sha256(byte[] bytes) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
            StringBuilder out = new StringBuilder(64);
            for (byte b : digest) out.append(String.format("%02x", b & 0xff));
            return out.toString();
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private static String sourceBody(Meta meta, List<Shard> shards) {
        StringBuilder out = new StringBuilder();
        out.append(metaLine(meta)).append('\n');
        Base64.Encoder encoder = Base64.getUrlEncoder().withoutPadding();
        for (Shard shard : shards) {
            out.append("shard|id=").append(shard.id)
                .append("|generation=").append(shard.generation)
                .append("|records=").append(shard.records.size())
                .append("|sha256=").append(shard.sha256).append('\n');
            for (String record : shard.records) {
                out.append("record|")
                    .append(encoder.encodeToString(record.getBytes(StandardCharsets.UTF_8)))
                    .append('\n');
            }
        }
        return out.toString();
    }

    private static String metaLine(Meta meta) {
        return "meta|dt=" + canonicalNumber(meta.dt)
            + "|box=" + canonicalNumber(meta.box)
            + "|particles=" + String.join(",", meta.particles)
            + "|fit=" + meta.fitStart + ":" + meta.fitEnd;
    }

    private static Meta parseMetaLine(String line) throws Validation {
        Map<String, String> values = fields(line, "meta", 4);
        if (!values.keySet().equals(Set.of("dt", "box", "particles", "fit"))) throw new Validation("invalid checkpoint metadata");
        double dt = Double.parseDouble(values.get("dt"));
        double box = Double.parseDouble(values.get("box"));
        List<String> particles = Arrays.asList(values.get("particles").split(",", -1));
        String[] fit = values.get("fit").split(":", -1);
        if (fit.length != 2) throw new Validation("invalid checkpoint metadata");
        return Recovery.validateMeta(dt, box, particles, Integer.parseInt(fit[0]), Integer.parseInt(fit[1]));
    }

    private static Map<String, String> fields(String line, String prefix, int expected) {
        String[] parts = line.split("\\|", -1);
        if (parts.length != expected + 1 || !parts[0].equals(prefix)) throw new IllegalArgumentException();
        Map<String, String> out = new HashMap<>();
        for (int i = 1; i < parts.length; i++) {
            int equals = parts[i].indexOf('=');
            if (equals <= 0 || out.put(parts[i].substring(0, equals), parts[i].substring(equals + 1)) != null) {
                throw new IllegalArgumentException();
            }
        }
        return out;
    }

    private static boolean sameMeta(Meta a, Meta b) {
        return Double.doubleToLongBits(a.dt) == Double.doubleToLongBits(b.dt)
            && Double.doubleToLongBits(a.box) == Double.doubleToLongBits(b.box)
            && a.fitStart == b.fitStart
            && a.fitEnd == b.fitEnd
            && a.particles.equals(b.particles);
    }

    private StateStore() {}
}
