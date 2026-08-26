#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include <map>

struct run_row {
  std::string bundle;
  std::string profile;
  uint64_t gen;
  uint64_t synced_gen;
  int dual_valid;
  int dual_peak;
  std::string status;
  uint64_t composed;
  uint64_t abs_deadline;
  int occupancy;
  int limit;
  std::string digest_key;
  std::string digest_sha256;
  std::string journal_tag;
};

struct run_matrix {
  std::string matrix_name;
  std::vector<std::string> profiles;
  std::vector<run_row> rows;
  std::map<std::string, std::string> digests;
  int stage_field_count;
  int journal_field_count;
  std::string recovery_marker;
  std::string epoch_ok;
};

struct journal_blob {
  std::string json_body;
  int field_count;
};
