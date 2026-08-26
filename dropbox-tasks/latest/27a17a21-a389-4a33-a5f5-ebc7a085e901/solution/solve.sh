#!/bin/bash
set -euo pipefail

# Fix Makefile bug (shadowing), bash-ism, and add retry logic
cat << 'EOF' > /app/Makefile
.PHONY: all clean run verify serve

all: run verify

override DATA_FILE = dataset.csv

trace_ext.so: trace_ext.c
	gcc -shared -fPIC -I/usr/include/lua5.4 -o trace_ext.so trace_ext.c

.PHONY: $(DATA_FILE)
$(DATA_FILE):
	python3 mock_server.py 8888 & echo $$! > server.pid; sleep 1
	if [ -z "$$NO_FETCH" ]; then \
		curl -f -z $(DATA_FILE) --remote-time --retry 5 --retry-delay 1 --retry-max-time 10 -s http://localhost:8888/iris.csv -o $(DATA_FILE); \
	fi
	kill `cat server.pid` || true; rm -f server.pid

run: $(DATA_FILE) trace_ext.so
	lua5.4 main.lua $(DATA_FILE)

verify: run
	duckdb iris.duckdb < verify.sql

clean:
	rm -f dataset.csv iris.duckdb server.pid insert_results.sql temp.csv trace_ext.so
EOF

# Fix C-extension array bounds (Lua arrays are 1-based) and fix stack memory leak
cat << 'EOF' > /app/trace_ext.c
#include <lua.h>
#include <lauxlib.h>
#include <lualib.h>

static int l_compute_trace(lua_State *L) {
    if (!lua_istable(L, 1)) {
        luaL_error(L, "Expected a table as the first argument");
        return 0;
    }
    double trace = 0.0;
    for (int i = 1; i <= 3; i++) {
        lua_rawgeti(L, 1, i);
        if (lua_istable(L, -1)) {
            lua_rawgeti(L, -1, i);
            if (lua_isnumber(L, -1)) {
                trace += lua_tonumber(L, -1);
            }
            lua_pop(L, 1);
        }
        lua_pop(L, 1);
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
EOF

# Replace main.lua with full correct implementation
cat << 'EOF' > /app/main.lua
local filename = arg[1] or "dataset.csv"

os.execute('duckdb iris.duckdb "CREATE TABLE IF NOT EXISTS iris AS SELECT * FROM read_csv_auto(\'' .. filename .. '\', ignore_errors=true);" ')

local data = {}
local means = {0, 0, 0, 0}
local counts = {0, 0, 0, 0}
local first_line = true

local function trim(value)
    return (value:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function split_csv(line)
    local fields = {}
    local start = 1
    while true do
        local comma = line:find(",", start, true)
        if not comma then
            table.insert(fields, trim(line:sub(start)))
            break
        end
        table.insert(fields, trim(line:sub(start, comma - 1)))
        start = comma + 1
    end
    return fields
end

for line in io.lines(filename) do
    line = line:gsub("\239\187\191", "")
    line = line:gsub("\r", "")

    if first_line then
        first_line = false
    elseif line ~= "" then
        local fields = split_csv(line)
        if #fields >= 4 then
            local row = {}
            for i = 1, 4 do
                local field = fields[i]
                if field ~= "" and field ~= "NA" then
                    row[i] = tonumber(field)
                else
                    row[i] = nil
                end
            end
            table.insert(data, row)
            for j = 1, 4 do
                if row[j] then
                    means[j] = means[j] + row[j]
                    counts[j] = counts[j] + 1
                end
            end
        end
    end
end

for j=1,4 do
    if counts[j] > 0 then means[j] = means[j] / counts[j] else means[j] = 0 end
end

for i=1,#data do
    for j=1,4 do
        if not data[i][j] then data[i][j] = means[j] end
    end
end

local w_means = {0, 0, 0}
local sum_w = 0
for i=1,#data do
    local w = data[i][1]
    sum_w = sum_w + w
    for j=1,3 do w_means[j] = w_means[j] + w * data[i][j+1] end
end
for j=1,3 do w_means[j] = w_means[j] / sum_w end

local cov = {}
for i=1,3 do cov[i] = {0, 0, 0} end

local sum_w2 = 0
for i=1,#data do
    local w = data[i][1]
    sum_w2 = sum_w2 + w * w
    for j=1,3 do
        for k=1,3 do
            cov[j][k] = cov[j][k] + w * (data[i][j+1] - w_means[j]) * (data[i][k+1] - w_means[k])
        end
    end
end

local denom = sum_w * sum_w - sum_w2
local factor = 0
if denom ~= 0 then
    factor = sum_w / denom
end
for j=1,3 do
    for k=1,3 do cov[j][k] = cov[j][k] * factor end
end

local trace_ext = require "trace_ext"
local trace_val = trace_ext.compute_trace(cov)

local function power_iteration(matrix, iterations)
    local v = {1, 1, 1}
    for _ = 1, iterations do
        local next_v = {0, 0, 0}
        for j = 1, 3 do
            for k = 1, 3 do next_v[j] = next_v[j] + matrix[j][k] * v[k] end
        end
        local norm = 0
        for j = 1, 3 do norm = norm + next_v[j]*next_v[j] end
        norm = math.sqrt(norm)
        if norm < 1e-12 then norm = 1e-12 end
        for j = 1, 3 do v[j] = next_v[j] / norm end
    end
    local num = 0
    local den = 0
    for j = 1, 3 do
        local mv = 0
        for k = 1, 3 do mv = mv + matrix[j][k] * v[k] end
        num = num + v[j] * mv
        den = den + v[j] * v[j]
    end
    return num / den, v
end

local eig1, v1 = power_iteration(cov, 100)
local cov2 = {}
for i=1,3 do cov2[i] = {0, 0, 0} end
for i=1,3 do
    for j=1,3 do cov2[i][j] = cov[i][j] - eig1 * v1[i] * v1[j] end
end
local eig2, v2 = power_iteration(cov2, 100)
local eigvals = {eig1, eig2}
table.sort(eigvals, function(a, b) return a > b end)

local f = io.open("insert_results.sql", "w")
f:write("CREATE TABLE IF NOT EXISTS covariance (i INT, j INT, val DOUBLE);\n")
f:write("DELETE FROM covariance;\n")
for j=1,3 do
    for k=1,3 do
        f:write(string.format("INSERT INTO covariance VALUES (%d, %d, %0.15f);\n", j, k, cov[j][k]))
    end
end
f:write("CREATE TABLE IF NOT EXISTS pca (component INT, eigenvalue DOUBLE);\n")
f:write("DELETE FROM pca;\n")
f:write(string.format("INSERT INTO pca VALUES (1, %0.15f);\n", eigvals[1]))
f:write(string.format("INSERT INTO pca VALUES (2, %0.15f);\n", eigvals[2]))
f:write("CREATE TABLE IF NOT EXISTS metrics (name VARCHAR, value DOUBLE);\n")
f:write("DELETE FROM metrics;\n")
f:write(string.format("INSERT INTO metrics VALUES ('trace', %0.15f);\n", trace_val))
f:close()

os.execute('duckdb iris.duckdb < insert_results.sql')
EOF
