local db_path = arg[1] or "/app/state/world.db"
local root = "/app"
local sql_path = root .. "/.build/migrations.sql"

local function shell_quote(value)
    return "'" .. value:gsub("'", "'\\''") .. "'"
end

local migrations = {
    "001_schema.lua",
    "002_legacy_seed.lua",
    "003_gallery_refit.lua",
    "004_keeper_audit.lua",
}

os.remove(db_path)

local output = assert(io.open(sql_path, "w"))
output:write("PRAGMA foreign_keys = ON;\n")
for _, filename in ipairs(migrations) do
    local sql = dofile(root .. "/migrations/" .. filename)
    assert(type(sql) == "string", filename .. " must return SQL text")
    output:write("\n-- ", filename, "\n", sql, "\n")
end
output:close()

local ok, reason, status = os.execute(
    "sqlite3 -batch " .. shell_quote(db_path) .. " < " .. shell_quote(sql_path)
)
if not ok then
    io.stderr:write(string.format("migration failed (%s %s)\n", tostring(reason), tostring(status)))
    os.exit(1)
end

print("rebuilt " .. db_path)
