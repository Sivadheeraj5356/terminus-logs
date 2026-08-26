#include "wg_api.hpp"

#include <cstdio>

void dump_overlap_labels(const char* env_root) {
    OvTbl tags = load_ov_tbl(std::string(env_root) + "/data/overlap_tbl.toml");
    for (const auto& [id, name] : tags) {
        std::printf("id=%u name=%s\n", id, name.c_str());
    }
}
