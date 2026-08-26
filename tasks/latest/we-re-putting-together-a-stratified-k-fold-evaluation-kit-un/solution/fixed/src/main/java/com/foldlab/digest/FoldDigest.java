package com.foldlab.digest;

import com.foldlab.model.FoldRecord;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public final class FoldDigest {
    public String compute(List<FoldRecord> folds) {
        List<FoldRecord> sorted = folds.stream()
                .sorted(Comparator.comparingInt(FoldRecord::getFoldId))
                .collect(Collectors.toList());
        StringBuilder body = new StringBuilder();
        for (FoldRecord fold : sorted) {
            if (body.length() > 0) {
                body.append('\n');
            }
            String labelHist = fold.getLabelCounts().entrySet().stream()
                    .sorted(Map.Entry.comparingByKey())
                    .map(entry -> entry.getKey() + "=" + entry.getValue())
                    .collect(Collectors.joining(","));
            body.append(fold.getFoldId())
                    .append('|')
                    .append(fold.getRowIds().size())
                    .append('|')
                    .append(labelHist);
        }
        return sha256Hex(body.toString());
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
