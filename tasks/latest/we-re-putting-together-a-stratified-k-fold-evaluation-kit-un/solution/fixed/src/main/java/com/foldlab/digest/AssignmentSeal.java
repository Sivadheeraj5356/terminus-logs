package com.foldlab.digest;

import com.foldlab.model.FoldRow;
import com.foldlab.util.CohortIds;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public final class AssignmentSeal {
    public String compute(List<FoldRow> rows, Map<Integer, List<String>> assignment) {
        Map<String, Integer> idToFold = new HashMap<>();
        for (Map.Entry<Integer, List<String>> entry : assignment.entrySet()) {
            for (String rowId : entry.getValue()) {
                idToFold.put(rowId, entry.getKey());
            }
        }
        Map<String, List<FoldRow>> grouped = rows.stream().collect(Collectors.groupingBy(FoldRow::getLabel));
        List<String> lines = new ArrayList<>();
        for (String label : grouped.keySet().stream().sorted().toList()) {
            List<FoldRow> group = grouped.get(label).stream()
                    .sorted(CohortIds.comparing(FoldRow::getId))
                    .toList();
            String sequence = group.stream()
                    .map(row -> String.valueOf(idToFold.get(row.getId())))
                    .collect(Collectors.joining(","));
            lines.add(label + "|" + sequence);
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
