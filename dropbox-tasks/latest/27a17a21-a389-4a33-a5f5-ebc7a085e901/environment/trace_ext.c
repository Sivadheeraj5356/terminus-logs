#include <lua.h>
#include <lauxlib.h>
#include <lualib.h>

// Computes the trace of a 3x3 matrix represented as a table of tables in Lua.
static int l_compute_trace(lua_State *L) {
    if (!lua_istable(L, 1)) {
        luaL_error(L, "Expected a table as the first argument");
        return 0;
    }

    double trace = 0.0;
    

    for (int i = 0; i < 3; i++) {
        // Get the inner table (matrix[i])
        lua_rawgeti(L, 1, i);
        if (lua_istable(L, -1)) {
            // Get the j-th element (matrix[i][i])
            lua_rawgeti(L, -1, i);
            if (lua_isnumber(L, -1)) {
                trace += lua_tonumber(L, -1);
            }
            lua_pop(L, 1);
        }
    }

    lua_pushnumber(L, trace);
    return 1;
}

static const struct luaL_Reg trace_ext[] = {
    {"compute_trace", l_compute_trace},
    {NULL, NULL}
};

int luaopen_trace_ext(lua_State *L) {
    luaL_newlib(L, trace_ext);
    return 1;
}
