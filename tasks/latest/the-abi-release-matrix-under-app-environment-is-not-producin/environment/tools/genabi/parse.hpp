#ifndef GENABI_PARSE_HPP
#define GENABI_PARSE_HPP

#include <string>

#include "common.hpp"

// Reads the lane profile file plus the ordered IDL fragments it selects and
// fills the model's ordered slot list and feature flags. Offsets are left for
// the layout pass. Returns false and prints a diagnostic on malformed input.
bool build_model(const std::string &idl_dir, const std::string &lane_file,
                 const std::string &label, LaneModel &model);

#endif
