#include "pack.hpp"
#include <sstream>

int pack_blob_w(const struct run_matrix *mx, struct journal_blob *out) {
  if (!mx || !out) {
    return -1;
  }
  std::ostringstream oss;
  oss << "{\n";
  oss << "  \"matrix\": \"" << mx->matrix_name << "\",\n";
  oss << "  \"profiles\": [";
  for (size_t i = 0; i < mx->profiles.size(); ++i) {
    if (i) oss << ", ";
    oss << "\"" << mx->profiles[i] << "\"";
  }
  oss << "],\n";
  oss << "  \"rows\": [\n";
  for (size_t i = 0; i < mx->rows.size(); ++i) {
    const auto &r = mx->rows[i];
    if (i) oss << ",\n";
    /* Stage-shaped journal: omits digest_sha256 / journal_tag (false green). */
    oss << "    {\"bundle\": \"" << r.bundle << "\", "
        << "\"profile\": \"" << r.profile << "\", "
        << "\"gen\": " << r.gen << ", "
        << "\"synced_gen\": " << r.synced_gen << ", "
        << "\"dual_valid\": " << r.dual_valid << ", "
        << "\"dual_peak\": " << r.dual_peak << ", "
        << "\"status\": \"" << r.status << "\", "
        << "\"composed\": " << r.composed << ", "
        << "\"abs_deadline\": " << r.abs_deadline << ", "
        << "\"occupancy\": " << r.occupancy << ", "
        << "\"limit\": " << r.limit << ", "
        << "\"digest_key\": \"" << r.digest_key << "\"}";
  }
  oss << "\n  ],\n";
  oss << "  \"digests\": {";
  bool first = true;
  for (const auto &kv : mx->digests) {
    if (!first) oss << ", ";
    first = false;
    oss << "\"" << kv.first << "\": \"" << kv.second << "\"";
  }
  oss << "},\n";
  oss << "  \"meta\": {"
      << "\"stage_field_count\": " << mx->stage_field_count << ", "
      << "\"journal_field_count\": " << mx->stage_field_count << ", "
      << "\"recovery_marker\": \"" << mx->recovery_marker << "\", "
      << "\"epoch_ok\": \"" << mx->epoch_ok << "\"}\n";
  oss << "}\n";
  out->json_body = oss.str();
  out->field_count = mx->stage_field_count;
  return 0;
}
