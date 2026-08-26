-- Loads promotion policy including latency ceiling precedence.

local waiver = require("waiver")
local eval = require("eval")

local M = {}

function M.latency_ceiling_ms(batch_id)
    return waiver.latency_ceiling_ms(batch_id)
end

function M.eval_is_fresh(eval_completed_at)
    return eval.is_fresh(eval_completed_at)
end

return M
