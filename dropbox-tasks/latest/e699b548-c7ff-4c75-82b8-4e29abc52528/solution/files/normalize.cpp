#include "normalize.h"
#include <cctype>

static bool is_ws(unsigned char c) {
    return c == ' ' || c == '\t' || c == '\n' || c == '\r';
}

std::string normalize_column_name(const std::string& raw, bool case_fold_ascii) {
    std::string s;
    s.reserve(raw.size());
    for (unsigned char c : raw) {
        if (c != 0) s.push_back(static_cast<char>(c));
    }
    if (s.size() >= 3 &&
        static_cast<unsigned char>(s[0]) == 0xEF &&
        static_cast<unsigned char>(s[1]) == 0xBB &&
        static_cast<unsigned char>(s[2]) == 0xBF) {
        s.erase(0, 3);
    }
    size_t start = 0;
    while (start < s.size() && is_ws(static_cast<unsigned char>(s[start]))) ++start;
    size_t end = s.size();
    while (end > start && is_ws(static_cast<unsigned char>(s[end - 1]))) --end;
    std::string out;
    out.reserve(end - start);
    bool in_ws = false;
    for (size_t i = start; i < end; ++i) {
        unsigned char c = static_cast<unsigned char>(s[i]);
        if (is_ws(c)) {
            if (!in_ws) { out.push_back(' '); in_ws = true; }
        } else {
            if (case_fold_ascii && c < 128) {
                out.push_back(static_cast<char>(std::tolower(c)));
            } else {
                out.push_back(static_cast<char>(c));
            }
            in_ws = false;
        }
    }
    return out;
}
