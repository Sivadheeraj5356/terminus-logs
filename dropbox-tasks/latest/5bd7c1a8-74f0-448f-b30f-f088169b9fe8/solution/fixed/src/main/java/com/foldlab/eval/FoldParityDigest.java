package com.foldlab.eval;

import com.foldlab.model.FoldRecord;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public final class FoldParityDigest {
    public String compute(List<FoldRecord> records) {
        List<FoldRecord> ordered = new ArrayList<>(records);
        ordered.sort(Comparator.comparingInt(FoldRecord::getFoldId));
        List<String> lines = new ArrayList<>();
        for (FoldRecord record : ordered) {
            String parity = (record.getFoldId() % 2 == 0) ? "even" : "odd";
            lines.add(record.getFoldId() + "|" + parity);
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
