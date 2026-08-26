#pragma once
#include "types.h"
#include <cstdint>
#include <string>

uint64_t fnv1a64(const std::string& text);
std::string fingerprint_hex(const std::string& text);
std::string plan_signature(const CompactionPlan& plan);
