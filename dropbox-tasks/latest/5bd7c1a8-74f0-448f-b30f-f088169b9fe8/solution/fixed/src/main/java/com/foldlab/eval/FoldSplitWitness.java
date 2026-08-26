package com.foldlab.eval;

import com.foldlab.model.FoldRecord;
import com.foldlab.util.CohortIds;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public final class FoldSplitWitness {
    public String compute(List<FoldRecord> records) {
        if (records == null || records.isEmpty()) {
            return sha256Hex("");
        }
        List<FoldRecord> ordered = new ArrayList<>(records);
        ordered.sort(Comparator.comparingInt(FoldRecord::getFoldId));
        List<String> lines = new ArrayList<>();
        for (FoldRecord record : ordered) {
            List<String> rowIds = record.getRowIds();
            if (rowIds == null || rowIds.isEmpty()) {
                lines.add(record.getFoldId() + "|-|-|0");
                continue;
            }
            BigInteger min = null;
            BigInteger max = null;
            for (String rowId : rowIds) {
                BigInteger value = CohortIds.parse(rowId);
                if (min == null || value.compareTo(min) < 0) {
                    min = value;
                }
                if (max == null || value.compareTo(max) > 0) {
                    max = value;
                }
            }
            lines.add(record.getFoldId() + "|" + min + "|" + max + "|" + rowIds.size());
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
