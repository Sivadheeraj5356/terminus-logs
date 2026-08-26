#pragma once
#include "types.h"
#include <string>

bool write_staging_snapshot(const std::string& path, const StagingSnapshot& snap, std::string& err);
bool read_staging_snapshot(const std::string& path, StagingSnapshot& out, std::string& err);
std::string catalog_digest_hex(const std::vector<Fragment>& fragments);
bool staging_snapshot_matches_catalog(const StagingSnapshot& snap, const std::vector<Fragment>& fragments);
void note_repair_snapshot_reset(const std::vector<Fragment>& fragments);
bool repair_snapshot_reset_pending(const std::vector<Fragment>& fragments);
