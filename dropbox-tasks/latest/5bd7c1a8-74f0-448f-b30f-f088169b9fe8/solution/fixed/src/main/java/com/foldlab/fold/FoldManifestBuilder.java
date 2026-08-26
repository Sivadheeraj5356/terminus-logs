package com.foldlab.fold;

import com.foldlab.model.FoldRecord;
import com.foldlab.model.FoldRow;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

public final class FoldManifestBuilder {
    public List<FoldRecord> buildRecords(List<FoldRow> rows, Map<Integer, List<String>> assignment) {
        Map<String, String> idToLabel = new HashMap<>();
        for (FoldRow row : rows) {
            idToLabel.put(row.getId(), row.getLabel());
        }
        List<FoldRecord> records = new ArrayList<>();
        for (Map.Entry<Integer, List<String>> entry : new TreeMap<>(assignment).entrySet()) {
            Map<String, Integer> labelCounts = new TreeMap<>();
            for (String rowId : entry.getValue()) {
                String label = idToLabel.get(rowId);
                labelCounts.put(label, labelCounts.getOrDefault(label, 0) + 1);
            }
            records.add(new FoldRecord(entry.getKey(), entry.getValue(), labelCounts));
        }
        return records;
    }
}
