#include "tableau.hpp"

#include <cstdlib>
#include <fstream>
#include <sstream>
#include <vector>

namespace {

std::vector<double> parse_values(const std::string &rest) {
    std::vector<double> out;
    std::istringstream iss(rest);
    std::string tok;
    while (iss >> tok) {
        out.push_back(std::strtod(tok.c_str(), nullptr));
    }
    return out;
}

}  // namespace

bool load_tableau(const std::string &path, Tableau &out, std::string &err) {
    std::ifstream in(path);
    if (!in) {
        err = "cannot open stage weight table: " + path;
        return false;
    }
    for (int i = 0; i < 6; ++i) {
        out.node[i] = 0.0;
        out.upper[i] = 0.0;
        out.lower[i] = 0.0;
        for (int j = 0; j < 6; ++j) out.a[i][j] = 0.0;
    }

    bool seen_node = false, seen_upper = false, seen_lower = false;
    int seen_stages = 0;
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) continue;
        std::istringstream iss(line);
        std::string key;
        iss >> key;
        std::string rest;
        std::getline(iss, rest);
        std::vector<double> vals = parse_values(rest);

        if (key == "node") {
            if (vals.size() != 6) { err = "node row must carry six entries"; return false; }
            for (int i = 0; i < 6; ++i) out.node[i] = vals[i];
            seen_node = true;
        } else if (key == "upper") {
            if (vals.size() != 6) { err = "upper row must carry six entries"; return false; }
            for (int i = 0; i < 6; ++i) out.upper[i] = vals[i];
            seen_upper = true;
        } else if (key == "lower") {
            if (vals.size() != 6) { err = "lower row must carry six entries"; return false; }
            for (int i = 0; i < 6; ++i) out.lower[i] = vals[i];
            seen_lower = true;
        } else if (key.rfind("stage", 0) == 0) {
            int idx = std::atoi(key.substr(5).c_str()) - 1;
            if (idx < 1 || idx > 5) { err = "stage row index out of range: " + key; return false; }
            if ((int)vals.size() != idx) { err = "stage row width does not match its index: " + key; return false; }
            for (int j = 0; j < idx; ++j) out.a[idx][j] = vals[j];
            seen_stages += 1;
        }
    }
    if (!seen_node || !seen_upper || !seen_lower || seen_stages != 5) {
        err = "stage weight table is incomplete";
        return false;
    }
    return true;
}
