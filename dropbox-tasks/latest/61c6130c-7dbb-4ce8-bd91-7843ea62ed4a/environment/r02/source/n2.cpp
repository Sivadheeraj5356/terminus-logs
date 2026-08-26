#include "n2.hpp"

#include <algorithm>
#include <sstream>
#include <string>

std::vector<ScoreX> m34_bridge(const std::vector<UnitX>& a, const TableX& b) {
    (void)b;
    std::vector<std::string> bad = {"toxic", "basura", "insult", "ganda", "dhamki", "threat", "samm"};
    std::vector<std::string> good = {"kind", "calm", "neutral", "support", "please", "stay", "review", "training"};
    std::vector<ScoreX> out;
    for (const UnitX& row : a) {
        if (!row.take) {
            continue;
        }
        int hot = 0;
        int cool = 0;
        std::istringstream ws(row.norm);
        std::string w;
        while (ws >> w) {
            if (std::find(bad.begin(), bad.end(), w) != bad.end()) {
                ++hot;
            }
            if (std::find(good.begin(), good.end(), w) != good.end()) {
                ++cool;
            }
        }
        ScoreX score;
        score.cid = row.cid;
        score.pid = row.pid;
        score.split = row.split;
        score.lang = row.lang;
        score.comp = row.comp;
        score.raw_pkg = row.raw_pkg;
        score.margin = 3 * hot - 2 * cool;
        score.label = score.margin >= 3 ? "block" : (score.margin > 0 ? "review" : "allow");
        out.push_back(score);
    }
    return out;
}
