#include "plan_builder.h"
#include "graph.h"
#include "hash.h"
#include "scan_cost.h"
#include "fragmentation.h"
#include "replica.h"
#include <map>

static uint32_t row_span(const Fragment& f) {
    return f.row_end >= f.row_start ? f.row_end - f.row_start + 1 : 0;
}

CompactionPlan build_compaction_plan(const std::vector<Fragment>& fragments, const Policy& policy) {
    CompactionPlan out;
    auto start = resolve_open_fragment(fragments, policy);
    if (!start.has_value()) return out;
    std::map<uint16_t, Fragment> by_id;
    for (const auto& f : fragments) by_id[f.id] = f;
    std::vector<uint16_t> order;
    order.push_back(*start);
    auto chain = trace_edge_path(fragments, policy);
    uint16_t cur = *start;
    for (const auto& e : chain) {
        if (e.from != cur) break;
        order.push_back(e.to);
        out.row_overlap_lengths.push_back(e.overlap);
        cur = e.to;
    }
    uint32_t total = row_span(by_id[order[0]]);
    for (size_t i = 1; i < order.size(); ++i) {
        const Fragment& next = by_id[order[i]];
        int ov = out.row_overlap_lengths[i - 1];
        total += row_span(next) - static_cast<uint32_t>(ov);
    }
    out.fragment_ids = order;
    out.total_rows = total;
    out.fragmentation_index = compute_fragmentation_index(out, fragments);
    out.replica_consistent = check_replica_consistency(fragments, policy);
    out.scan_cost_units = compute_scan_cost_units(out, fragments, policy);
    out.fingerprint = fingerprint_hex(plan_signature(out));
    return out;
}
