#include "cryoready/ledger.hpp"

#include "cryoready/types.hpp"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <stdexcept>

namespace cryoready {

std::string ledger_path() {
    const char* env = std::getenv("CRYOREADY_LEDGER_PATH");
    return env ? env : kDefaultLedgerPath;
}

nlohmann::json load_ledger(const std::string& path) {
    std::ifstream in(path);
    if (!in) {
        return {{"write_seq", 0}, {"entries", nlohmann::json::object()}};
    }
    try {
        nlohmann::json doc;
        in >> doc;
        if (!doc.contains("entries")) {
            doc["entries"] = nlohmann::json::object();
        }
        if (!doc.contains("write_seq")) {
            doc["write_seq"] = 0;
        }
        return doc;
    } catch (...) {
        return {{"write_seq", 0}, {"entries", nlohmann::json::object()}};
    }
}

void save_ledger(const std::string& path, const nlohmann::json& ledger) {
    std::filesystem::path p(path);
    if (p.has_parent_path()) {
        std::filesystem::create_directories(p.parent_path());
    }
    std::ofstream out(path);
    if (!out) {
        throw std::runtime_error("cannot write ledger: " + path);
    }
    out << ledger.dump(2) << '\n';
}

std::string assess_ledger_key(
    const std::string& facility_digest,
    const std::string& catalog_digest,
    const std::string& maintenance_digest) {
    (void)catalog_digest;
    (void)maintenance_digest;
    return facility_digest;
}

namespace {

nlohmann::json default_entry() {
    return {
        {"inventory_runs", 0},
        {"assess_runs", 0},
        {"last_inventory_digest", ""},
        {"last_report_digest", ""},
    };
}

}  // namespace

void record_inventory_run(
    const std::string& path,
    const std::string& facility_digest,
    const std::string& catalog_digest,
    const std::string& maintenance_digest,
    const std::string& inventory_digest) {
    auto ledger = load_ledger(path);
    auto& entries = ledger["entries"];
    const std::string key = assess_ledger_key(facility_digest, catalog_digest, maintenance_digest);
    if (!entries.contains(key)) {
        entries[key] = default_entry();
    }
    auto& entry = entries[key];
    entry["inventory_runs"] = entry.value("inventory_runs", 0) + 1;
    entry["last_inventory_digest"] = inventory_digest;
    ledger["write_seq"] = ledger.value("write_seq", 0) + 1;
    save_ledger(path, ledger);
}

void record_assess_run(
    const std::string& path,
    const std::string& facility_digest,
    const std::string& catalog_digest,
    const std::string& maintenance_digest,
    const std::string& report_digest) {
    auto ledger = load_ledger(path);
    auto& entries = ledger["entries"];
    const std::string key = assess_ledger_key(facility_digest, catalog_digest, maintenance_digest);
    if (!entries.contains(key)) {
        entries[key] = default_entry();
    }
    auto& entry = entries[key];
    const std::string prev = entry.value("last_report_digest", "");
    if (prev != report_digest) {
        entry["assess_runs"] = entry.value("assess_runs", 0) + 1;
    }
    entry["last_report_digest"] = report_digest;
    ledger["write_seq"] = ledger.value("write_seq", 0) + 1;
    save_ledger(path, ledger);
}

}  // namespace cryoready
