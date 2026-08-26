-- Loads candidate rows from the evaluation database.

local M = {}

function M.load_candidate(db_path, candidate_id)
    local escaped = candidate_id:gsub("'", "''")
    local query = string.format(
        "SELECT candidate_id, model_id, sklearn_pin, artifact_digest, accuracy, macro_f1, "
        .. "latency_p99_ms, canary_fixture, batch_id, eval_completed_at, holdout_samples FROM candidates "
        .. "WHERE candidate_id='%s';",
        escaped
    )
    local cmd = string.format("sqlite3 -separator '|' %q %q", db_path, query)
    local fh = io.popen(cmd)
    if not fh then
        return nil
    end
    local line = fh:read("*l")
    fh:close()
    if not line or line == "" then
        return nil
    end

    local parts = {}
    local index = 1
    for field in string.gmatch(line, "([^|]+)") do
        parts[index] = field
        index = index + 1
    end

    return {
        candidate_id = parts[1],
        model_id = parts[2],
        sklearn_pin = parts[3],
        artifact_digest = parts[4],
        accuracy = tonumber(parts[5]),
        macro_f1 = tonumber(parts[6]),
        latency_p99_ms = tonumber(parts[7]),
        canary_fixture = parts[9],
        batch_id = parts[8],
        holdout_samples = tonumber(parts[11]),
    }
end

return M
