#pragma once
#include "types.h"
#include <string>

bool read_policy_file(const std::string& path, Policy& out, std::string& err);
bool read_plan_file(const std::string& path, CompactionPlan& out, std::string& err);
bool write_text_file(const std::string& path, const std::string& content, std::string& err);
