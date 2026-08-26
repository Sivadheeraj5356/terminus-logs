#pragma once
#include "types.h"
#include <cstdint>
#include <map>
#include <vector>

uint32_t chain_span_total(
    const std::vector<uint16_t>& order,
    const std::vector<int>& overlaps,
    const std::map<uint16_t, Fragment>& by_id);
