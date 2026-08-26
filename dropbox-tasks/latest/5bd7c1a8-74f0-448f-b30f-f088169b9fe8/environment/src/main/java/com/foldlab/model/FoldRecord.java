package com.foldlab.model;

import java.util.List;
import java.util.Map;

public final class FoldRecord {
    private final int foldId;
    private final List<String> rowIds;
    private final Map<String, Integer> labelCounts;

    public FoldRecord(int foldId, List<String> rowIds, Map<String, Integer> labelCounts) {
        this.foldId = foldId;
        this.rowIds = rowIds;
        this.labelCounts = labelCounts;
    }

    public int getFoldId() {
        return foldId;
    }

    public List<String> getRowIds() {
        return rowIds;
    }

    public Map<String, Integer> getLabelCounts() {
        return labelCounts;
    }
}
