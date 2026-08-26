#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

#include "cryoready/assess.hpp"
#include "cryoready/certificate.hpp"
#include "cryoready/digest.hpp"
#include "cryoready/inventory.hpp"
#include "cryoready/ledger.hpp"
#include "cryoready/load.hpp"

namespace {

void usage() {
    std::cerr
        << "usage: cryoready inventory --facility <path> --catalog <path> --maintenance <path>\n"
        << "       cryoready assess --facility <path> --catalog <path> --maintenance <path> "
           "--output-report <path> --output-certificate <path>\n";
}

std::string flag_value(int argc, char** argv, const std::string& flag) {
    for (int i = 1; i < argc - 1; ++i) {
        if (argv[i] == flag) {
            return argv[i + 1];
        }
    }
    return "";
}

void write_json(const std::string& path, const nlohmann::json& doc) {
    std::ofstream out(path);
    if (!out) {
        throw std::runtime_error("cannot write output: " + path);
    }
    out << doc.dump(2) << '\n';
}

int cmd_inventory(int argc, char** argv) {
    auto facility_path = flag_value(argc, argv, "--facility");
    auto catalog_path = flag_value(argc, argv, "--catalog");
    auto maintenance_path = flag_value(argc, argv, "--maintenance");
    if (facility_path.empty() || catalog_path.empty() || maintenance_path.empty()) {
        usage();
        return 2;
    }
    auto facility = cryoready::load_facility(facility_path);
    auto catalog = cryoready::load_catalog(catalog_path);
    auto maint = cryoready::load_maintenance(maintenance_path);
    auto stage = cryoready::build_inventory_stage(
        facility, catalog, maint, facility_path, catalog_path, maintenance_path);
    cryoready::write_inventory_stage(stage);
    cryoready::record_inventory_run(
        cryoready::ledger_path(),
        stage.at("facility_digest").get<std::string>(),
        stage.at("catalog_digest").get<std::string>(),
        stage.at("maintenance_digest").get<std::string>(),
        stage.at("inventory_digest").get<std::string>());
    return 0;
}

int cmd_assess(int argc, char** argv) {
    auto facility_path = flag_value(argc, argv, "--facility");
    auto catalog_path = flag_value(argc, argv, "--catalog");
    auto maintenance_path = flag_value(argc, argv, "--maintenance");
    auto report_path = flag_value(argc, argv, "--output-report");
    auto cert_path = flag_value(argc, argv, "--output-certificate");
    if (facility_path.empty() || catalog_path.empty() || maintenance_path.empty() || report_path.empty() ||
        cert_path.empty()) {
        usage();
        return 2;
    }
    nlohmann::json stage;
    try {
        stage = cryoready::load_inventory_stage();
    } catch (const std::exception& ex) {
        std::cerr << "inventory required: " << ex.what() << "\n";
        return 2;
    }
    auto facility = cryoready::load_facility(facility_path);
    auto catalog = cryoready::load_catalog(catalog_path);
    auto maint = cryoready::load_maintenance(maintenance_path);
    nlohmann::json report;
    try {
        report = cryoready::build_readiness_report(
            facility, catalog, maint, stage, facility_path, catalog_path, maintenance_path);
    } catch (const std::exception& ex) {
        std::cerr << ex.what() << "\n";
        return 2;
    }
    auto certificate = cryoready::build_certificate(report);
    write_json(report_path, report);
    write_json(cert_path, certificate);
    cryoready::record_assess_run(
        cryoready::ledger_path(),
        report.at("facility_digest").get<std::string>(),
        report.at("catalog_digest").get<std::string>(),
        report.at("maintenance_digest").get<std::string>(),
        report.at("report_digest").get<std::string>());
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        usage();
        return 2;
    }
    try {
        const std::string cmd = argv[1];
        if (cmd == "inventory") {
            return cmd_inventory(argc, argv);
        }
        if (cmd == "assess") {
            return cmd_assess(argc, argv);
        }
        usage();
        return 2;
    } catch (const std::exception& ex) {
        std::cerr << "error: " << ex.what() << "\n";
        return 1;
    }
}
