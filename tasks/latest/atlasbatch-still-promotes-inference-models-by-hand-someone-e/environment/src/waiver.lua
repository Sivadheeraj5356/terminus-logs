-- Latency waiver discovery and ceiling precedence.

local config = require("config")

local M = {}

local DEFAULT_CEILING = 45.0
local WAIVER_PATH = "/app/archives/comms/latency-waiver-2026-04.eml"

local function waiver_active(batch_id, waiver_content)
    if not waiver_content:find(batch_id, 1, true) then
        return false
    end
    local revert = waiver_content:match("Revert after (%d%d%d%d%-%d%d%-%d%d)")
    local as_of = config.read_as_of_date()
    if not revert or not as_of then
        return false
    end
    return as_of <= revert
end

function M.latency_ceiling_ms(batch_id)
    local fh = io.open(WAIVER_PATH, "r")
    if not fh then
        return DEFAULT_CEILING
    end
    local content = fh:read("*a")
    fh:close()

    if not waiver_active(batch_id, content) then
        return DEFAULT_CEILING
    end

    local ceiling = content:match("ceiling from 45 ms to %*%*([%d%.]+) ms%*%*")
    if ceiling then
        return tonumber(ceiling)
    end
    return DEFAULT_CEILING
end

return M
