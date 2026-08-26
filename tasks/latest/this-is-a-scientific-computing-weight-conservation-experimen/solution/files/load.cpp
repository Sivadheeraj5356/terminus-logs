#include "cryoready/load.hpp"

#include <fstream>
#include <stdexcept>

namespace cryoready {

namespace {

nlohmann::json read_json(const std::string& path) {
    std::ifstream in(path);
    if (!in) {
        throw std::runtime_error("cannot open: " + path);
    }
    nlohmann::json doc;
    in >> doc;
    return doc;
}

}  // namespace

Facility load_facility(const std::string& path) {
    auto doc = read_json(path);
    Facility f;
    f.facility_id = doc.at("facility_id").get<std::string>();
    f.assessment_epoch_unix = doc.at("assessment_epoch_unix").get<long long>();
    for (const auto& v : doc.at("vessels")) {
        Vessel vessel;
        vessel.vessel_id = v.at("vessel_id").get<std::string>();
        vessel.model_id = v.at("model_id").get<std::string>();
        vessel.cryogen = v.at("cryogen").get<std::string>();
        vessel.level_liters = v.at("level_liters").get<double>();
        vessel.pressure_psig = v.at("pressure_psig").get<double>();
        vessel.sensor_calibrated_until_unix = v.at("sensor_calibrated_until_unix").get<long long>();
        f.vessels.push_back(vessel);
    }
    if (doc.contains("placement_requests")) {
        for (const auto& p : doc.at("placement_requests")) {
            PlacementRequest req;
            req.request_id = p.at("request_id").get<std::string>();
            req.specimen_class = p.at("specimen_class").get<std::string>();
            req.min_hold_hours = p.at("min_hold_hours").get<double>();
            if (p.contains("preferred_vessel_id") && !p.at("preferred_vessel_id").is_null()) {
                req.preferred_vessel_id = p.at("preferred_vessel_id").get<std::string>();
            }
            f.placements.push_back(req);
        }
    }
    return f;
}

Catalog load_catalog(const std::string& path) {
    auto doc = read_json(path);
    Catalog c;
    for (const auto& m : doc.at("models")) {
        ModelSpec spec;
        spec.model_id = m.at("model_id").get<std::string>();
        spec.cryogen_class = m.at("cryogen_class").get<std::string>();
        spec.gross_capacity_l = m.at("gross_capacity_l").get<double>();
        spec.usable_capacity_l = m.at("usable_capacity_l").get<double>();
        spec.mawp_psia = m.at("mawp_psia").get<double>();
        spec.setpoint_k = m.at("setpoint_k").get<double>();
        spec.boil_off_l_per_day = m.at("boil_off_l_per_day").get<double>();
        spec.min_fill_fraction = m.at("min_fill_fraction").get<double>();
        spec.max_fill_fraction = m.at("max_fill_fraction").get<double>();
        spec.hold_reserve_fraction = m.at("hold_reserve_fraction").get<double>();
        c.models.push_back(spec);
    }
    return c;
}

Maintenance load_maintenance(const std::string& path) {
    auto doc = read_json(path);
    Maintenance m;
    for (const auto& w : doc.at("windows")) {
        MaintenanceWindow win;
        win.window_id = w.at("window_id").get<std::string>();
        win.vessel_id = w.at("vessel_id").get<std::string>();
        win.start_unix = w.at("start_unix").get<long long>();
        win.end_unix = w.at("end_unix").get<long long>();
        win.kind = w.value("kind", "");
        m.windows.push_back(win);
    }
    return m;
}

const ModelSpec* find_model(const Catalog& catalog, const std::string& model_id) {
    for (const auto& m : catalog.models) {
        if (m.model_id == model_id) {
            return &m;
        }
    }
    return nullptr;
}

}  // namespace cryoready
