#include "k7_stage.hpp"
#include "wg_api.hpp"

#include <cstring>
#include <fstream>
#include <string>

int fn_k7(const char* env_root, int seed, char* digest_out, size_t digest_cap) {
    std::string material = std::string(env_root) + "|seed=" + std::to_string(seed);
    bool dual_present = false;
    {
        std::ifstream alt(std::string(env_root) + "/w8g/staged/dual_alt.bin");
        if (alt) {
            dual_present = true;
            std::string alt_body((std::istreambuf_iterator<char>(alt)), std::istreambuf_iterator<char>());
            material += "|dual=" + alt_body;
        } else {
            material += "|single";
        }
    }
    std::string digest = wg_md5_hex16(material);
    if (digest_out && digest_cap > 0) {
        std::strncpy(digest_out, digest.c_str(), digest_cap - 1);
        digest_out[digest_cap - 1] = '\0';
    }
    std::ifstream tok(std::string(env_root) + "/w8g/staged/local_mux.token");
    if (!tok) return 0;
    std::string line;
    if (!std::getline(tok, line) || line != "ok") return 0;
    if (dual_present) return 0;
    return 1;
}

int k7_emit_mux(const char* env_root, int seed, char* digest_out, size_t digest_cap) {
    return fn_k7(env_root, seed, digest_out, digest_cap);
}
