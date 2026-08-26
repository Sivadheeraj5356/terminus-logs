#include "io/pack_io.hpp"

#include "metrics/reconstruct.hpp"
#include "metrics/types.hpp"
#include "util/digest.hpp"

#include <cctype>
#include <fstream>
#include <iomanip>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace io {
namespace {

std::string trim(const std::string& s) {
  std::size_t start = 0;
  while (start < s.size() && std::isspace(static_cast<unsigned char>(s[start]))) {
    ++start;
  }
  std::size_t end = s.size();
  while (end > start && std::isspace(static_cast<unsigned char>(s[end - 1]))) {
    --end;
  }
  return s.substr(start, end - start);
}

std::string read_file(const char* path) {
  std::ifstream in(path);
  if (!in) {
    throw std::runtime_error(std::string("cannot open pack: ") + path);
  }
  std::ostringstream oss;
  oss << in.rdbuf();
  return oss.str();
}

double parse_number(const std::string& text, const std::string& key) {
  const std::string needle = '"' + key + '"';
  const std::size_t pos = text.find(needle);
  if (pos == std::string::npos) {
    throw std::runtime_error("missing key: " + key);
  }
  const std::size_t colon = text.find(':', pos);
  const std::size_t end = text.find_first_of(",}\n", colon);
  return std::stod(trim(text.substr(colon + 1, end - colon - 1)));
}

int parse_int(const std::string& text, const std::string& key) {
  return static_cast<int>(parse_number(text, key));
}

bool has_key(const std::string& text, const std::string& key) {
  return text.find('"' + key + '"') != std::string::npos;
}

std::string parse_string(const std::string& text, const std::string& key) {
  const std::string needle = '"' + key + '"';
  const std::size_t pos = text.find(needle);
  if (pos == std::string::npos) {
    throw std::runtime_error("missing key: " + key);
  }
  const std::size_t q1 = text.find('"', pos + needle.size());
  const std::size_t q2 = text.find('"', q1 + 1);
  return text.substr(q1 + 1, q2 - q1 - 1);
}

std::optional<double> parse_optional_number_token(const std::string& token) {
  const std::string t = trim(token);
  if (t == "null") {
    return std::nullopt;
  }
  return std::stod(t);
}

std::vector<std::optional<double>> parse_samples(const std::string& block) {
  std::vector<std::optional<double>> out;
  const std::string key = "\"samples\"";
  const std::size_t pos = block.find(key);
  if (pos == std::string::npos) {
    return out;
  }
  const std::size_t lb = block.find('[', pos);
  const std::size_t rb = block.find(']', lb);
  if (lb == std::string::npos || rb == std::string::npos) {
    return out;
  }
  std::string inner = block.substr(lb + 1, rb - lb - 1);
  std::stringstream ss(inner);
  std::string token;
  while (std::getline(ss, token, ',')) {
    token = trim(token);
    if (token.empty()) {
      continue;
    }
    out.push_back(parse_optional_number_token(token));
  }
  return out;
}

std::vector<std::string> extract_objects(const std::string& text, const std::string& array_key) {
  std::vector<std::string> out;
  const std::string key = '"' + array_key + '"';
  const std::size_t pos = text.find(key);
  if (pos == std::string::npos) {
    return out;
  }
  std::size_t i = text.find('[', pos);
  if (i == std::string::npos) {
    return out;
  }
  int depth = 0;
  std::size_t start = std::string::npos;
  for (; i < text.size(); ++i) {
    if (text[i] == '{') {
      if (depth == 0) {
        start = i;
      }
      ++depth;
    } else if (text[i] == '}') {
      --depth;
      if (depth == 0 && start != std::string::npos) {
        out.push_back(text.substr(start, i - start + 1));
        start = std::string::npos;
      }
    } else if (text[i] == ']' && depth == 0) {
      break;
    }
  }
  return out;
}

std::vector<tone::BandSpec> parse_bands(const std::string& block, int schema_version) {
  std::vector<tone::BandSpec> out;
  for (const std::string& band_block : extract_objects(block, "bands")) {
    tone::BandSpec band;
    band.name = parse_string(band_block, "name");
    band.low_hz = parse_number(band_block, "low_hz");
    band.high_hz = parse_number(band_block, "high_hz");
    if (schema_version >= 3) {
      band.weight = parse_number(band_block, "weight");
    }
    out.push_back(band);
  }
  return out;
}

std::vector<tone::SampleOp> parse_sample_ops(const std::string& revision_block) {
  std::vector<tone::SampleOp> out;
  for (const std::string& op_block : extract_objects(revision_block, "ops")) {
    tone::SampleOp op;
    op.index = static_cast<std::size_t>(parse_int(op_block, "index"));
    const std::string key = "\"value\"";
    const std::size_t pos = op_block.find(key);
    if (pos == std::string::npos) {
      throw std::runtime_error("missing sample op value");
    }
    const std::size_t colon = op_block.find(':', pos);
    const std::size_t end = op_block.find_first_of(",}", colon);
    op.value = parse_optional_number_token(op_block.substr(colon + 1, end - colon - 1));
    out.push_back(op);
  }
  return out;
}

std::vector<tone::SampleRevision> parse_sample_revisions(const std::string& block) {
  std::vector<tone::SampleRevision> out;
  for (const std::string& rev_block : extract_objects(block, "sample_revisions")) {
    tone::SampleRevision revision;
    revision.revision_id = parse_string(rev_block, "revision_id");
    revision.ops = parse_sample_ops(rev_block);
    out.push_back(revision);
  }
  return out;
}

std::vector<tone::CalibrationOp> parse_calibration_ops(const std::string& revision_block) {
  std::vector<tone::CalibrationOp> out;
  for (const std::string& op_block : extract_objects(revision_block, "ops")) {
    tone::CalibrationOp op;
    op.start = static_cast<std::size_t>(parse_int(op_block, "start"));
    op.end = static_cast<std::size_t>(parse_int(op_block, "end"));
    op.gain = parse_number(op_block, "gain");
    op.offset = parse_number(op_block, "offset");
    out.push_back(op);
  }
  return out;
}

std::vector<tone::CalibrationRevision> parse_calibration_revisions(const std::string& block) {
  std::vector<tone::CalibrationRevision> out;
  for (const std::string& rev_block : extract_objects(block, "calibration_revisions")) {
    tone::CalibrationRevision revision;
    revision.revision_id = parse_string(rev_block, "revision_id");
    revision.ops = parse_calibration_ops(rev_block);
    out.push_back(revision);
  }
  return out;
}

tone::ScenarioSpec parse_scenario_block(const std::string& block, int schema_version) {
  tone::ScenarioSpec spec;
  spec.id = parse_string(block, "id");
  spec.sample_rate_hz = parse_number(block, "sample_rate_hz");
  spec.frame_len = static_cast<std::size_t>(parse_int(block, "frame_len"));
  spec.hop_len = static_cast<std::size_t>(parse_int(block, "hop_len"));
  spec.detrend = parse_string(block, "detrend");
  spec.gap_policy = parse_string(block, "gap_policy");
  spec.bands = parse_bands(block, schema_version);
  if (schema_version >= 3) {
    spec.min_frame_quality = parse_number(block, "min_frame_quality");
    spec.timeline_len = static_cast<std::size_t>(parse_int(block, "timeline_len"));
    spec.sample_revisions = parse_sample_revisions(block);
    spec.calibration_revisions = parse_calibration_revisions(block);
  } else {
    spec.samples = parse_samples(block);
  }
  return spec;
}

std::vector<tone::ScenarioSpec> parse_scenarios(const std::string& text, int schema_version) {
  std::vector<tone::ScenarioSpec> out;
  for (const std::string& block : extract_objects(text, "scenarios")) {
    out.push_back(parse_scenario_block(block, schema_version));
  }
  return out;
}

std::string format_fixed12(double value) {
  std::ostringstream oss;
  oss << std::fixed << std::setprecision(12) << value;
  return oss.str();
}

std::string timeline_csv(const std::vector<std::optional<double>>& timeline) {
  std::ostringstream oss;
  for (std::size_t i = 0; i < timeline.size(); ++i) {
    if (i > 0) {
      oss << ',';
    }
    if (!timeline[i].has_value()) {
      oss << "null";
    } else {
      oss << format_fixed12(*timeline[i]);
    }
  }
  return oss.str();
}

std::string revision_ids_csv(const std::vector<std::string>& ids) {
  std::ostringstream oss;
  for (std::size_t i = 0; i < ids.size(); ++i) {
    if (i > 0) {
      oss << ',';
    }
    oss << ids[i];
  }
  return oss.str();
}

std::string scenario_seal_v2(const tone::ScenarioResult& row) {
  std::ostringstream oss;
  oss << row.id << '|' << row.sample_count << '|' << row.valid_sample_count << '|'
      << row.frame_len << '|' << row.hop_len << '|' << row.frame_count << '|'
      << row.dropped_frame_count << '|' << format_fixed12(row.window_energy);
  for (const auto& band : row.bands) {
    oss << '|' << band.name << ':' << format_fixed12(band.low_hz) << ':'
        << format_fixed12(band.high_hz) << ':' << band.bin_count << ':' << band.peak_bin
        << ':' << format_fixed12(band.peak_hz) << ':' << format_fixed12(band.energy);
  }
  return oss.str();
}

std::string scenario_seal_v3(const tone::ScenarioResult& row) {
  std::ostringstream oss;
  oss << row.id << '|' << row.sample_count << '|' << row.valid_sample_count << '|'
      << row.frame_len << '|' << row.hop_len << '|' << row.frame_count << '|'
      << row.dropped_frame_count << '|' << format_fixed12(row.window_energy);
  for (const auto& band : row.bands) {
    oss << '|' << band.name << ':' << format_fixed12(band.low_hz) << ':'
        << format_fixed12(band.high_hz) << ':' << band.bin_count << ':' << band.peak_bin
        << ':' << format_fixed12(band.peak_hz) << ':' << format_fixed12(band.energy);
  }
  return oss.str();
}

std::string summary_seal(const tone::Report& report) {
  std::ostringstream oss;
  oss << report.schema_version << '|' << report.summary.scenario_count << '|'
      << report.summary.band_result_count << '|' << report.summary.total_frame_count << '|'
      << report.summary.total_dropped_frames;
  if (report.schema_version >= 3) {
    oss << '|' << report.summary.total_rejected_frames;
  }
  for (const auto& row : report.scenarios) {
    oss << '|' << row.digest_hex;
  }
  return oss.str();
}

std::string report_json(const tone::Report& report) {
  std::ostringstream out;
  out << std::fixed << std::setprecision(12);
  out << "{\n";
  out << "  \"schema_version\": " << report.schema_version << ",\n";
  out << "  \"scenarios\": [\n";
  for (std::size_t i = 0; i < report.scenarios.size(); ++i) {
    const auto& row = report.scenarios[i];
    out << "    {\n";
    out << "      \"id\": \"" << row.id << "\",\n";
    out << "      \"sample_count\": " << row.sample_count << ",\n";
    out << "      \"valid_sample_count\": " << row.valid_sample_count << ",\n";
    out << "      \"frame_len\": " << row.frame_len << ",\n";
    out << "      \"hop_len\": " << row.hop_len << ",\n";
    out << "      \"frame_count\": " << row.frame_count << ",\n";
    out << "      \"dropped_frame_count\": " << row.dropped_frame_count << ",\n";
    if (report.schema_version >= 3) {
      out << "      \"rejected_frame_count\": " << row.rejected_frame_count << ",\n";
    }
    out << "      \"window_energy\": " << row.window_energy << ",\n";
    if (report.schema_version >= 3) {
      out << "      \"lineage_hex\": \"" << row.lineage_hex << "\",\n";
    }
    out << "      \"bands\": [\n";
    for (std::size_t j = 0; j < row.bands.size(); ++j) {
      const auto& band = row.bands[j];
      out << "        {\n";
      out << "          \"name\": \"" << band.name << "\",\n";
      out << "          \"low_hz\": " << band.low_hz << ",\n";
      out << "          \"high_hz\": " << band.high_hz << ",\n";
      if (report.schema_version >= 3) {
        out << "          \"weight\": " << band.weight << ",\n";
      }
      out << "          \"bin_count\": " << band.bin_count << ",\n";
      out << "          \"peak_bin\": " << band.peak_bin << ",\n";
      out << "          \"peak_hz\": " << band.peak_hz << ",\n";
      out << "          \"energy\": " << band.energy << "\n";
      out << "        }";
      if (j + 1 < row.bands.size()) {
        out << ',';
      }
      out << '\n';
    }
    out << "      ],\n";
    out << "      \"digest_hex\": \"" << row.digest_hex << "\"\n";
    out << "    }";
    if (i + 1 < report.scenarios.size()) {
      out << ',';
    }
    out << '\n';
  }
  out << "  ],\n";
  out << "  \"summary\": {\n";
  out << "    \"scenario_count\": " << report.summary.scenario_count << ",\n";
  out << "    \"band_result_count\": " << report.summary.band_result_count << ",\n";
  out << "    \"total_frame_count\": " << report.summary.total_frame_count << ",\n";
  out << "    \"total_dropped_frames\": " << report.summary.total_dropped_frames << ",\n";
  if (report.schema_version >= 3) {
    out << "    \"total_rejected_frames\": " << report.summary.total_rejected_frames << ",\n";
  }
  out << "    \"digest_hex\": \"" << report.summary.digest_hex << "\"\n";
  out << "  }\n";
  out << "}\n";
  return out.str();
}

}  // namespace

