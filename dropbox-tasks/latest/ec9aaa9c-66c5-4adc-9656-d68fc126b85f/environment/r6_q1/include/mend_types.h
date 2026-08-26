#pragma once

#include <string>

// Truncate incomplete trailing journal bytes and drop GEN-gap tails.
// Returns number of bytes removed across all journal files under stage_root.
int mend_r4(const std::string& stage_root);
