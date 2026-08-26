#include "f3_stage.hpp"

#include <cstring>
#include <fstream>
#include <string>

int fn_f3(const char* env_root, uint32_t mark, char* route_out, size_t route_cap) {
    (void)mark;
    std::string route = "detached";
    {
        std::ifstream tok(std::string(env_root) + "/w8g/staged/local_mux.token");
        if (!tok) route = "open";
    }
    {
        std::ifstream mux("/app/state/wg/stage_mux.txt");
        if (mux) route = "open";
    }
    if (route_out && route_cap > 0) {
        std::strncpy(route_out, route.c_str(), route_cap - 1);
        route_out[route_cap - 1] = '\0';
    }
    return route == "detached" ? 1 : 0;
}

int f3_emit_mark(const char* env_root, uint32_t mark, char* route_out, size_t route_cap) {
    return fn_f3(env_root, mark, route_out, route_cap);
}
