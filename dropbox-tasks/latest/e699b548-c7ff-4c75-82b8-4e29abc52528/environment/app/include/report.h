#pragma once
#include "types.h"
#include <string>

std::string plan_to_json(const CompactionPlan& plan);
std::string validation_to_json(const ValidationResult& vr);
std::string repair_to_json(const RepairResult& rr);
