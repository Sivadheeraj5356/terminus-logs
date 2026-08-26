#include "f3_stage.hpp"

#include <cstring>
#include <fstream>
#include <string>

int fn_f3(const char* env_root, uint32_t mark, char* route_out, size_t route_cap) {
    (void)mark;
    std::string route = "open";
    {
        std::ifstream tok(std::string(env_root) + "/w8g/staged/local_mux.token");
        if (tok) {
            std::string line;
            if (std::getline(tok, line) && line == "ok") route = "detached";
        }
    }
    if (route_out && route_cap > 0) {
        std::strncpy(route_out, route.c_str(), route_cap - 1);
        route_out[route_cap - 1] = '\0';
    }
    return route == "detached" ? 1 : 0;
}
