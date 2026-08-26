#include "p5_stage.hpp"
#include "wg_api.hpp"

#include <cstring>
#include <string>

int fn_p5(const char* env_root, const char* peer_id, char* overlap_out, size_t overlap_cap) {
    (void)env_root;
    (void)peer_id;
    (void)overlap_out;
    (void)overlap_cap;
    return 0;
}

int p5_emit_ov(const char* env_root, const char* peer_id, char* overlap_out, size_t overlap_cap) {
    return fn_p5(env_root, peer_id, overlap_out, overlap_cap);
}
