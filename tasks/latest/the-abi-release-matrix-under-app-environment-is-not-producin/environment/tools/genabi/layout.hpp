#ifndef GENABI_LAYOUT_HPP
#define GENABI_LAYOUT_HPP

#include "common.hpp"

// Assigns byte offsets, record size, and alignment to the ordered slots.
void compute_layout(LaneModel &model);

#endif
