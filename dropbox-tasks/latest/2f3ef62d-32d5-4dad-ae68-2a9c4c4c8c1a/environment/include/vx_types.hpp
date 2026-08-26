#pragma once

#include <cstdint>
#include <string>
#include <vector>

struct Row {
    std::string lane_id;
    int loc_rc = 0;
    int img_rc = 0;
    int bind_rc = 0;
    int lag_code = 0;
    std::string facet_hex;
};

struct Summary {
    int rows_total = 0;
    std::string sync_label;
    int span_band = 0;
    std::string matrix_digest;
    uint64_t pack_epoch = 0;
    uint64_t settle_epoch = 0;
    std::string chain_bind;
};

struct LanePressure {
    std::string lane_id;
    uint32_t pending_arp_pressure = 0;
    std::string membership_digest;
};

struct RuntimeState {
    uint64_t epoch = 0;
    std::vector<LanePressure> lanes;
};

enum class Profile { Prep, Seal };

std::string md5_hex16(const std::string& input);
