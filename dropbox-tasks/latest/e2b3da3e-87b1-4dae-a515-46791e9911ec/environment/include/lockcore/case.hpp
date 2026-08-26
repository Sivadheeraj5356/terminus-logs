#pragma once

#include "lockcore/types.hpp"

#include <string>

namespace lockcore {

class Topology;

void validate_case_spec(const CaseSpec& spec);

// Computes the 64-character lowercase hex case digest from the canonical
// case JSON, a zero byte separator, and the canonical normalized topology
// JSON. Forcing bytes are intentionally excluded.
std::string compute_case_digest_hex(const CaseSpec& spec, const Topology& topology);

}  // namespace lockcore
