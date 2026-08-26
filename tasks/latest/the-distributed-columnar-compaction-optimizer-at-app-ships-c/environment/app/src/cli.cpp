#include "cli.h"
#include "catalog.h"
#include "export_stage.h"
#include "ingest_stage.h"
#include "json_io.h"
#include "plan_builder.h"
#include "repair.h"
#include "report.h"
#include "staging_io.h"
#include "validate.h"
#include <iostream>
#include <string>
#include <sys/stat.h>

static void usage() {
    std::cerr << "USAGE\n";
}

static bool ensure_state_dir() {
    struct stat st {};
    if (stat("/app/state", &st) == 0 && S_ISDIR(st.st_mode)) return true;
    return mkdir("/app/state", 0755) == 0;
}

static int run_ingest_cmd(int argc, char** argv) {
    std::string catalog, policy, snapshot = DEFAULT_SNAPSHOT_PATH;
    for (int i = 2; i + 1 < argc; i += 2) {
        std::string flag = argv[i];
        if (flag == "--catalog") catalog = argv[i + 1];
        else if (flag == "--policy") policy = argv[i + 1];
        else if (flag == "--snapshot") snapshot = argv[i + 1];
    }
    if (catalog.empty() || policy.empty()) {
        usage();
        return 2;
    }
    auto parsed = parse_catalog_file(catalog);
    if (!parsed.ok) {
        std::cerr << parsed.error << "\n";
        return 1;
    }
    Policy pol;
    std::string err;
    if (!read_policy_file(policy, pol, err)) {
        std::cerr << err << "\n";
        return 1;
    }
    if (!ensure_state_dir()) {
        std::cerr << "IO_ERROR\n";
        return 1;
    }
    IngestResult ing = run_ingest_stage(catalog, pol, parsed.fragments);
    if (!ing.ok) {
        std::cerr << ing.error << "\n";
        return 1;
    }
    if (!write_staging_snapshot(snapshot, ing.snapshot, err)) {
        std::cerr << err << "\n";
        return 1;
    }
    return 0;
}

static int run_export_cmd(int argc, char** argv) {
    std::string catalog, policy, out, snapshot = DEFAULT_SNAPSHOT_PATH;
    for (int i = 2; i + 1 < argc; i += 2) {
        std::string flag = argv[i];
        if (flag == "--catalog") catalog = argv[i + 1];
        else if (flag == "--policy") policy = argv[i + 1];
        else if (flag == "--out") out = argv[i + 1];
        else if (flag == "--snapshot") snapshot = argv[i + 1];
    }
    if (catalog.empty() || policy.empty() || out.empty()) {
        usage();
        return 2;
    }
    StagingSnapshot snap;
    std::string err;
    if (!read_staging_snapshot(snapshot, snap, err)) {
        std::cerr << err << "\n";
        return 1;
    }
    auto parsed = parse_catalog_file(catalog);
    if (!parsed.ok) {
        std::cerr << parsed.error << "\n";
        return 1;
    }
    if (!staging_snapshot_matches_catalog(snap, parsed.fragments)) {
        std::cerr << "STALE_SNAPSHOT\n";
        return 1;
    }
    Policy pol;
    if (!read_policy_file(policy, pol, err)) {
        std::cerr << err << "\n";
        return 1;
    }
    CompactionPlan plan = export_plan_from_staging(snap, parsed.fragments, pol);
    ValidationResult vr = validate_plan(plan, parsed.fragments, pol);
    if (!vr.ok) {
        std::cerr << vr.primary_error << "\n";
        return 1;
    }
    if (!write_text_file(out, plan_to_json(plan), err)) {
        std::cerr << err << "\n";
        return 1;
    }
    std::cout << plan_to_json(plan);
    return 0;
}

