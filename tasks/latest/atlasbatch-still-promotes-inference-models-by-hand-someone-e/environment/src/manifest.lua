-- Registry manifest lookup for artifact digests.

local M = {}

local MANIFEST_ROOT = "/app/docs/manifests"

function M.digest_registered(model_id, sklearn_pin, artifact_digest)
    local path = MANIFEST_ROOT .. "/" .. model_id .. ".toml"
    local fh = io.open(path, "r")
    if not fh then
        return false
    end
    local content = fh:read("*a")
    fh:close()

    local block_pin = nil
    local block_digest = nil
    for line in content:gmatch("[^\r\n]+") do
        local pin = line:match('sklearn_pin%s*=%s*"([^"]+)"')
        if pin then
            block_pin = pin
        end
        local digest = line:match('artifact_digest%s*=%s*"([^"]+)"')
        if digest then
            block_digest = digest
            if block_pin == sklearn_pin and block_digest == artifact_digest then
                return true
            end
        end
    end
    return false
end

return M
