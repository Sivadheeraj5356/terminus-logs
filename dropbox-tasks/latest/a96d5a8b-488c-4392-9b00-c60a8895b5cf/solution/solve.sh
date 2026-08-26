#!/bin/bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path


def apply_replacements(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text()
    staged: list[tuple[str, str]] = []
    for index, (old, new) in enumerate(replacements):
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"expected one occurrence in {path}: {old!r}; found {count}")
        marker = f"__CLOCKWORK_REPLACEMENT_{index}__"
        text = text.replace(old, marker)
        staged.append((marker, new))
    for marker, new in staged:
        text = text.replace(marker, new)
    path.write_text(text)


apply_replacements(
    Path("/app/migrations/004_keeper_audit.lua"),
    [
        ("north = 'gearwell', east = 'gallery', south = NULL, west = NULL", "north = 'gallery', east = 'gearwell', south = NULL, west = NULL"),
        ("north = 'observatory', east = 'archive', south = 'vestibule', west = NULL", "north = 'archive', east = 'observatory', south = 'vestibule', west = NULL"),
        ("north = 'choir', east = NULL, south = NULL, west = 'vestibule'", "north = 'boiler', east = NULL, south = NULL, west = 'vestibule'"),
        ("north = NULL, east = 'ossuary', south = 'gearwell', west = NULL", "north = NULL, east = 'choir', south = 'gearwell', west = NULL"),
        ("north = 'archive', east = NULL, south = NULL, west = 'boiler'", "north = 'ossuary', east = NULL, south = NULL, west = 'boiler'"),
        ("north = NULL, east = 'mirror', south = 'choir', west = NULL", "north = NULL, east = 'archive', south = 'choir', west = NULL"),
        ("north = 'clockheart', east = 'observatory', south = 'gallery', west = 'ossuary'", "north = NULL, east = 'mirror', south = 'gallery', west = 'ossuary'"),
        ("north = 'clockheart', east = NULL, south = NULL, west = 'gallery'", "north = 'mirror', east = NULL, south = NULL, west = 'gallery'"),
        ("north = 'keeper', east = NULL, south = 'archive', west = 'observatory'", "north = 'clockheart', east = NULL, south = 'observatory', west = 'archive'"),
        ("north = NULL, east = 'mirror', south = 'observatory', west = NULL", "north = NULL, east = 'keeper', south = 'mirror', west = NULL"),
        ("north = NULL, east = NULL, south = NULL, west = 'mirror'", "north = NULL, east = NULL, south = NULL, west = 'clockheart'"),
        ("room_id = 'gallery', unlocks = 'choir_latch', reusable = 0", "room_id = 'gearwell', unlocks = 'boiler_hatch', reusable = 1"),
        ("room_id = 'gearwell', unlocks = 'boiler_hatch', reusable = 1", "room_id = 'boiler', unlocks = 'choir_latch', reusable = 0"),
        ("room_id = 'boiler', unlocks = 'archive_door', reusable = 0", "room_id = 'choir', unlocks = 'ossuary_gate', reusable = 1"),
        ("room_id = 'choir', unlocks = 'ossuary_gate', reusable = 1", "room_id = 'ossuary', unlocks = 'archive_door', reusable = 0"),
        ("room_id = 'ossuary', unlocks = 'moon_shutter', reusable = 1", "room_id = 'archive', unlocks = 'mirror_cipher', reusable = 0"),
        ("room_id = 'archive', unlocks = 'mirror_cipher', reusable = 0", "room_id = 'observatory', unlocks = 'moon_shutter', reusable = 1"),
        ("room_id = 'observatory', unlocks = 'keeper_gate', reusable = 1", "room_id = 'mirror', unlocks = 'clockheart_prism', reusable = 0"),
        ("room_id = 'keeper', unlocks = 'clockheart_prism', reusable = 1", "room_id = 'clockheart', unlocks = 'keeper_gate', reusable = 0"),
        ("room_id = 'gallery', requires_item = 'soot_ribbon', opens_flag = 'choir_latch_open'", "room_id = 'gearwell', requires_item = 'brass_key', opens_flag = 'boiler_hatch_open'"),
        ("room_id = 'gearwell', requires_item = 'brass_key', opens_flag = 'boiler_hatch_open'", "room_id = 'boiler', requires_item = 'soot_ribbon', opens_flag = 'choir_latch_open'"),
        ("room_id = 'boiler', requires_item = 'bone_token', opens_flag = 'archive_door_open'", "room_id = 'choir', requires_item = 'choir_pin', opens_flag = 'ossuary_gate_open'"),
        ("room_id = 'choir', requires_item = 'choir_pin', opens_flag = 'ossuary_gate_open'", "room_id = 'ossuary', requires_item = 'bone_token', opens_flag = 'archive_door_open'"),
        ("room_id = 'archive', requires_item = 'vellum_strip', opens_flag = 'mirror_cipher_open'", "room_id = 'observatory', requires_item = 'silver_lens', opens_flag = 'moon_shutter_open'"),
        ("room_id = 'observatory', requires_item = 'silver_lens', opens_flag = 'moon_shutter_open'", "room_id = 'archive', requires_item = 'vellum_strip', opens_flag = 'mirror_cipher_open'"),
        ("room_id = 'keeper', requires_item = 'pendulum_tooth', opens_flag = 'keeper_gate_open'", "room_id = 'mirror', requires_item = 'mirror_shard', opens_flag = 'clockheart_prism_open'"),
        ("room_id = 'mirror', requires_item = 'mirror_shard', opens_flag = 'clockheart_prism_open'", "room_id = 'clockheart', requires_item = 'pendulum_tooth', opens_flag = 'keeper_gate_open'"),
        ("room_id = 'gallery', gate_flag = 'choir_latch_open', dialogue_flag = 'ashes_collect', grants_flag = 'furnace_bank_2'", "room_id = 'boiler', gate_flag = 'boiler_hatch_open', dialogue_flag = 'ash_confession', grants_flag = 'furnace_bank_3'"),
        ("room_id = 'boiler', gate_flag = 'boiler_hatch_open', dialogue_flag = 'hymn_forwards', grants_flag = 'hymn_unturned'", "room_id = 'choir', gate_flag = 'choir_latch_open', dialogue_flag = 'hymn_backwards', grants_flag = 'hymn_reversed'"),
        ("room_id = 'choir', gate_flag = 'archive_door_open', dialogue_flag = 'kept_bone', grants_flag = 'bone_token_kept'", "room_id = 'ossuary', gate_flag = 'ossuary_gate_open', dialogue_flag = 'borrowed_bone', grants_flag = 'bone_token_returned'"),
        ("room_id = 'ossuary', gate_flag = 'ossuary_gate_open', dialogue_flag = 'ink_with_shadow', grants_flag = 'archive_denial'", "room_id = 'archive', gate_flag = 'archive_door_open', dialogue_flag = 'ink_without_shadow', grants_flag = 'archive_oath'"),
        ("room_id = 'archive', gate_flag = 'mirror_cipher_open', dialogue_flag = 'stars_forget', grants_flag = 'stars_erased'", "room_id = 'observatory', gate_flag = 'moon_shutter_open', dialogue_flag = 'stars_remember', grants_flag = 'stars_named'"),
        ("room_id = 'observatory', gate_flag = 'moon_shutter_open', dialogue_flag = 'the_second_face', grants_flag = 'reflection_denied'", "room_id = 'mirror', gate_flag = 'mirror_cipher_open', dialogue_flag = 'the_third_face', grants_flag = 'reflection_named'"),
        ("room_id = 'clockheart', gate_flag = 'clockheart_prism_open', dialogue_flag = 'the_clock_collects', grants_flag = 'crypt_unsettled'", "room_id = 'keeper', gate_flag = 'keeper_gate_open', dialogue_flag = 'the_clock_forgives', grants_flag = 'crypt_reconciled'"),
        ("room_id = 'gallery', action = 'display', subject_id = 'gear', requires_flag = 'keeper_seal_set', emits_flag = 'first_panel_set'", "room_id = 'gearwell', action = 'turn', subject_id = 'brass_key', requires_flag = 'boiler_hatch_open', emits_flag = 'gear_teeth_aligned'"),
        ("room_id = 'mirror', action = 'name', subject_id = 'mirror_shard', requires_flag = 'reflection_named', emits_flag = 'third_face_set'", "room_id = 'boiler', action = 'stoke', subject_id = 'soot_ribbon', requires_flag = 'furnace_bank_3', emits_flag = 'ash_pressure_set'"),
        ("room_id = 'archive', action = 'scribe', subject_id = 'vellum_strip', requires_flag = 'archive_oath', emits_flag = 'vellum_clause_set'", "room_id = 'choir', action = 'reverse', subject_id = 'choir_pin', requires_flag = 'hymn_reversed', emits_flag = 'choir_phrase_set'"),
        ("room_id = 'gearwell', action = 'turn', subject_id = 'brass_key', requires_flag = 'boiler_hatch_open', emits_flag = 'gear_teeth_aligned'", "room_id = 'ossuary', action = 'return', subject_id = 'bone_token', requires_flag = 'bone_token_returned', emits_flag = 'pendulum_bones_set'"),
        ("room_id = 'mirror', action = 'reflect', subject_id = 'mirror', requires_flag = 'third_face_set', emits_flag = 'second_panel_set'", "room_id = 'archive', action = 'scribe', subject_id = 'vellum_strip', requires_flag = 'archive_oath', emits_flag = 'vellum_clause_set'"),
        ("room_id = 'choir', action = 'reverse', subject_id = 'choir_pin', requires_flag = 'hymn_reversed', emits_flag = 'choir_phrase_set'", "room_id = 'observatory', action = 'focus', subject_id = 'silver_lens', requires_flag = 'stars_named', emits_flag = 'lunar_index_set'"),
        ("room_id = 'keeper', action = 'forgive', subject_id = 'keeper', requires_flag = 'crypt_reconciled', emits_flag = 'keeper_seal_set'", "room_id = 'mirror', action = 'name', subject_id = 'mirror_shard', requires_flag = 'reflection_named', emits_flag = 'third_face_set'"),
        ("room_id = 'clockheart', action = 'chime', subject_id = 'heart', requires_flag = 'keeper_seal_set', emits_flag = 'crypt_open'", "room_id = 'clockheart', action = 'seat', subject_id = 'pendulum_tooth', requires_flag = 'clockheart_prism_open', emits_flag = 'escapement_set'"),
        ("room_id = 'boiler', action = 'stoke', subject_id = 'soot_ribbon', requires_flag = 'furnace_bank_3', emits_flag = 'ash_pressure_set'", "room_id = 'keeper', action = 'forgive', subject_id = 'keeper', requires_flag = 'crypt_reconciled', emits_flag = 'keeper_seal_set'"),
        ("room_id = 'observatory', action = 'focus', subject_id = 'silver_lens', requires_flag = 'stars_named', emits_flag = 'lunar_index_set'", "room_id = 'gallery', action = 'display', subject_id = 'gear', requires_flag = 'gear_teeth_aligned', emits_flag = 'first_panel_set'"),
        ("room_id = 'clockheart', action = 'seat', subject_id = 'pendulum_tooth', requires_flag = 'clockheart_prism_open', emits_flag = 'escapement_set'", "room_id = 'mirror', action = 'reflect', subject_id = 'mirror', requires_flag = 'third_face_set', emits_flag = 'second_panel_set'"),
        ("room_id = 'ossuary', action = 'return', subject_id = 'bone_token', requires_flag = 'bone_token_returned', emits_flag = 'pendulum_bones_set'", "room_id = 'clockheart', action = 'chime', subject_id = 'heart', requires_flag = 'keeper_seal_set', emits_flag = 'crypt_open'"),
        ("source = 'moon.ppm', position = 4, rotation = 0, matte = '#0D2440'", "source = 'gear.ppm', position = 1, rotation = 90, matte = '#241D2F'"),
        ("source = 'raven.ppm', position = 1, rotation = 90, matte = '#1D1727'", "source = 'moon.ppm', position = 2, rotation = 0, matte = '#0D2440'"),
        ("source = 'bell.ppm', position = 5, rotation = 180, matte = '#2B2112'", "source = 'raven.ppm', position = 3, rotation = 270, matte = '#1D1727'"),
        ("source = 'eye.ppm', position = 2, rotation = 270, matte = '#141B29'", "source = 'bell.ppm', position = 4, rotation = 180, matte = '#2B2112'"),
        ("source = 'bone.ppm', position = 9, rotation = 90, matte = '#2A2830'", "source = 'eye.ppm', position = 5, rotation = 0, matte = '#141B29'"),
        ("source = 'key.ppm', position = 3, rotation = 0, matte = '#1D2A24'", "source = 'bone.ppm', position = 6, rotation = 90, matte = '#2A2830'"),
        ("source = 'mirror.ppm', position = 8, rotation = 180, matte = '#202737'", "source = 'key.ppm', position = 7, rotation = 270, matte = '#1D2A24'"),
        ("source = 'heart.ppm', position = 6, rotation = 270, matte = '#301923'", "source = 'mirror.ppm', position = 8, rotation = 180, matte = '#202737'"),
        ("source = 'gear.ppm', position = 7, rotation = 90, matte = '#241D2F'", "source = 'heart.ppm', position = 9, rotation = 0, matte = '#301923'"),
    ],
)

