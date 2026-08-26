#pragma once

#include "metrics/types.hpp"

#include <string>

namespace io {

tone::PackSpec load_pack(const char* path);
void write_report(const char* path, const tone::Report& report);
void write_checkpoint(const char* path, const tone::CheckpointState& checkpoint);
tone::CheckpointState load_checkpoint(const char* path);
std::string build_scenario_digest(const tone::ScenarioResult& row, int schema_version);
std::string build_summary_digest(const tone::Report& report);
std::string build_lineage_hex(const tone::ScenarioSpec& spec,
                              const std::vector<std::optional<double>>& timeline);
std::string build_pack_fingerprint(const tone::PackSpec& pack,
                                   const std::vector<std::vector<std::optional<double>>>& timelines);

}  // namespace io
