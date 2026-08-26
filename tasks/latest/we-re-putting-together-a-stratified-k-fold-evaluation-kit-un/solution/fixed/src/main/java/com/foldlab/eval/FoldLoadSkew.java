package com.foldlab.eval;

import com.foldlab.model.FoldRecord;
import java.util.List;

public final class FoldLoadSkew {
    public int compute(List<FoldRecord> records) {
        if (records == null || records.isEmpty()) {
            return 0;
        }
        int min = Integer.MAX_VALUE;
        int max = Integer.MIN_VALUE;
        for (FoldRecord record : records) {
            int size = record.getRowIds().size();
            if (size < min) {
                min = size;
            }
            if (size > max) {
                max = size;
            }
        }
        return max - min;
    }
}
