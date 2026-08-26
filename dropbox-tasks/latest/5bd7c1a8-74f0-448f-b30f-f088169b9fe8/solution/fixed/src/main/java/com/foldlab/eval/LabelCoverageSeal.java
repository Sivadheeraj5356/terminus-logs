package com.foldlab.eval;

import com.foldlab.model.FoldRecord;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.TreeSet;

public final class LabelCoverageSeal {
    public String compute(List<FoldRecord> records, int foldCount) {
        Map<String, Integer> coverage = new TreeMap<>();
        TreeSet<String> labels = new TreeSet<>();
        for (FoldRecord record : records) {
            labels.addAll(record.getLabelCounts().keySet());
        }
        for (String label : labels) {
            int present = 0;
            for (FoldRecord record : records) {
                Integer count = record.getLabelCounts().get(label);
                if (count != null && count > 0) {
                    present++;
                }
            }
            coverage.put(label, present);
        }
        List<String> lines = new ArrayList<>();
        for (Map.Entry<String, Integer> entry : coverage.entrySet()) {
            lines.add(entry.getKey() + "|" + entry.getValue());
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
