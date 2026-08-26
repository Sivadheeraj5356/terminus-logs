#pragma once

#include <string>

struct PositionFile {
    std::string fen;
    int depth;
};

PositionFile read_position_file(const std::string &path);
void write_output_json(const std::string &path, long long perft_nodes);
std::string env_or_default(const char *name, const std::string &fallback);
