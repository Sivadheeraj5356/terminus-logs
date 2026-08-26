#include "fragmentation.h"
#include <map>

uint32_t compute_fragmentation_index(const CompactionPlan& plan, const std::vector<Fragment>& fragments) {
    if (plan.fragment_ids.size() < 2) return 0;
    std::map<uint16_t, Fragment> by_id;
    for (const auto& f : fragments) by_id[f.id] = f;
    uint32_t gaps = 0;
    for (size_t i = 0; i + 1 < plan.fragment_ids.size(); ++i) {
        const Fragment& a = by_id[plan.fragment_ids[i]];
        const Fragment& b = by_id[plan.fragment_ids[i + 1]];
        if (b.row_start > a.row_end + 1) {
            gaps += b.row_start - a.row_end - 1;
        }
    }
    if (plan.total_rows == 0) return gaps;
    return (gaps * 1000) / plan.total_rows;
}
