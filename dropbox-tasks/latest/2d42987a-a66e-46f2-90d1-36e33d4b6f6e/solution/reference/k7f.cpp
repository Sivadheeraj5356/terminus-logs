#include "k7_stage.hpp"
#include "wg_api.hpp"

#include <cstring>
#include <fstream>
#include <string>

int fn_k7(const char* env_root, int seed, char* digest_out, size_t digest_cap) {
    std::string material = std::string(env_root) + "|seed=" + std::to_string(seed) + "|dual=open";
    std::string digest = wg_md5_hex16(material);
    if (digest_out && digest_cap > 0) {
        std::strncpy(digest_out, digest.c_str(), digest_cap - 1);
        digest_out[digest_cap - 1] = '\0';
    }
    std::ifstream tok(std::string(env_root) + "/w8g/staged/local_mux.token");
    if (!tok) return 0;
    std::string line;
    if (!std::getline(tok, line) || line != "ok") return 0;
    return 1;
}
