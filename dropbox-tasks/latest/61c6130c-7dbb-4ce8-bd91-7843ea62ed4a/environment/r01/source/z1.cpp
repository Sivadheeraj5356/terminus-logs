#include "x.hpp"

#include <fstream>
#include <regex>
#include <stdexcept>
#include <string>

std::string z1_pick(const std::string& line, const std::string& key) {
    std::regex re("\"" + key + "\"\\s*:\\s*\"([^\"]*)\"");
    std::smatch match;
    if (!std::regex_search(line, match, re)) {
        return "";
    }
    return match[1].str();
}

void z1_take(const std::string& path, std::vector<UnitX>& out) {
    std::ifstream in(path);
    if (!in) {
        throw std::runtime_error("cannot open " + path);
    }
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) {
            continue;
        }
        UnitX row;
        row.cid = z1_pick(line, "case_id");
        row.pid = z1_pick(line, "prompt_id");
        row.split = z1_pick(line, "split");
        row.lang = z1_pick(line, "lang");
        row.text = z1_pick(line, "text");
        row.comp = z1_pick(line, "component");
        row.raw_pkg = z1_pick(line, "package");
        row.norm = row.text;
        out.push_back(row);
    }
}

std::vector<UnitX> z1_pull(const std::string& root) {
    std::vector<UnitX> rows;
    z1_take(root + "/inputs/i1.jsonl", rows);
    z1_take(root + "/inputs/i2.jsonl", rows);
    return rows;
}
