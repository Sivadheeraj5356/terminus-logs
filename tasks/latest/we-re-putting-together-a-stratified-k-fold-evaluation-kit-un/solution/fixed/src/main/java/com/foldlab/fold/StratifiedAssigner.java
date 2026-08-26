package com.foldlab.fold;

import com.foldlab.model.FoldRow;
import com.foldlab.util.CohortIds;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

public final class StratifiedAssigner {
    public Map<Integer, List<String>> assign(List<FoldRow> rows, int foldCount) {
        Map<String, List<FoldRow>> byLabel = new TreeMap<>();
        for (FoldRow row : rows) {
            byLabel.computeIfAbsent(row.getLabel(), ignored -> new ArrayList<>()).add(row);
        }
        Map<Integer, List<String>> folds = new HashMap<>();
        for (int i = 0; i < foldCount; i++) {
            folds.put(i, new ArrayList<>());
        }
        for (List<FoldRow> group : byLabel.values()) {
            group.sort(CohortIds.comparing(FoldRow::getId));
            for (int n = 0; n < group.size(); n++) {
                int foldId = n % foldCount;
                folds.get(foldId).add(group.get(n).getId());
            }
        }
        for (List<String> ids : folds.values()) {
            ids.sort(CohortIds.ORDER);
        }
        return folds;
    }
}
