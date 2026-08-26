#pragma once

#include <nlohmann/json.hpp>
#include <string>

namespace cryoready {

std::string ledger_path();
nlohmann::json load_ledger(const std::string& path);
void save_ledger(const std::string& path, const nlohmann::json& ledger);

std::string assess_ledger_key(
    const std::string& facility_digest,
    const std::string& catalog_digest,
    const std::string& maintenance_digest);

void record_inventory_run(
    const std::string& path,
    const std::string& facility_digest,
    const std::string& catalog_digest,
    const std::string& maintenance_digest,
    const std::string& inventory_digest);

void record_assess_run(
    const std::string& path,
    const std::string& facility_digest,
    const std::string& catalog_digest,
    const std::string& maintenance_digest,
    const std::string& report_digest);

}  // namespace cryoready
