#include "io.hpp"

#include <cstdlib>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <vector>

std::string env_or_default(const char *name, const std::string &fallback) {
    const char *val = std::getenv(name);
    if (val == nullptr || std::string(val).empty()) {
        return fallback;
    }
    return std::string(val);
}

static std::string trim(const std::string &s) {
    size_t start = s.find_first_not_of(" \t\r\n");
    if (start == std::string::npos) {
        return "";
    }
    size_t end = s.find_last_not_of(" \t\r\n");
    return s.substr(start, end - start + 1);
}

PositionFile read_position_file(const std::string &path) {
    std::ifstream in(path);
    if (!in) {
        throw std::runtime_error("cannot open position file: " + path);
    }
    std::string line;
    std::vector<std::string> lines;
    while (std::getline(in, line)) {
        std::string t = trim(line);
        if (!t.empty()) {
            lines.push_back(t);
        }
    }
    if (lines.size() < 2) {
        throw std::runtime_error("position file missing fen or depth line");
    }
    PositionFile pf;
    pf.fen = lines[0];
    pf.depth = std::stoi(lines[1]);
    return pf;
}

void write_output_json(const std::string &path, long long perft_nodes) {
    size_t slash = path.find_last_of('/');
    if (slash != std::string::npos) {
        std::string dir = path.substr(0, slash);
        std::string cmd = "mkdir -p \"" + dir + "\"";
        std::system(cmd.c_str());
    }
    std::ofstream out(path);
    if (!out) {
        throw std::runtime_error("cannot open output file for writing: " + path);
    }
    out << "{\"perft_nodes\": " << perft_nodes << "}\n";
}
