package com.foldlab.eval;

import com.foldlab.model.FoldRecord;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public final class LabelCardinality {
    public int compute(List<FoldRecord> records) {
        if (records == null || records.isEmpty()) {
            return 0;
        }
        Set<String> labels = new HashSet<>();
        for (FoldRecord record : records) {
            labels.addAll(record.getLabelCounts().keySet());
        }
        return labels.size();
    }
}
