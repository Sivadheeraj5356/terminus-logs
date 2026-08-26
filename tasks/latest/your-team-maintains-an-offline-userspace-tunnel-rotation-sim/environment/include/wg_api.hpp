#pragma once

#include "wg_replay.hpp"
#include "wg_types.hpp"

#include <string>
#include <utility>
#include <vector>

std::string file_digest16(const std::string& path);
PermTbl load_perm_tbl(const std::string& path);
OvTbl load_ov_tbl(const std::string& path);
std::string flow_digest_rows(const std::vector<PeerRow>& rows);
std::pair<std::vector<PeerRow>, std::vector<PhaseTrace>> run_pipeline(PipelineInput& input);
std::pair<uint8_t, std::string> fn_bind(const RowTbl& rows, const std::vector<uint8_t>& witness_bytes,
                                        const std::string& peer_id);
std::string refresh_witness(const std::string& witness, const std::string& peer_id, const std::string& facet);
int capture_mux_snapshot(MuxSnapshot& snap, int variant_seed, uint32_t route_mark);
