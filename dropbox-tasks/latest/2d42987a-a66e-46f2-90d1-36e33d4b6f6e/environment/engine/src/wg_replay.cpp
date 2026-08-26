#include "wg_replay.hpp"

#include <cstdio>
#include <fstream>
#include <string>

static const char* STAGE_PATH = "/app/state/wg/stage_mux.txt";

void replay_invalidate_all() {
    std::remove(STAGE_PATH);
}

int replay_save_snapshot(const MuxSnapshot& snap) {
    std::system("mkdir -p /app/state/wg");
    std::ofstream out(STAGE_PATH);
    out << snap.perm_epoch << "\n"
        << snap.k7_rc << "\n"
        << snap.f3_rc << "\n"
        << snap.k7_digest << "\n"
        << snap.f3_mark << "\n";
    return 0;
}

int replay_load_snapshot(MuxSnapshot* snap) {
    std::ifstream in(STAGE_PATH);
    if (!in) return -1;
    std::getline(in, snap->perm_epoch);
    std::string line;
    if (!std::getline(in, line)) return -1;
    snap->k7_rc = std::stoi(line);
    if (!std::getline(in, line)) return -1;
    snap->f3_rc = std::stoi(line);
    if (!std::getline(in, snap->k7_digest)) return -1;
    if (!std::getline(in, snap->f3_mark)) return -1;
    return 0;
}