int run_cli(int argc, char** argv) {
    if (argc < 2) {
        usage();
        return 2;
    }
    std::string cmd = argv[1];
    if (cmd == "ingest") return run_ingest_cmd(argc, argv);
    if (cmd == "export") return run_export_cmd(argc, argv);
    if (cmd == "plan") {
        std::string catalog, policy, out;
        for (int i = 2; i + 1 < argc; i += 2) {
            std::string flag = argv[i];
            if (flag == "--catalog") catalog = argv[i + 1];
            else if (flag == "--policy") policy = argv[i + 1];
            else if (flag == "--out") out = argv[i + 1];
        }
        if (catalog.empty() || policy.empty() || out.empty()) {
            usage();
            return 2;
        }
        if (!ensure_state_dir()) {
            std::cerr << "IO_ERROR\n";
            return 1;
        }
        auto parsed = parse_catalog_file(catalog);
        if (!parsed.ok) {
            std::cerr << parsed.error << "\n";
            return 1;
        }
        Policy pol;
        std::string err;
        if (!read_policy_file(policy, pol, err)) {
            std::cerr << err << "\n";
            return 1;
        }
        IngestResult ing = run_ingest_stage(catalog, pol, parsed.fragments);
        if (!ing.ok) {
            std::cerr << ing.error << "\n";
            return 1;
        }
        if (!write_staging_snapshot(DEFAULT_SNAPSHOT_PATH, ing.snapshot, err)) {
            std::cerr << err << "\n";
            return 1;
        }
        StagingSnapshot snap;
        if (!read_staging_snapshot(DEFAULT_SNAPSHOT_PATH, snap, err)) {
            std::cerr << err << "\n";
            return 1;
        }
        if (!staging_snapshot_matches_catalog(snap, parsed.fragments)) {
            std::cerr << "STALE_SNAPSHOT\n";
            return 1;
        }
        CompactionPlan plan = export_plan_from_staging(snap, parsed.fragments, pol);
        ValidationResult vr = validate_plan(plan, parsed.fragments, pol);
        if (!vr.ok) {
            std::cerr << vr.primary_error << "\n";
            return 1;
        }
        if (!write_text_file(out, plan_to_json(plan), err)) {
            std::cerr << err << "\n";
            return 1;
        }
        std::cout << plan_to_json(plan);
        return 0;
    }
    if (cmd == "validate") {
        std::string catalog, plan_path, policy_path = "/app/data/policies/default.json";
        for (int i = 2; i + 1 < argc; i += 2) {
            std::string flag = argv[i];
            if (flag == "--catalog") catalog = argv[i + 1];
            else if (flag == "--plan") plan_path = argv[i + 1];
            else if (flag == "--policy") policy_path = argv[i + 1];
        }
        if (catalog.empty() || plan_path.empty()) {
            usage();
            return 2;
        }
        auto parsed = parse_catalog_file(catalog);
        if (!parsed.ok) {
            std::cerr << parsed.error << "\n";
            return 1;
        }
        Policy pol;
        std::string err;
        if (!read_policy_file(policy_path, pol, err)) {
            std::cerr << err << "\n";
            return 1;
        }
        CompactionPlan plan;
        if (!read_plan_file(plan_path, plan, err)) {
            std::cerr << err << "\n";
            return 1;
        }
        ValidationResult vr = validate_plan(plan, parsed.fragments, pol);
        if (!vr.ok) {
            std::cerr << vr.primary_error << "\n";
            return 1;
        }
        std::cout << validation_to_json(vr);
        return 0;
    }
    if (cmd == "repair") {
        std::string catalog, plan_path, policy_path = "/app/data/policies/default.json", out;
        for (int i = 2; i + 1 < argc; i += 2) {
            std::string flag = argv[i];
            if (flag == "--catalog") catalog = argv[i + 1];
            else if (flag == "--plan") plan_path = argv[i + 1];
            else if (flag == "--policy") policy_path = argv[i + 1];
            else if (flag == "--out") out = argv[i + 1];
        }
        if (catalog.empty() || plan_path.empty() || out.empty()) {
            usage();
            return 2;
        }
        auto parsed = parse_catalog_file(catalog);
        if (!parsed.ok) {
            std::cerr << parsed.error << "\n";
            return 1;
        }
        Policy pol;
        std::string err;
        if (!read_policy_file(policy_path, pol, err)) {
            std::cerr << err << "\n";
            return 1;
        }
        CompactionPlan plan;
        if (!read_plan_file(plan_path, plan, err)) {
            std::cerr << err << "\n";
            return 1;
        }
        RepairResult rr = repair_plan(plan, parsed.fragments, pol);
        if (!rr.ok) {
            std::cerr << rr.primary_error << "\n";
            return 1;
        }
        note_repair_snapshot_reset(parsed.fragments);
        if (!write_text_file(out, plan_to_json(plan), err)) {
            std::cerr << err << "\n";
            return 1;
        }
        std::cout << repair_to_json(rr);
        return 0;
    }
    usage();
    return 2;
}
