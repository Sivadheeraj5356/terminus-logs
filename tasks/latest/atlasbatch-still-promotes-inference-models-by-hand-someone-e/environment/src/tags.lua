-- Lists release tags from the configured sklearn mirror.

local M = {}

function M.tag_exists(mirror_path, tag)
    local cmd = string.format("git -C %q tag -l", mirror_path)
    local fh = io.popen(cmd)
    if not fh then
        return false
    end
    local output = fh:read("*a")
    fh:close()

    for line in output:gmatch("[^\r\n]+") do
        if line == "v" .. tag then
            return true
        end
    end
    return false
end

return M
