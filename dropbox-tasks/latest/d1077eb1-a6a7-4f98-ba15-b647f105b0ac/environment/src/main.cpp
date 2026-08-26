#include "io/pack_io.hpp"
#include "metrics/pipeline.hpp"
#include "metrics/reconstruct.hpp"

#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

namespace {

void usage() {
  std::cerr << "usage: hann_energy_audit --pack <path> --out <path> [--checkpoint <path>]\n";
}

}  // namespace

int main(int argc, char** argv) {
  const char* pack_path = nullptr;
  const char* out_path = nullptr;
  const char* checkpoint_path = nullptr;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    if (arg == "--pack" && i + 1 < argc) {
      pack_path = argv[++i];
    } else if (arg == "--out" && i + 1 < argc) {
      out_path = argv[++i];
    } else if (arg == "--checkpoint" && i + 1 < argc) {
      checkpoint_path = argv[++i];
    } else {
      usage();
      return 2;
    }
  }
  if (pack_path == nullptr || out_path == nullptr) {
    usage();
    return 2;
  }

  const std::filesystem::path out_file(out_path);
  if (out_file.has_parent_path()) {
    std::filesystem::create_directories(out_file.parent_path());
  }

  try {
    const tone::PackSpec pack = io::load_pack(pack_path);
    if (checkpoint_path != nullptr && pack.schema_version < 3) {
      throw std::runtime_error("checkpoint requires schema_version 3");
    }

    std::vector<std::vector<std::optional<double>>> timelines;
    timelines.reserve(pack.scenarios.size());
    for (const auto& scenario : pack.scenarios) {
      if (scenario.timeline_len > 0) {
        timelines.push_back(tone::reconstruct_timeline(scenario));
      } else {
        timelines.push_back(scenario.samples);
      }
    }

    tone::Report report;
    report.schema_version = pack.schema_version;
    report.summary.scenario_count = pack.scenarios.size();
    for (const auto& scenario : pack.scenarios) {
      tone::ScenarioResult row = tone::evaluate_scenario(scenario, pack.schema_version);
      if (pack.schema_version >= 3) {
        const std::size_t idx = report.scenarios.size();
        row.lineage_hex = io::build_lineage_hex(scenario, timelines[idx]);
      }
      row.digest_hex = io::build_scenario_digest(row, pack.schema_version);
      report.scenarios.push_back(row);
      report.summary.band_result_count += row.bands.size();
      report.summary.total_frame_count += row.frame_count;
      report.summary.total_dropped_frames += row.dropped_frame_count;
      report.summary.total_rejected_frames += row.rejected_frame_count;
    }
    report.summary.digest_hex = io::build_summary_digest(report);

    io::write_report(out_path, report);

    if (checkpoint_path != nullptr) {
      const std::filesystem::path ckpt_file(checkpoint_path);
      if (ckpt_file.has_parent_path()) {
        std::filesystem::create_directories(ckpt_file.parent_path());
      }
      tone::CheckpointState checkpoint;
      checkpoint.schema_version = 3;
      checkpoint.pack_fingerprint = io::build_pack_fingerprint(pack, timelines);
      for (const auto& row : report.scenarios) {
        checkpoint.completed.push_back({row.id, row.digest_hex});
      }
      io::write_checkpoint(checkpoint_path, checkpoint);
    }
  } catch (const std::exception& ex) {
    std::cerr << "error: " << ex.what() << '\n';
    return 1;
  }
  return 0;
}
