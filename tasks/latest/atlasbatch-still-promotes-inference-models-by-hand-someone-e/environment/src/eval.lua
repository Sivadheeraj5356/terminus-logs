-- Evaluation freshness window helpers.

local config = require("config")

local M = {}

local EVAL_WINDOW_DAYS = 30

local function parse_date(text)
    local y, m, d = text:match("(%d%d%d%d)%-(%d%d)%-(%d%d)")
    if not y then
        return nil
    end
    return { year = tonumber(y), month = tonumber(m), day = tonumber(d) }
end

local function date_to_ordinal(parts)
    return os.time({ year = parts.year, month = parts.month, day = parts.day, hour = 12 })
end

function M.is_fresh(eval_completed_at)
    local as_of = config.read_as_of_date()
    if not as_of or not eval_completed_at then
        return false
    end
    local as_of_parts = parse_date(as_of)
    local eval_parts = parse_date(eval_completed_at)
    if not as_of_parts or not eval_parts then
        return false
    end
    local earliest = date_to_ordinal(as_of_parts) - (EVAL_WINDOW_DAYS * 86400)
    return date_to_ordinal(eval_parts) >= earliest
end

return M