tone::PackSpec load_pack(const char* path) {
  const std::string text = read_file(path);
  tone::PackSpec pack;
  pack.schema_version = parse_int(text, "schema_version");
  if (pack.schema_version != 2 && pack.schema_version != 3) {
    throw std::runtime_error("unsupported schema_version");
  }
  pack.scenarios = parse_scenarios(text, pack.schema_version);
  return pack;
}

void write_report(const char* path, const tone::Report& report) {
  std::ofstream out(path, std::ios::trunc);
  if (!out) {
    throw std::runtime_error(std::string("cannot write report: ") + path);
  }
  out << report_json(report);
}

void write_checkpoint(const char* path, const tone::CheckpointState& checkpoint) {
  std::ofstream out(path, std::ios::trunc);
  if (!out) {
    throw std::runtime_error(std::string("cannot write checkpoint: ") + path);
  }
  out << std::fixed << std::setprecision(12);
  out << "{\n";
  out << "  \"schema_version\": " << checkpoint.schema_version << ",\n";
  out << "  \"pack_fingerprint\": \"" << checkpoint.pack_fingerprint << "\",\n";
  out << "  \"completed\": [\n";
  for (std::size_t i = 0; i < checkpoint.completed.size(); ++i) {
    const auto& entry = checkpoint.completed[i];
    out << "    {\"id\": \"" << entry.id << "\", \"digest_hex\": \"" << entry.digest_hex << "\"}";
    if (i + 1 < checkpoint.completed.size()) {
      out << ',';
    }
    out << '\n';
  }
  out << "  ]\n";
  out << "}\n";
}

