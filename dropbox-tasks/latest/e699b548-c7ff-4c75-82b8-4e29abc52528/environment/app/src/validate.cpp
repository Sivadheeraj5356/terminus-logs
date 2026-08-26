#include "validate.h"
#include "plan_builder.h"
#include "graph.h"
#include "hash.h"
#include "row_overlap.h"
#include <algorithm>
#include <map>
#include <set>

static const char* ISSUE_TABLE[] = {
    "CATALOG_ERROR", "DUPLICATE_ID", "OVERLAP_CONFLICT", "ORDER_VIOLATION",
    "OVERLAP_TOO_SHORT", "GAP_DETECTED", "COVERAGE", "FINGERPRINT", "AMBIGUITY",
    "REPLICA_MISMATCH", "SCAN_COST", "FRAGMENTATION"
};

static int issue_weight(const std::string& e) {
    for (int i = 0; i < 12; ++i) {
        if (e == ISSUE_TABLE[i]) return i;
    }
    return 999;
}

static void add_error(ValidationResult& vr, const std::string& e) {
    if (std::find(vr.errors.begin(), vr.errors.end(), e) == vr.errors.end()) {
        vr.errors.push_back(e);
    }
}

ValidationResult validate_plan(const CompactionPlan& plan, const std::vector<Fragment>& fragments, const Policy& policy) {
    ValidationResult vr;
    std::map<uint16_t, Fragment> by_id;
    for (const auto& f : fragments) {
        if (by_id.count(f.id)) add_error(vr, "DUPLICATE_ID");
        by_id[f.id] = f;
    }
    if (plan.fragment_ids.size() != fragments.size()) add_error(vr, "COVERAGE");
    std::set<uint16_t> seen;
    for (uint16_t id : plan.fragment_ids) {
        if (!by_id.count(id)) add_error(vr, "COVERAGE");
        if (seen.count(id)) add_error(vr, "DUPLICATE_ID");
        seen.insert(id);
    }
    if (plan.fragment_ids.size() >= 2) {
        for (size_t i = 0; i + 1 < plan.fragment_ids.size(); ++i) {
            const Fragment& a = by_id[plan.fragment_ids[i]];
            const Fragment& b = by_id[plan.fragment_ids[i + 1]];
            if (b.seq < a.seq) add_error(vr, "ORDER_VIOLATION");
            int ov = row_junction_overlap(a, b, policy.min_row_overlap, policy.case_fold_ascii);
            int max_ov = row_junction_peak(a, b, policy.case_fold_ascii);
            if (ov == 0) add_error(vr, "GAP_DETECTED");
            else if (ov < policy.min_row_overlap) add_error(vr, "OVERLAP_TOO_SHORT");
            if (max_ov > 0 && ov > 0 && ov < max_ov) add_error(vr, "OVERLAP_CONFLICT");
            if (i < plan.row_overlap_lengths.size()) {
                if (plan.row_overlap_lengths[i] != ov) add_error(vr, "GAP_DETECTED");
                if (max_ov >= policy.min_row_overlap && plan.row_overlap_lengths[i] < max_ov) {
                    add_error(vr, "OVERLAP_CONFLICT");
                }
            }
            auto outgoing = select_outgoing_edge(a.id, fragments, policy);
            if (outgoing.has_value() && outgoing->to != b.id) add_error(vr, "AMBIGUITY");
        }
    }
    CompactionPlan rebuilt = build_compaction_plan(fragments, policy);
    if (plan.total_rows != rebuilt.total_rows) add_error(vr, "GAP_DETECTED");
    if (plan.scan_cost_units != rebuilt.scan_cost_units) add_error(vr, "SCAN_COST");
    if (plan.fragmentation_index != rebuilt.fragmentation_index) add_error(vr, "FRAGMENTATION");
    if (plan.replica_consistent != rebuilt.replica_consistent) add_error(vr, "REPLICA_MISMATCH");
    std::string fp = fingerprint_hex(plan_signature(plan));
    if (plan.fingerprint != fp) add_error(vr, "FINGERPRINT");
    vr.fingerprint = fp;
    if (!vr.errors.empty()) {
        std::sort(vr.errors.begin(), vr.errors.end(), [](const std::string& a, const std::string& b) {
            return issue_weight(a) > issue_weight(b);
        });
        vr.primary_error = vr.errors[0];
        vr.ok = false;
        return vr;
    }
    vr.ok = true;
    vr.primary_error.clear();
    return vr;
}
