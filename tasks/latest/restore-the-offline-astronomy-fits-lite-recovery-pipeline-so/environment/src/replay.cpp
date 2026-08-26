#include "replay.hpp"

#include "io.hpp"

#include <algorithm>

RecoveryPlan build_recovery_plan(const std::string& data_dir, const std::string& work_dir, const std::vector<OrderEntry>& authority) {
    RecoveryPlan plan;
    auto manifest = read_manifest(work_dir + "/tile-order.manifest");
    if (!manifest.empty()) {
        plan.expected_order = manifest;
        plan.source = "work-manifest";
    } else {
        for (const auto& entry : authority) plan.expected_order.push_back(entry.tile_id);
        plan.source = "authority";
    }

    for (const auto& rec : parse_journal(data_dir + "/journal/resume.tsv")) {
        if (rec.event == "PREPARE" || rec.event == "COMMIT") {
            if (std::find(plan.expected_order.begin(), plan.expected_order.end(), rec.tile_id) == plan.expected_order.end()) {
                plan.expected_order.push_back(rec.tile_id);
            }
        }
    }

    plan.committed_prefix = plan.expected_order;
    plan.resumed_tiles = plan.expected_order;
    return plan;
}
