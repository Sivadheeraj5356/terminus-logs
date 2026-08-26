#pragma once
#include "types.h"
#include <optional>
#include <vector>

struct IngestChainResult {
    uint16_t open_fragment_id = 0;
    std::vector<uint16_t> chain_fragment_ids;
    std::vector<int> chain_overlaps;
};

IngestChainResult trace_ingest_chain(const std::vector<Fragment>& fragments, const Policy& policy);
bool evaluate_replica_coverage(const std::vector<Fragment>& fragments, const Policy& policy);
