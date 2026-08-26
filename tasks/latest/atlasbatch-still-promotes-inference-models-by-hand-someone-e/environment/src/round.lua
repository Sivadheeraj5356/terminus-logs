-- Shared metric rounding for gate comparisons.

local M = {}

function M.round_metric(value)
    return math.floor(value * 100 + 0.5) / 100
end

return M
