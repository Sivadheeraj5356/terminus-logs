#include "n4.hpp"

#include <map>

std::vector<GroupX> h62_span(const std::vector<ScoreX>& a, const std::vector<NodeX>& b) {
    (void)b;
    std::map<std::string, GroupX> grouped;
    std::map<std::string, int> sums;
    for (const ScoreX& score : a) {
        std::string key = score.pid + "\n" + score.raw_pkg;
        GroupX& group = grouped[key];
        group.pid = score.pid;
        group.canon_pkg = score.raw_pkg;
        group.comp = score.comp;
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
        group.mean_margin_milli = group.variant_count == 0 ? 0 : (sums[entry.first] * 1000) / group.variant_count;
        out.push_back(group);
    }
    return out;
}
