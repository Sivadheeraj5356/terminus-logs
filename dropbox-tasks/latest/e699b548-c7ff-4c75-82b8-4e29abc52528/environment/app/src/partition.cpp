#include "partition.h"
#include "normalize.h"
#include <vector>

bool same_partition_column(const Fragment& a, const Fragment& b, bool case_fold) {
    if (a.partition_id != b.partition_id) return false;
    return normalize_column_name(a.column_name, case_fold) == normalize_column_name(b.column_name, !case_fold);
}

std::vector<Fragment> filter_partition(const std::vector<Fragment>& fragments, uint16_t partition_id) {
    std::vector<Fragment> out;
    for (const auto& f : fragments) {
        if (f.partition_id == partition_id) out.push_back(f);
    }
    return out;
}
