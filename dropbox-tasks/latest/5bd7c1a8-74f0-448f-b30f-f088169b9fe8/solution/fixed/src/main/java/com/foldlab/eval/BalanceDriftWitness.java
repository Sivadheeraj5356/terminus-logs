package com.foldlab.eval;

import com.foldlab.model.FoldRecord;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeSet;

public final class BalanceDriftWitness {
    public String compute(
            List<FoldRecord> records, int rowCount, double maxLabelSkew, String skewBand) {
        double javaSkew = computeJavaSkew(records, rowCount);
        String javaSix = String.format(Locale.US, "%.6f", javaSkew);
        String rSix = String.format(Locale.US, "%.6f", maxLabelSkew);
        String band = skewBand == null ? "" : skewBand;
        return sha256Hex(javaSix + "|" + rSix + "|" + band);
    }

    private static double computeJavaSkew(List<FoldRecord> records, int rowCount) {
        if (records == null || records.isEmpty() || rowCount <= 0) {
            return 0.0;
        }
        Map<String, Integer> globalCounts = new HashMap<>();
        List<FoldRecord> positiveFolds = new java.util.ArrayList<>();
        for (FoldRecord record : records) {
            if (record.getRowIds() == null || record.getRowIds().isEmpty()) {
                continue;
            }
            positiveFolds.add(record);
            if (record.getLabelCounts() != null) {
                for (Map.Entry<String, Integer> entry : record.getLabelCounts().entrySet()) {
                    int value = entry.getValue() == null ? 0 : entry.getValue();
                    globalCounts.merge(entry.getKey(), value, Integer::sum);
                }
            }
        }
        if (positiveFolds.isEmpty()) {
            return 0.0;
        }
        TreeSet<String> labels = new TreeSet<>(globalCounts.keySet());
        double maxSkew = 0.0;
        for (String label : labels) {
            double globalShare = globalCounts.getOrDefault(label, 0) / (double) rowCount;
            for (FoldRecord record : positiveFolds) {
                int foldSize = record.getRowIds().size();
                Integer count =
                        record.getLabelCounts() == null
                                ? null
                                : record.getLabelCounts().get(label);
                double foldShare = (count == null ? 0 : count) / (double) foldSize;
                maxSkew = Math.max(maxSkew, Math.abs(foldShare - globalShare));
            }
        }
        return maxSkew;
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
