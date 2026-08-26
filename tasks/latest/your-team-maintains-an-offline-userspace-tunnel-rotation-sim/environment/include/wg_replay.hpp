#pragma once

#include <cstdint>
#include <string>

struct MuxSnapshot {
    std::string perm_epoch;
    std::string k7_digest;
    std::string f3_mark;
    int k7_rc = 0;
    int f3_rc = 0;
};

int replay_save_snapshot(const MuxSnapshot& snap);
int replay_load_snapshot(MuxSnapshot* snap);
void replay_invalidate_all();
