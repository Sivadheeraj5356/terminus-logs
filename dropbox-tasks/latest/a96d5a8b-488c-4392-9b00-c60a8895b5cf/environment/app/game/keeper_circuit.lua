local db_path = arg[1] or "/app/state/world.db"
local start_id = arg[2] or "vestibule"
local goal_id = arg[3] or "keeper"

local direction_order = { "north", "east", "south", "west" }

local function shell_quote(value)
    return "'" .. value:gsub("'", "'\\''") .. "'"
end

local query = table.concat({
    "SELECT id, COALESCE(north, ''), COALESCE(east, ''),",
    "COALESCE(south, ''), COALESCE(west, '') FROM rooms ORDER BY id;",
}, " ")
local command = "sqlite3 -batch -noheader -separator '|' "
    .. shell_quote(db_path) .. " " .. shell_quote(query)
local pipe = assert(io.popen(command, "r"))

local rooms = {}
for line in pipe:lines() do
    local fields = {}
    for field in (line .. "|"):gmatch("(.-)|") do
        fields[#fields + 1] = field
    end
    local id = fields[1]
    rooms[id] = {
        north = fields[2],
        east = fields[3],
        south = fields[4],
        west = fields[5],
    }
end
local ok = pipe:close()
if not ok then
    io.stderr:write("could not read room graph\n")
    os.exit(2)
end

if rooms[start_id] == nil or rooms[goal_id] == nil then
    io.stderr:write("unknown circuit endpoint\n")
    os.exit(2)
end

-- Rehearsal draft: this queue remembers only the current room. Once a room has
-- been seen by any partial route, later routes reaching it with a different
-- visited set are discarded. That shortcut finds an ordinary endpoint route,
-- but it cannot solve the signed all-room circuit contract.
local queue = { { room = start_id, moves = {}, path = { start_id } } }
local seen = { [start_id] = true }
local head = 1
while head <= #queue do
    local state = queue[head]
    head = head + 1
    if state.room == goal_id and #state.path == 1 then
        break
    end
    for _, direction in ipairs(direction_order) do
        local destination = rooms[state.room][direction]
        if destination ~= "" and not seen[destination] then
            seen[destination] = true
            local moves = { table.unpack(state.moves) }
            local path = { table.unpack(state.path) }
            moves[#moves + 1] = direction
            path[#path + 1] = destination
            queue[#queue + 1] = { room = destination, moves = moves, path = path }
        end
    end
end

io.stderr:write("no all-room circuit from " .. start_id .. " to " .. goal_id .. "\n")
os.exit(3)
