#include "wg_api.hpp"

#include <cstdlib>
#include <fstream>

extern int fn_k7(const char* env_root, int seed, char* digest_out, size_t digest_cap);
extern int fn_f3(const char* env_root, uint32_t mark, char* route_out, size_t route_cap);

namespace {

std::string env_root() {
    const char* root = std::getenv("WG_ENV_ROOT");
    return root ? root : ".";
}

}  // namespace

int capture_mux_snapshot(MuxSnapshot& snap, int variant_seed, uint32_t route_mark) {
    const auto root = env_root();
    char route_buf[32] = {0};
    char k7_buf[32] = {0};
    fn_f3(root.c_str(), route_mark, route_buf, sizeof(route_buf));
    snap.f3_mark = route_buf;
    snap.f3_rc = (snap.f3_mark == "detached") ? 1 : 0;
    snap.k7_rc = fn_k7(root.c_str(), variant_seed, k7_buf, sizeof(k7_buf));
    snap.k7_digest = k7_buf;
    return 0;
}
