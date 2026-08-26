package com.foldlab.digest;

import com.foldlab.model.FoldRecord;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

public final class LabelQuorumWitness {
    public String compute(List<FoldRecord> records) {
        Map<String, Integer> minFoldByLabel = new TreeMap<>();
        for (FoldRecord record : records) {
            int foldId = record.getFoldId();
            for (String label : record.getLabelCounts().keySet()) {
                minFoldByLabel.merge(label, foldId, Math::min);
            }
        }
        List<String> lines = new ArrayList<>();
        for (Map.Entry<String, Integer> entry : minFoldByLabel.entrySet()) {
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
