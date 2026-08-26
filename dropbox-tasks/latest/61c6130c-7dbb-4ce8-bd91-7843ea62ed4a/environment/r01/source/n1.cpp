#include "n1.hpp"

#include <cctype>

std::vector<UnitX> q17_fold(const std::vector<UnitX>& a, const RuleX& b) {
    (void)b;
    std::vector<UnitX> out = a;
    for (UnitX& row : out) {
        row.take = row.split != "train";
        row.norm.clear();
        for (unsigned char ch : row.text) {
            row.norm.push_back(static_cast<char>(std::tolower(ch)));
        }
    }
    return out;
}
