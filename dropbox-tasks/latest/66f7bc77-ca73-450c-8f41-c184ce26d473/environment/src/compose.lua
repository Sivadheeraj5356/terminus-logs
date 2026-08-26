-- Parses inference service metadata from a Compose file.

local M = {}

function M.parse_inference_labels(compose_path)
    local fh = io.open(compose_path, "r")
    if not fh then
        return nil
    end
    local content = fh:read("*a")
    fh:close()

    return {
        model_id = content:match('atlas%.model_id:%s*"([^"]+)"'),
        sklearn_pin = content:match('SKLEARN_VERSION:%s*"([^"]+)"'),
        artifact_digest = content:match('atlas%.artifact_digest:%s*"([^"]+)"'),
    }
end

return M
