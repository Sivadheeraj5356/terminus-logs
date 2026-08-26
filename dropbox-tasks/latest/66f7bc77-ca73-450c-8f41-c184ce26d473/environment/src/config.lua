-- Reads runtime configuration paths and evaluation clock.

local M = {}

local UPSTREAM_PATH = "/app/config/upstream.toml"
local CLOCK_PATH = "/app/config/eval-clock.toml"

function M.read_mirror_path()
    local fh = io.open(UPSTREAM_PATH, "r")
    if not fh then
        return nil
    end
    local content = fh:read("*a")
    fh:close()
    return content:match("remote_url%s*=%s*\"([^\"]+)\"")
end

function M.read_as_of_date()
    local fh = io.open(CLOCK_PATH, "r")
    if not fh then
        return nil
    end
    local content = fh:read("*a")
    fh:close()
    return content:match("eval_date%s*=%s*\"(%d%d%d%d%-%d%d%-%d%d)\"")
end

return M
