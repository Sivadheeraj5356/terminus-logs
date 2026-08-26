#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <vector>

namespace tone {

struct BandSpec {
  std::string name;
  double low_hz{};
  double high_hz{};
  double weight{1.0};
};

struct BandResult {
  std::string name;
  double low_hz{};
  double high_hz{};
  double weight{1.0};
  std::size_t bin_count{};
  int peak_bin{-1};
  double peak_hz{};
  double energy{};
};

struct SampleOp {
  std::size_t index{};
  std::optional<double> value;
};

struct SampleRevision {
  std::string revision_id;
  std::vector<SampleOp> ops;
};

struct CalibrationOp {
  std::size_t start{};
  std::size_t end{};
  double gain{1.0};
  double offset{};
};

struct CalibrationRevision {
  std::string revision_id;
  std::vector<CalibrationOp> ops;
};

struct ScenarioSpec {
  std::string id;
  double sample_rate_hz{};
  std::size_t frame_len{};
  std::size_t hop_len{};
  std::string detrend;
  std::string gap_policy;
  double min_frame_quality{1.0};
  std::size_t timeline_len{};
  std::vector<BandSpec> bands;
  std::vector<std::optional<double>> samples;
  std::vector<SampleRevision> sample_revisions;
  std::vector<CalibrationRevision> calibration_revisions;
};

struct ScenarioResult {
  std::string id;
  std::size_t sample_count{};
  std::size_t valid_sample_count{};
  std::size_t frame_len{};
  std::size_t hop_len{};
  std::size_t frame_count{};
  std::size_t dropped_frame_count{};
  std::size_t rejected_frame_count{};
  double window_energy{};
  std::string lineage_hex;
  std::vector<BandResult> bands;
  std::string digest_hex;
};

struct SummaryResult {
  std::size_t scenario_count{};
  std::size_t band_result_count{};
  std::size_t total_frame_count{};
  std::size_t total_dropped_frames{};
  std::size_t total_rejected_frames{};
  std::string digest_hex;
};

struct PackSpec {
  int schema_version{};
  std::vector<ScenarioSpec> scenarios;
};

struct Report {
  int schema_version{};
  std::vector<ScenarioResult> scenarios;
  SummaryResult summary;
};

struct CheckpointEntry {
  std::string id;
  std::string digest_hex;
};

struct CheckpointState {
  int schema_version{};
  std::string pack_fingerprint;
  std::vector<CheckpointEntry> completed;
};

}  // namespace tone
