#include "cryoready/assess.hpp"

#include "cryoready/compat.hpp"
#include "cryoready/digest.hpp"
#include "cryoready/load.hpp"

#include <stdexcept>
#include <string>

namespace cryoready {

namespace {

const nlohmann::json* find_vessel_row(const nlohmann::json& vessels, const std::string& vessel_id) {
    for (const auto& row : vessels) {
        if (row.at("vessel_id").get<std::string>() == vessel_id) {
            return &row;
        }
    }
    return nullptr;
}

bool vessel_meets_request(const nlohmann::json& row, const PlacementRequest& req) {
    if (!row.at("ready").get<bool>()) {
        return false;
    }
    const std::string vclass = row.at("cryogen_class").get<std::string>();
    if (!specimen_compatible(req.specimen_class, vclass)) {
        return false;
    }
    if (row.at("hold_hours").get<double>() + 1e-9 < req.min_hold_hours) {
        return false;
    }
    return true;
}

std::string first_eligible(const nlohmann::json& vessels, const PlacementRequest& req) {
    for (const auto& row : vessels) {
        if (vessel_meets_request(row, req)) {
            return row.at("vessel_id").get<std::string>();
        }
    }
    return "";
}

}  // namespace

nlohmann::json build_readiness_report(
    const Facility& facility,
    const Catalog& catalog,
    const Maintenance& maint,
    const nlohmann::json& inventory_stage,
    const std::string& facility_path,
    const std::string& catalog_path,
    const std::string& maintenance_path) {
    (void)maint;
    (void)catalog;

    const std::string fac_d = sha256_file(facility_path);
    const std::string cat_d = sha256_file(catalog_path);
    const std::string mnt_d = sha256_file(maintenance_path);

    if (inventory_stage.value("facility_digest", "") != fac_d ||
        inventory_stage.value("catalog_digest", "") != cat_d ||
        inventory_stage.value("maintenance_digest", "") != mnt_d) {
        throw std::runtime_error("inventory stage digests stale; re-run inventory");
    }

    const auto& vessels = inventory_stage.at("vessels");
    int ready_count = 0;
    int blocked_count = 0;
    for (const auto& row : vessels) {
        if (row.at("ready").get<bool>()) {
            ready_count += 1;
        } else {
            blocked_count += 1;
        }
    }

    nlohmann::json placements = nlohmann::json::array();
    int satisfied = 0;
    for (const auto& req : facility.placements) {
        nlohmann::json reasons = nlohmann::json::array();
        std::string assigned;
        bool ok = false;

        if (!req.preferred_vessel_id.empty()) {
            const nlohmann::json* row = find_vessel_row(vessels, req.preferred_vessel_id);
            if (!row) {
                reasons.push_back("preferred_vessel_missing");
            } else if (!vessel_meets_request(*row, req)) {
                reasons.push_back("preferred_vessel_not_eligible");
            } else {
                assigned = req.preferred_vessel_id;
                ok = true;
            }
        }

        if (!ok) {
            assigned = first_eligible(vessels, req);
            if (!assigned.empty()) {
                ok = true;
            } else if (reasons.empty()) {
                reasons.push_back("no_compatible_ready_vessel");
            } else {
                reasons.push_back("no_compatible_ready_vessel");
            }
        }

        if (ok) {
            satisfied += 1;
            if (req.preferred_vessel_id.empty() || assigned == req.preferred_vessel_id) {
                reasons = nlohmann::json::array();
            }
        }

        placements.push_back({
            {"request_id", req.request_id},
            {"specimen_class", req.specimen_class},
            {"min_hold_hours", req.min_hold_hours},
            {"preferred_vessel_id", req.preferred_vessel_id},
            {"assigned_vessel_id", assigned.empty() ? nlohmann::json(nullptr) : nlohmann::json(assigned)},
            {"satisfied", ok},
            {"reasons", reasons},
        });
    }

    nlohmann::json report = {
        {"facility_id", facility.facility_id},
        {"assessment_epoch_unix", facility.assessment_epoch_unix},
        {"facility_digest", fac_d},
        {"catalog_digest", cat_d},
        {"maintenance_digest", mnt_d},
        {"inventory_digest", inventory_stage.at("inventory_digest")},
        {"vessels", vessels},
        {"placements", placements},
        {"ready_vessel_count", ready_count},
        {"blocked_vessel_count", blocked_count},
        {"satisfied_placement_count", satisfied},
        {"placement_request_count", static_cast<int>(facility.placements.size())},
    };
    report["report_digest"] = sha256_bytes(canonical_json_compact({
        {"facility_id", report["facility_id"]},
        {"assessment_epoch_unix", report["assessment_epoch_unix"]},
        {"facility_digest", report["facility_digest"]},
        {"catalog_digest", report["catalog_digest"]},
        {"maintenance_digest", report["maintenance_digest"]},
        {"inventory_digest", report["inventory_digest"]},
        {"vessels", report["vessels"]},
        {"placements", report["placements"]},
        {"ready_vessel_count", report["ready_vessel_count"]},
        {"blocked_vessel_count", report["blocked_vessel_count"]},
        {"satisfied_placement_count", report["satisfied_placement_count"]},
        {"placement_request_count", report["placement_request_count"]},
    }));
    return report;
}

}  // namespace cryoready
