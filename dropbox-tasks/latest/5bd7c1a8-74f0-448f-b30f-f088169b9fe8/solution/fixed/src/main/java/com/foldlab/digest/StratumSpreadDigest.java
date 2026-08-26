package com.foldlab.digest;

import com.foldlab.model.FoldRecord;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;

public final class StratumSpreadDigest {
    public String compute(List<FoldRecord> records) {
        Set<String> labels = new TreeSet<>();
        for (FoldRecord record : records) {
            labels.addAll(record.getLabelCounts().keySet());
        }
        List<String> lines = new ArrayList<>();
        for (String label : labels) {
            List<Integer> counts = new ArrayList<>();
            for (FoldRecord record : records) {
                counts.add(record.getLabelCounts().getOrDefault(label, 0));
            }
            int min = counts.stream().mapToInt(Integer::intValue).min().orElse(0);
            int max = counts.stream().mapToInt(Integer::intValue).max().orElse(0);
            lines.add(label + "|" + (max - min));
        }
        return sha256Hex(String.join("\n", lines));
    }

    private static String sha256Hex(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(hash.length * 2);
            for (byte b : hash) {
                hex.append(String.format("%02x", b));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }
}
