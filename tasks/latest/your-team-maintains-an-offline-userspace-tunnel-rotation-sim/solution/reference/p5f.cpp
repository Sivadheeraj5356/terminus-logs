#include "p5_stage.hpp"
#include "wg_api.hpp"

#include <cstring>
#include <string>

int fn_p5(const char* env_root, const char* peer_id, char* overlap_out, size_t overlap_cap) {
    OvTbl table = load_ov_tbl(std::string(env_root) + "/data/overlap_tbl.toml");
    uint32_t key = 0;
    for (char ch : std::string(peer_id)) key = key * 31u + static_cast<unsigned char>(ch);
    auto it = table.find(key % 1000u);
    if (it == table.end()) return 0;
    std::string overlap = wg_md5_hex16(it->second);
    if (overlap_out && overlap_cap > 0) {
        std::strncpy(overlap_out, overlap.c_str(), overlap_cap - 1);
        overlap_out[overlap_cap - 1] = '\0';
    }
    return 1;
}