tone::CheckpointState load_checkpoint(const char* path) {
  const std::string text = read_file(path);
  tone::CheckpointState state;
  state.schema_version = parse_int(text, "schema_version");
  state.pack_fingerprint = parse_string(text, "pack_fingerprint");
  for (const std::string& block : extract_objects(text, "completed")) {
    tone::CheckpointEntry entry;
    entry.id = parse_string(block, "id");
    entry.digest_hex = parse_string(block, "digest_hex");
    state.completed.push_back(entry);
  }
  return state;
}

std::string build_scenario_digest(const tone::ScenarioResult& row, int schema_version) {
  if (schema_version >= 3) {
    return util::sha256_hex_lower(scenario_seal_v3(row));
  }
  return util::sha256_hex_lower(scenario_seal_v2(row));
}

std::string build_summary_digest(const tone::Report& report) {
  return util::sha256_hex_lower(summary_seal(report));
}

std::string build_lineage_hex(const tone::ScenarioSpec& spec,
                              const std::vector<std::optional<double>>& timeline) {
  std::vector<std::string> sample_ids;
  for (const auto& revision : spec.sample_revisions) {
    sample_ids.push_back(revision.revision_id);
  }
  const std::string seal = revision_ids_csv(sample_ids) + '|' + timeline_csv(timeline);
  return util::sha256_hex_lower(seal);
}

std::string build_pack_fingerprint(const tone::PackSpec& pack,
                                   const std::vector<std::vector<std::optional<double>>>& timelines) {
  std::ostringstream oss;
  oss << pack.schema_version;
  for (std::size_t si = 0; si < pack.scenarios.size(); ++si) {
    const auto& spec = pack.scenarios[si];
    const auto& timeline = timelines[si];
    oss << '|' << spec.id << '|' << spec.timeline_len;
    std::vector<std::string> sample_ids;
    for (const auto& revision : spec.sample_revisions) {
      sample_ids.push_back(revision.revision_id);
    }
    oss << '|' << revision_ids_csv(sample_ids);
    oss << '|' << timeline_csv(timeline);
  }
  return util::sha256_hex_lower(oss.str());
}

}  // namespace io
