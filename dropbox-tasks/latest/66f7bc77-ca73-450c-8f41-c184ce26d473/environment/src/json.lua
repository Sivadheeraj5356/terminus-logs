-- Serializes promotion decision artifacts to JSON.

local M = {}

local function json_escape(value)
    return value:gsub("\\", "\\\\"):gsub('"', '\\"')
end

local function encode_reasons(reasons)
    local parts = {}
    for index, reason in ipairs(reasons) do
        parts[index] = '"' .. json_escape(reason) .. '"'
    end
    return table.concat(parts, ", ")
end

function M.write_decision(output_path, decision)
    local lines = {
        "{",
        '  "candidate_id": "' .. json_escape(decision.candidate_id) .. '",',
        '  "approved": ' .. tostring(decision.approved) .. ",",
        '  "status": "' .. json_escape(decision.status) .. '",',
        '  "reasons": [' .. encode_reasons(decision.reasons) .. "],",
        '  "checks": {',
        '    "canary_ok": ' .. tostring(decision.checks.canary_ok) .. ",",
        '    "eval_fresh": ' .. tostring(decision.checks.eval_fresh) .. ",",
        '    "holdout_ok": ' .. tostring(decision.checks.holdout_ok) .. ",",
        '    "latency_ok": ' .. tostring(decision.checks.latency_ok) .. ",",
        '    "manifest_ok": ' .. tostring(decision.checks.manifest_ok) .. ",",
        '    "metrics_ok": ' .. tostring(decision.checks.metrics_ok) .. ",",
        '    "upstream_tag_present": ' .. tostring(decision.checks.upstream_tag_present) .. ",",
        '    "compose_ok": ' .. tostring(decision.checks.compose_ok),
        "  }",
        "}",
        "",
    }

    local fh = io.open(output_path, "w")
    if not fh then
        return false
    end
    fh:write(table.concat(lines, "\n"))
    fh:close()
    return true
end

return M
