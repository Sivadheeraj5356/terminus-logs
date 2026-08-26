package com.foldlab.eval;

import com.foldlab.model.FoldRecord;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.TreeSet;

public final class StratumStabilityIndex {
    public String compute(List<FoldRecord> records) {
        if (records == null || records.isEmpty()) {
            return sha256Hex("");
        }
        List<FoldRecord> positiveFolds = new ArrayList<>();
        for (FoldRecord record : records) {
            if (record.getRowIds() != null && !record.getRowIds().isEmpty()) {
                positiveFolds.add(record);
            }
        }
        if (positiveFolds.isEmpty()) {
            return sha256Hex("");
        }
        TreeSet<String> labels = new TreeSet<>();
        for (FoldRecord record : records) {
            labels.addAll(record.getLabelCounts().keySet());
        }
        List<String> lines = new ArrayList<>();
        for (String label : labels) {
            double maxShare = Double.NEGATIVE_INFINITY;
            double minShare = Double.POSITIVE_INFINITY;
            for (FoldRecord record : positiveFolds) {
                int foldSize = record.getRowIds().size();
                Integer count = record.getLabelCounts().get(label);
                double share = (count == null ? 0 : count) / (double) foldSize;
                if (share > maxShare) {
                    maxShare = share;
                }
                if (share < minShare) {
                    minShare = share;
                }
            }
            lines.add(
                    label
                            + "|"
                            + String.format(Locale.US, "%.6f", maxShare)
                            + "|"
                            + String.format(Locale.US, "%.6f", minShare));
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
