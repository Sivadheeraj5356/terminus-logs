package org.terminus.calc;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import static org.terminus.calc.Model.*;

final class StateStore {
    static Shard shard(String id, long generation, List<String> rawRecords) throws Validation {
        if (id == null || !id.matches("[A-Za-z0-9_.-]+") || generation < 0) {
            throw new Validation("invalid shard header");
        }
        List<String> records = new ArrayList<>(rawRecords);
        records.sort(String::compareTo);
        return new Shard(id, generation, List.copyOf(records), "");
    }

    static StateData create(Meta meta, List<Shard> supplied) throws Validation {
        List<Shard> shards = new ArrayList<>(supplied);
        shards.sort(Comparator.comparingLong((Shard shard) -> shard.generation).thenComparing(shard -> shard.id));
        return new StateData(meta, List.copyOf(shards), "", "", "");
    }

    static StateData read(Path path) throws StateMismatch {
        throw new StateMismatch("checkpoint support not implemented");
    }

    static void requireExtension(StateData previous, StateData current) throws StateMismatch {
        throw new StateMismatch("checkpoint resume not implemented");
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

    private StateStore() {}
}
