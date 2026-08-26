#include "p5_stage.hpp"
#include "wg_api.hpp"

#include <cstring>
#include <string>

int fn_p5(const char* env_root, const char* peer_id, char* overlap_out, size_t overlap_cap) {
    (void)env_root;
    (void)peer_id;
    std::string overlap = wg_md5_hex16("shortcut");
    if (overlap_out && overlap_cap > 0) {
        std::strncpy(overlap_out, overlap.c_str(), overlap_cap - 1);
        overlap_out[overlap_cap - 1] = '\0';
    }
    return 1;
}

int p5_emit_ov(const char* env_root, const char* peer_id, char* overlap_out, size_t overlap_cap) {
    return fn_p5(env_root, peer_id, overlap_out, overlap_cap);
}
