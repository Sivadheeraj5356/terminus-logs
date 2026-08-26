#pragma once
#include <string>
#include "spec_loader.hpp"

struct DerivativeResult {
    std::string source_file;
    std::string asset_class;
    std::string output_path;
    int width;
    int height;
    std::string icc_policy;      // "preserved" or "assumed_srgb"
    bool orientation_normalized;
    std::string sha256;
};

DerivativeResult produce_derivative(
    const std::string& source_path,
    const AssetClassRule& rule,
    const std::string& out_dir
);
