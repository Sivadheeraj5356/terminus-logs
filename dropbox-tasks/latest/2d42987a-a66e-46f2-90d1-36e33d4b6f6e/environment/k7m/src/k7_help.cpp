#include "k7_stage.hpp"

#include <cstdio>
#include <fstream>
#include <string>

void list_peer_labels(const char* env_root) {
    std::ifstream in(std::string(env_root) + "/docs/peer_ids.txt");
    std::string line;
    while (std::getline(in, line)) {
        if (!line.empty() && line[0] != '#') std::printf("id:%s\n", line.c_str());
    }
}
