-- Reads nested canary baseline metrics from fixture JSON.

local M = {}

function M.fixture_batch_id(fixture_path)
    local fh = io.open(fixture_path, "r")
    if not fh then
        return nil
    end
    local content = fh:read("*a")
    fh:close()
    return content:match('"batch_id"%s*:%s*"([^"]+)"')
end

function M.load_baseline(fixture_path)
    local fh = io.open(fixture_path, "r")
    if not fh then
        return nil
    end
    local content = fh:read("*a")
    fh:close()

    local accuracy = nil
    local macro_f1 = nil
    for line in content:gmatch("[^\r\n]+") do
        if line:find('"accuracy"') then
            accuracy = tonumber(line:match(":%s*([%d%.]+)"))
        elseif line:find('"macro_f1"') then
            macro_f1 = tonumber(line:match(":%s*([%d%.]+)"))
            break
        end
    end

    if accuracy == nil or macro_f1 == nil then
        return nil
    end
    return { accuracy = accuracy, macro_f1 = macro_f1 }
end

return M
