package com.foldlab.eval;

import com.foldlab.model.FoldRecord;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.List;
import java.util.TreeSet;

public final class TrainFoldMask {
    public String compute(List<FoldRecord> records, int holdoutFoldId) {
        TreeSet<Integer> trainIds = new TreeSet<>();
        if (records != null) {
            for (FoldRecord record : records) {
                int foldId = record.getFoldId();
                if (foldId != holdoutFoldId) {
                    trainIds.add(foldId);
                }
            }
        }
        if (trainIds.isEmpty()) {
            return sha256Hex("");
        }
        StringBuilder body = new StringBuilder();
        boolean first = true;
        for (Integer foldId : trainIds) {
            if (!first) {
                body.append(',');
            }
            body.append(foldId);
            first = false;
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
