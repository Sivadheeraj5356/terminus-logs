-- Digest comparison helpers for compose and manifest gates.

local M = {}

function M.digests_equal(left, right)
    return left == right
end

return M
