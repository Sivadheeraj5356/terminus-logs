#include "export_stage.h"
#include "hash.h"
#include "scan_cost.h"
#include "fragmentation.h"
#include "replica.h"
#include <map>

static uint32_t row_span(const Fragment& f) {
    return f.row_end >= f.row_start ? f.row_end - f.row_start + 1 : 0;
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
    uint32_t total = row_span(by_id.at(out.fragment_ids[0]));
    for (size_t i = 1; i < out.fragment_ids.size(); ++i) {
        const Fragment& next = by_id.at(out.fragment_ids[i]);
        int ov = out.row_overlap_lengths[i - 1];
        total += row_span(next) - static_cast<uint32_t>(ov);
    }
    out.total_rows = total;
    out.replica_consistent = check_replica_consistency(fragments, policy);
    out.fragmentation_index = compute_fragmentation_index(out, fragments);
    out.scan_cost_units = compute_scan_cost_units(out, fragments, policy);
    out.fingerprint = fingerprint_hex(plan_signature(out));
    return out;
}
