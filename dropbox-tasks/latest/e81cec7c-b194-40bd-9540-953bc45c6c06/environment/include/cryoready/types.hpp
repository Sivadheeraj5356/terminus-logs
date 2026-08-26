#pragma once

#include <nlohmann/json.hpp>
#include <string>
#include <vector>

namespace cryoready {

inline constexpr double kAtmPsia = 14.6959;
inline constexpr const char* kDefaultLedgerPath = "/app/var/cryoready-ledger.json";
inline constexpr const char* kDefaultStateDir = "/app/state";
inline constexpr const char* kInventoryStageName = "inventory-stage.json";

struct ModelSpec {
    std::string model_id;
    std::string cryogen_class;
    double gross_capacity_l = 0;
    double usable_capacity_l = 0;
    double mawp_psia = 0;
    double setpoint_k = 0;
    double boil_off_l_per_day = 0;
    double min_fill_fraction = 0;
    double max_fill_fraction = 0;
    double hold_reserve_fraction = 0;
};

struct Vessel {
    std::string vessel_id;
    std::string model_id;
    std::string cryogen;
    double level_liters = 0;
    double pressure_psig = 0;
    long long sensor_calibrated_until_unix = 0;
};

struct PlacementRequest {
    std::string request_id;
    std::string specimen_class;
    double min_hold_hours = 0;
    std::string preferred_vessel_id;
};

struct MaintenanceWindow {
    std::string window_id;
    std::string vessel_id;
    long long start_unix = 0;
    long long end_unix = 0;
    std::string kind;
};

struct Facility {
    std::string facility_id;
    long long assessment_epoch_unix = 0;
    std::vector<Vessel> vessels;
    std::vector<PlacementRequest> placements;
};

struct Catalog {
    std::vector<ModelSpec> models;
};

struct Maintenance {
    std::vector<MaintenanceWindow> windows;
};

}  // namespace cryoready
