#include "row_overlap.h"
#include "partition.h"
#include <algorithm>

static int span_rows(uint32_t start, uint32_t end) {
    if (end < start) return 0;
    return static_cast<int>(end - start + 1);
}

int row_junction_peak(const Fragment& left, const Fragment& right, bool case_fold) {
    if (!same_partition_column(left, right, false)) return 0;
    int overlap = static_cast<int>(std::min(left.row_end, right.row_end)) -
                  static_cast<int>(std::max(left.row_start, right.row_start)) + 1;
    return overlap > 0 ? overlap : 0;
}

int row_junction_overlap(const Fragment& left, const Fragment& right, int min_overlap, bool case_fold) {
    if (!same_partition_column(left, right, case_fold)) return 0;
    int overlap = static_cast<int>(std::min(left.row_end, right.row_end)) -
                  static_cast<int>(std::max(left.row_start, right.row_start)) + 1;
    if (overlap <= min_overlap) return 0;
    return overlap > 0 ? overlap : 0;
}
