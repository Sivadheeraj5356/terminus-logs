package com.foldlab.eval;

import com.foldlab.model.FoldRecord;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;

public final class LabelPairCooccurrence {
    public String compute(List<FoldRecord> records) {
        if (records == null || records.isEmpty()) {
            return sha256Hex("");
        }
        List<FoldRecord> ordered = new ArrayList<>(records);
        ordered.sort(Comparator.comparingInt(FoldRecord::getFoldId));
        List<String> lines = new ArrayList<>();
        for (FoldRecord record : ordered) {
            Map<String, Integer> counts = record.getLabelCounts();
            if (counts == null || counts.isEmpty()) {
                continue;
            }
            TreeSet<String> positive = new TreeSet<>();
            for (Map.Entry<String, Integer> entry : counts.entrySet()) {
                if (entry.getValue() != null && entry.getValue() > 0) {
                    positive.add(entry.getKey());
                }
            }
            List<String> labels = new ArrayList<>(positive);
            for (int i = 0; i < labels.size(); i++) {
                for (int j = i + 1; j < labels.size(); j++) {
                    String a = labels.get(i);
                    String b = labels.get(j);
                    lines.add(record.getFoldId() + "|" + a + "|" + b);
                }
            }
        }
        if (lines.isEmpty()) {
            return sha256Hex("");
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
