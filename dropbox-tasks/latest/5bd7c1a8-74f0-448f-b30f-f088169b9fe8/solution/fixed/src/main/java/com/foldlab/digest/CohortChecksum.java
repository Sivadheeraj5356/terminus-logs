package com.foldlab.digest;

import com.foldlab.model.FoldRow;
import com.foldlab.util.CohortIds;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.List;
import java.util.stream.Collectors;

public final class CohortChecksum {
    public String compute(List<FoldRow> rows) {
        String body = rows.stream()
                .sorted(CohortIds.comparing(FoldRow::getId))
                .map(row -> row.getId() + "|" + row.getLabel())
                .collect(Collectors.joining("\n"));
        return sha256Hex(body);
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
