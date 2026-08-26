#!/bin/bash
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
Path("/app/environment/r04/source/n4.cpp").write_text(r'''
#include "n4.hpp"

#include <algorithm>
#include <cmath>
#include <map>

std::vector<GroupX> h62_span(const std::vector<ScoreX>& a, const std::vector<NodeX>& b) {
    auto nd_for = [&](const std::string& raw_pkg) -> const NodeX* {
        for (const NodeX& nd : b) {
            if (std::find(nd.aliases.begin(), nd.aliases.end(), raw_pkg) != nd.aliases.end()) {
                return &nd;
            }
        }
        return nullptr;
    };

    std::map<std::string, GroupX> grouped;
    std::map<std::string, int> sums;
    for (const ScoreX& score : a) {
        const NodeX* nd = nd_for(score.raw_pkg);
        std::string canon = nd ? nd->canon_pkg : score.raw_pkg;
        std::string key = score.pid + "\n" + canon;
        GroupX& group = grouped[key];
        group.pid = score.pid;
        group.canon_pkg = canon;
        group.comp = nd ? nd->comp : score.comp;
        group.sig = nd ? nd->sig : "";
        group.variant_count += 1;
        group.langs.push_back(score.lang);
        group.cases.push_back(score.cid);
        if (score.label != "block") {
            group.deficit_count += 1;
        }
        sums[key] += score.margin;
    }
    std::vector<GroupX> out;
    for (auto& entry : grouped) {
        GroupX group = entry.second;
        std::sort(group.langs.begin(), group.langs.end());
        group.langs.erase(std::unique(group.langs.begin(), group.langs.end()), group.langs.end());
        std::sort(group.cases.begin(), group.cases.end());
        group.mean_margin_milli = group.variant_count == 0 ? 0 : static_cast<int>(std::llround((sums[entry.first] * 1000.0) / group.variant_count));
        out.push_back(group);
    }
    std::sort(out.begin(), out.end(), [](const GroupX& left, const GroupX& right) {
        if (left.pid != right.pid) {
            return left.pid < right.pid;
        }
        return left.canon_pkg < right.canon_pkg;
    });
    return out;
}
''')
PY
