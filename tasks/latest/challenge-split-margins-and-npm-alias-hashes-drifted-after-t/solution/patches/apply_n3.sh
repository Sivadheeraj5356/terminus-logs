#!/bin/bash
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
Path("/app/environment/r03/source/n3.cpp").write_text(r'''
#include "n3.hpp"

#include <algorithm>
#include <map>

std::vector<NodeX> r08_flux(const GraphX& a, const std::vector<ItemX>& b) {
    std::map<std::string, NodeX> grouped;
    for (const ItemX& item : b) {
        NodeX& nd = grouped[item.canon_pkg];
        nd.canon_pkg = item.canon_pkg;
        nd.comp = item.comp;
        auto found = a.sig.find(item.canon_pkg);
        nd.sig = found == a.sig.end() ? "" : found->second;
        nd.aliases.push_back(item.raw_pkg);
    }
    std::vector<NodeX> out;
    for (auto& entry : grouped) {
        NodeX nd = entry.second;
        std::sort(nd.aliases.begin(), nd.aliases.end());
        nd.aliases.erase(std::unique(nd.aliases.begin(), nd.aliases.end()), nd.aliases.end());
        out.push_back(nd);
    }
    std::sort(out.begin(), out.end(), [](const NodeX& left, const NodeX& right) {
        return left.canon_pkg < right.canon_pkg;
    });
    return out;
}
''')
PY
