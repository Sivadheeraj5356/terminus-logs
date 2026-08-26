#pragma once
#include <cstdint>
#include <string>
#include <vector>

struct Fragment {
    uint16_t id = 0;
    uint16_t partition_id = 0;
    uint16_t seq = 0;
    uint16_t flags = 0;
    uint32_t row_start = 0;
    uint32_t row_end = 0;
    uint32_t byte_size = 0;
    uint16_t replica_mask = 0;
    std::string column_name;
    std::string normalized_column;
};

struct Policy {
    int min_row_overlap = 3;
    bool case_fold_ascii = true;
    int max_ambiguity = 0;
    uint16_t required_replica_mask = 0x0007;
    int scan_cost_per_byte = 1;
    int scan_penalty_per_gap = 10;
};

struct CompactionPlan {
    std::vector<uint16_t> fragment_ids;
    std::vector<int> row_overlap_lengths;
    uint32_t total_rows = 0;
    uint64_t scan_cost_units = 0;
    uint32_t fragmentation_index = 0;
    bool replica_consistent = false;
    std::string fingerprint;
};

struct ValidationResult {
    bool ok = false;
    std::string primary_error;
    std::vector<std::string> errors;
    std::string fingerprint;
};

struct RepairResult {
    bool ok = false;
    std::string primary_error;
    int swaps = 0;
    std::string fingerprint;
};

struct StagingSnapshot {
    int version = 1;
    std::string catalog_path;
    uint16_t open_fragment_id = 0;
    std::vector<uint16_t> chain_fragment_ids;
    std::vector<int> chain_overlaps;
    bool replica_summary = false;
    std::string catalog_digest;
};

inline constexpr const char* DEFAULT_SNAPSHOT_PATH = "/app/state/compaction-snapshot.json";
