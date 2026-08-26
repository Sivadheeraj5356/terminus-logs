#pragma once
#include "types.h"
#include <cstdint>
#include <optional>
#include <vector>

struct EdgeChoice {
    uint16_t from = 0;
    uint16_t to = 0;
    int overlap = 0;
};

std::optional<EdgeChoice> select_outgoing_edge(uint16_t from_id, const std::vector<Fragment>& frags, const Policy& policy);
std::optional<uint16_t> resolve_open_fragment(const std::vector<Fragment>& fragments, const Policy& policy);
std::vector<EdgeChoice> trace_edge_path(const std::vector<Fragment>& fragments, const Policy& policy);