apply_replacements(
    Path("/app/tools/build_atlas.sh"),
    [
        ("-filter triangle", "-filter point"),
        ("-resize 40x40", "-resize 44x44"),
        ("-gravity northwest", "-gravity center"),
        ('"${tiles[0]}" "${tiles[2]}" "${tiles[1]}"', '"${tiles[0]}" "${tiles[1]}" "${tiles[2]}"'),
        ('"${tiles[6]}" "${tiles[8]}" "${tiles[7]}"', '"${tiles[6]}" "${tiles[7]}" "${tiles[8]}"'),
    ],
)

Path("/app/game/keeper_circuit.lua").write_text(r'''local db_path = arg[1] or "/app/state/world.db"
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
local room_ids = {}
for line in pipe:lines() do
    local fields = {}
    for field in (line .. "|"):gmatch("(.-)|") do
        fields[#fields + 1] = field
    end
    local id = fields[1]
    room_ids[#room_ids + 1] = id
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

if #room_ids == 0 or #room_ids > 62 then
    io.stderr:write("circuit planner requires between 1 and 62 rooms\n")
    os.exit(2)
end
if rooms[start_id] == nil or rooms[goal_id] == nil then
    io.stderr:write("unknown circuit endpoint\n")
    os.exit(2)
end

local room_bits = {}
for index, id in ipairs(room_ids) do
    room_bits[id] = 1 << (index - 1)
end
for id, exits in pairs(rooms) do
    for _, direction in ipairs(direction_order) do
        local destination = exits[direction]
        if destination ~= "" and rooms[destination] == nil then
            io.stderr:write("unknown room referenced by " .. id .. "\n")
            os.exit(2)
        end
    end
end

local function state_key(room, mask)
    return room .. "|" .. tostring(mask)
end

local full_mask = (1 << #room_ids) - 1
local start_mask = room_bits[start_id]
local start_key = state_key(start_id, start_mask)
local states = {
    [start_key] = {
        room = start_id,
        mask = start_mask,
        parent = nil,
        move = nil,
        distance = 0,
        count = 1,
    },
}
local queue = { start_key }
local head = 1
local answer_key = nil
local answer_distance = nil

if start_id == goal_id and start_mask == full_mask then
    answer_key = start_key
    answer_distance = 0
end

while head <= #queue do
    local key = queue[head]
    head = head + 1
    local state = states[key]
    if answer_distance ~= nil and state.distance >= answer_distance then
        break
    end
    for _, direction in ipairs(direction_order) do
        local destination = rooms[state.room][direction]
        if destination ~= "" then
            local mask = state.mask | room_bits[destination]
            local next_key = state_key(destination, mask)
            local next_distance = state.distance + 1
            if states[next_key] == nil then
                states[next_key] = {
                    room = destination,
                    mask = mask,
                    parent = key,
                    move = direction,
                    distance = next_distance,
                    count = state.count,
                }
                queue[#queue + 1] = next_key
                if destination == goal_id and mask == full_mask and answer_key == nil then
                    answer_key = next_key
                    answer_distance = next_distance
                end
            elseif states[next_key].distance == next_distance then
                states[next_key].count = states[next_key].count + state.count
            end
        end
    end
end

if answer_key == nil then
    io.stderr:write("no all-room circuit from " .. start_id .. " to " .. goal_id .. "\n")
    os.exit(3)
end

local reversed_rooms = {}
local reversed_moves = {}
local key = answer_key
while key ~= nil do
    local state = states[key]
    reversed_rooms[#reversed_rooms + 1] = state.room
    if state.move ~= nil then
        reversed_moves[#reversed_moves + 1] = state.move
    end
    key = state.parent
end

local rooms_path = {}
for index = #reversed_rooms, 1, -1 do
    rooms_path[#rooms_path + 1] = reversed_rooms[index]
end
local moves = {}
for index = #reversed_moves, 1, -1 do
    moves[#moves + 1] = reversed_moves[index]
end

print("steps=" .. tostring(#moves))
print("shortest_walks=" .. tostring(states[answer_key].count))
print("moves=" .. table.concat(moves, ","))
print("rooms=" .. table.concat(rooms_path, ","))
''')
PY

/app/bin/rebuild-world
