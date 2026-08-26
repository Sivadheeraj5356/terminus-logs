#pragma once
#include <string>
#include <vector>
#include "derive.hpp"

void write_manifest(
    const std::string& manifest_path,
    const std::vector<DerivativeResult>& derivatives
);
