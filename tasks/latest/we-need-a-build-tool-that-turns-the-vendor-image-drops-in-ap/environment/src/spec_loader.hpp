#pragma once
#include <string>
#include <vector>

struct AssetClassRule {
    std::string name;
    std::string mode;     // "cover" or "fit"
    int width;
    int height;
    bool shrink_only;
};

std::vector<AssetClassRule> load_spec(const std::string& spec_path);
