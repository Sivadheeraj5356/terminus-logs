#include "cryoready/certificate.hpp"

#include "cryoready/digest.hpp"

namespace cryoready {

nlohmann::json build_certificate(const nlohmann::json& report) {
    const bool all_placements =
        report.at("satisfied_placement_count").get<int>() == report.at("placement_request_count").get<int>();
    const bool certificate_ok = report.at("ready_vessel_count").get<int>() > 0;

    nlohmann::json cert = {
        {"facility_id", report.at("facility_id")},
        {"assessment_epoch_unix", report.at("assessment_epoch_unix")},
        {"report_digest", report.at("report_digest")},
        {"facility_digest", report.at("facility_digest")},
        {"catalog_digest", report.at("catalog_digest")},
        {"maintenance_digest", report.at("maintenance_digest")},
        {"inventory_digest", report.at("inventory_digest")},
        {"all_placements_satisfied", all_placements},
        {"ready_vessel_count", report.at("ready_vessel_count")},
        {"blocked_vessel_count", report.at("blocked_vessel_count")},
        {"certificate_ok", certificate_ok},
    };
    cert["certificate_digest"] = sha256_bytes(canonical_json_compact({
        {"facility_id", cert["facility_id"]},
        {"assessment_epoch_unix", cert["assessment_epoch_unix"]},
        {"report_digest", cert["report_digest"]},
        {"facility_digest", cert["facility_digest"]},
        {"catalog_digest", cert["catalog_digest"]},
        {"maintenance_digest", cert["maintenance_digest"]},
        {"inventory_digest", cert["inventory_digest"]},
        {"all_placements_satisfied", cert["all_placements_satisfied"]},
        {"ready_vessel_count", cert["ready_vessel_count"]},
        {"blocked_vessel_count", cert["blocked_vessel_count"]},
        {"certificate_ok", cert["certificate_ok"]},
    }));
    return cert;
}

}  // namespace cryoready
