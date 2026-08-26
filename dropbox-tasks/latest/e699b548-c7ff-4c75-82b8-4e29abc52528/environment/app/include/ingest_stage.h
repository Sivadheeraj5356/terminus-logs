#pragma once
#include "types.h"
#include <string>

struct IngestResult {
    bool ok = false;
    std::string error;
    StagingSnapshot snapshot;
};

IngestResult run_ingest_stage(
    const std::string& catalog_path,
    const Policy& policy,
    const std::vector<Fragment>& fragments);
