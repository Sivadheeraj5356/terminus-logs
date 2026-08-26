#pragma once

#include "vx_types.hpp"

#include <cstdint>
#include <string>
#include <utility>
#include <vector>

std::string JoinNotes(const std::vector<std::string>& notes);

std::string facet_hex_for(const std::string& canonical, const std::string& triple,
                          const std::string& reloc, double weight);
std::string canonical_id(const std::string& id);
std::string matrix_digest(const std::vector<Row>& rows);
int span_band(const std::vector<Row>& rows);
bool coherent(const std::vector<Row>& rows);

struct PipelineInput {
    Profile profile = Profile::Prep;
    bool hook_replay = false;
    int seed = 0;
    std::string out_path = "/app/output/failover_report.json";
    std::string env_root = "/app/environment";
};

int run_pipeline(const PipelineInput& in);
