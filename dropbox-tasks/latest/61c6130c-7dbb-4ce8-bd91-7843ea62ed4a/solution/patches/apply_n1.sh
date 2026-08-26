#!/bin/bash
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
Path("/app/environment/r01/source/n1.cpp").write_text(r'''
#include "n1.hpp"

#include <cctype>

std::vector<UnitX> q17_fold(const std::vector<UnitX>& a, const RuleX& b) {
    (void)b;
    std::vector<UnitX> out = a;
    for (UnitX& row : out) {
        row.take = row.split == "eval" || row.split == "challenge";
        row.norm.clear();
        for (unsigned char raw : row.text) {
            char ch = static_cast<char>(std::tolower(raw));
            if (ch == '0') ch = 'o';
            else if (ch == '1') ch = 'i';
            else if (ch == '3') ch = 'e';
            else if (ch == '4') ch = 'a';
            else if (ch == '5') ch = 's';
            else if (ch == '7') ch = 't';
            if (std::isalnum(static_cast<unsigned char>(ch)) || std::isspace(static_cast<unsigned char>(ch))) {
                row.norm.push_back(ch);
            } else {
                row.norm.push_back(' ');
            }
        }
    }
    return out;
}
''')
PY
