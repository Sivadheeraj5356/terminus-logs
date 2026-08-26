#include "f3_stage.hpp"

#include <cstring>
#include <fstream>
#include <string>

int fn_f3(const char* env_root, uint32_t mark, char* route_out, size_t route_cap) {
    (void)env_root;
    (void)mark;
    std::string route = "open";
    if (route_out && route_cap > 0) {
        std::strncpy(route_out, route.c_str(), route_cap - 1);
        route_out[route_cap - 1] = '\0';
    }
    return 0;
}

int f3_emit_mark(const char* env_root, uint32_t mark, char* route_out, size_t route_cap) {
    return fn_f3(env_root, mark, route_out, route_cap);
}
