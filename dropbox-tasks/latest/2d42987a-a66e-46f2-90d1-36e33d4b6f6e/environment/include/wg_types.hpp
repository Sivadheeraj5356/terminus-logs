#pragma once

#include <cstdint>
#include <map>
#include <string>
#include <tuple>
#include <vector>

enum class Profile { Stage, Apply };

using PermTbl = std::map<int32_t, std::map<std::string, double>>;
using OvTbl = std::map<uint32_t, std::string>;
using RowTbl = std::map<std::string, std::tuple<uint8_t, uint8_t, uint8_t, uint8_t, int32_t, std::string>>;

struct PeerRow {
    std::string peer_id;
    uint8_t mux_rc;
    uint8_t mark_rc;
    uint8_t ov_rc;
    uint8_t seal_rc;
    int32_t shift_code;
    std::string bind_hex;
};

struct PhaseTrace {
    std::string phase;
    std::string detail;
};

struct PipelineInput {
    Profile profile;
    bool hook_replay = false;
    const PermTbl* perm_tbl;
    const OvTbl* ov_tbl;
    std::string witness_text;
    const std::vector<std::string>* peer_ids;
    int32_t variant_seed;
};

std::string wg_md5_hex16(const std::string& input);
