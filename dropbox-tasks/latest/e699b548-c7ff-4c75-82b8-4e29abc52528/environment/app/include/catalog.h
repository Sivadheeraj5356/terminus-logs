#pragma once
#include "types.h"
#include <string>
#include <vector>

struct CatalogParseResult {
    bool ok = false;
    std::string error;
    std::vector<Fragment> fragments;
};

CatalogParseResult parse_catalog_file(const std::string& path);
