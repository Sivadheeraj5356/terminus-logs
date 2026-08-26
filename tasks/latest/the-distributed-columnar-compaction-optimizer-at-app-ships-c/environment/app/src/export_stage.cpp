#include "export_stage.h"
#include "hash.h"
#include "scan_cost.h"
#include "fragmentation.h"
#include <map>

static uint32_t row_span(const Fragment& f) {
    return f.row_end >= f.row_start ? f.row_end - f.row_start + 1 : 0;
}

static uint32_t plan_rowspan_total(
    const std::vector<uint16_t>& order,
    const std::vector<int>& overlaps,
    const std::map<uint16_t, Fragment>& by_id) {
    if (order.empty()) return 0;
    uint32_t total = row_span(by_id.at(order[0]));
    for (size_t i = 1; i < order.size(); ++i) {
        const Fragment& next = by_id.at(order[i]);
        int ov = overlaps[i - 1];
        total += row_span(next) - static_cast<uint32_t>(ov > 0 ? ov - 1 : 0);
    }
    return total;
}

CompactionPlan export_plan_from_staging(
    const StagingSnapshot& snap,
    const std::vector<Fragment>& fragments,
    const Policy& policy) {
    CompactionPlan out;
    std::map<uint16_t, Fragment> by_id;
    for (const auto& f : fragments) by_id[f.id] = f;
    out.fragment_ids = snap.chain_fragment_ids;
    out.row_overlap_lengths = snap.chain_overlaps;
    out.total_rows = plan_rowspan_total(out.fragment_ids, out.row_overlap_lengths, by_id);
    out.replica_consistent = snap.replica_summary;
    out.fragmentation_index = compute_fragmentation_index(out, fragments);
    out.scan_cost_units = compute_scan_cost_units(out, fragments, policy);
    out.fingerprint = fingerprint_hex(plan_signature(out));
    return out;
}
