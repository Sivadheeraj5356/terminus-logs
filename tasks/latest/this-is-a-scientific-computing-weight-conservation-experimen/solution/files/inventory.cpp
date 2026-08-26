#include "cryoready/inventory.hpp"

#include "cryoready/compat.hpp"
#include "cryoready/digest.hpp"
#include "cryoready/fill.hpp"
#include "cryoready/hold.hpp"
#include "cryoready/load.hpp"
#include "cryoready/pressure.hpp"
#include "cryoready/sensors.hpp"
#include "cryoready/windows.hpp"

#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <cmath>
#include <stdexcept>

namespace cryoready {

namespace {

double round6(double v) {
    return std::round(v * 1e6) / 1e6;
}

}  // namespace


std::string inventory_stage_path() {
    const char* dir = std::getenv("CRYOREADY_STATE_DIR");
    std::string base = dir ? dir : kDefaultStateDir;
    return base + "/" + kInventoryStageName;
}

void write_inventory_stage(const nlohmann::json& stage) {
    const std::string path = inventory_stage_path();
    std::filesystem::path p(path);
    if (p.has_parent_path()) {
        std::filesystem::create_directories(p.parent_path());
    }
    std::ofstream out(path);
    if (!out) {
        throw std::runtime_error("cannot write inventory stage: " + path);
    }
    out << stage.dump(2) << '\n';
}

nlohmann::json load_inventory_stage() {
    const std::string path = inventory_stage_path();
    std::ifstream in(path);
    if (!in) {
        throw std::runtime_error("inventory stage missing: " + path);
    }
    nlohmann::json doc;
    in >> doc;
    return doc;
}

nlohmann::json build_inventory_stage(
    const Facility& facility,
    const Catalog& catalog,
    const Maintenance& maint,
    const std::string& facility_path,
    const std::string& catalog_path,
    const std::string& maintenance_path) {
    std::vector<Vessel> vessels = facility.vessels;
    std::sort(vessels.begin(), vessels.end(), [](const Vessel& a, const Vessel& b) {
        return a.vessel_id < b.vessel_id;
    });

    nlohmann::json vessel_rows = nlohmann::json::array();
    for (const auto& v : vessels) {
        const ModelSpec* model = find_model(catalog, v.model_id);
        if (!model) {
            throw std::runtime_error("unknown model_id: " + v.model_id);
        }
        const double frac = round6(fill_fraction(v.level_liters, *model));
        const double hold = round6(hold_hours(v.level_liters, *model));
        const double psia = round6(pressure_psia(v.pressure_psig));
        const bool maint_block = in_maintenance(maint, v.vessel_id, facility.assessment_epoch_unix);
        const bool cal_ok = sensor_cal_ok(v.sensor_calibrated_until_unix, facility.assessment_epoch_unix);
        const bool fill_ok = fill_in_range(frac, *model);
        const bool press_ok = pressure_ok(v.pressure_psig, *model);

        nlohmann::json reasons = nlohmann::json::array();
        if (maint_block) {
            reasons.push_back("in_maintenance");
        }
        if (!cal_ok) {
            reasons.push_back("sensor_cal_expired");
        }
        if (!fill_ok) {
            if (frac < model->min_fill_fraction) {
                reasons.push_back("fill_below_min");
            } else {
                reasons.push_back("fill_above_max");
            }
        }
        if (!press_ok) {
            reasons.push_back("pressure_exceeds_mawp");
        }

        const bool ready = reasons.empty();
        vessel_rows.push_back({
            {"vessel_id", v.vessel_id},
            {"model_id", v.model_id},
            {"cryogen", v.cryogen},
            {"cryogen_class", model->cryogen_class},
            {"level_liters", v.level_liters},
            {"fill_fraction", frac},
            {"pressure_psig", v.pressure_psig},
            {"pressure_psia", psia},
            {"hold_hours", hold},
            {"sensor_calibrated_until_unix", v.sensor_calibrated_until_unix},
            {"ready", ready},
            {"reasons", reasons},
        });
    }

    nlohmann::json stage = {
        {"facility_id", facility.facility_id},
        {"assessment_epoch_unix", facility.assessment_epoch_unix},
        {"facility_digest", sha256_file(facility_path)},
        {"catalog_digest", sha256_file(catalog_path)},
        {"maintenance_digest", sha256_file(maintenance_path)},
        {"vessels", vessel_rows},
    };
    stage["inventory_digest"] = sha256_bytes(canonical_json_compact({
        {"assessment_epoch_unix", stage["assessment_epoch_unix"]},
        {"facility_digest", stage["facility_digest"]},
        {"catalog_digest", stage["catalog_digest"]},
        {"maintenance_digest", stage["maintenance_digest"]},
        {"facility_id", stage["facility_id"]},
        {"vessels", stage["vessels"]},
    }));
    return stage;
}

}  // namespace cryoready
