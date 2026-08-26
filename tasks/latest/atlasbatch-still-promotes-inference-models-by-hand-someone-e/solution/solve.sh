#!/bin/bash
set -euo pipefail

cat > /app/src/config.lua << 'LUAEOF'
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
    return content:match('mirror_path%s*=%s*"([^"]+)"')
end

function M.read_as_of_date()
    local fh = io.open(CLOCK_PATH, "r")
    if not fh then
        return nil
    end
    local content = fh:read("*a")
    fh:close()
    return content:match('as_of_date%s*=%s*"(%d%d%d%d%-%d%d%-%d%d)"')
end

return M
LUAEOF

cat > /app/src/db.lua << 'LUAEOF'
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
        canary_fixture = parts[8],
        batch_id = parts[9],
        eval_completed_at = parts[10],
        holdout_samples = tonumber(parts[11]),
    }
end

return M
LUAEOF

cat > /app/src/compose.lua << 'LUAEOF'
local M = {}

function M.parse_inference_labels(compose_path)
    local fh = io.open(compose_path, "r")
    if not fh then
        return nil
    end
    local lines = {}
    for line in fh:lines() do
        table.insert(lines, line)
    end
    fh:close()

    local start_index = nil
    for index, line in ipairs(lines) do
        if line:match("^%s+inference:%s*$") then
            start_index = index
            break
        end
    end
    if not start_index then
        return nil
    end

    local block = {}
    for index = start_index + 1, #lines do
        local line = lines[index]
        if line:match("^  %S") and not line:match("^    ") then
            break
        end
        table.insert(block, line)
    end

    local content = table.concat(block, "\n")
    return {
        model_id = content:match('atlas%.model_id:%s*"([^"]+)"'),
        sklearn_pin = content:match('atlas%.sklearn_pin:%s*"([^"]+)"'),
        artifact_digest = content:match('atlas%.artifact_digest:%s*"([^"]+)"'),
    }
end

return M
LUAEOF

cat > /app/src/canary.lua << 'LUAEOF'
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

    local in_canary = false
    local accuracy = nil
    local macro_f1 = nil
    for line in content:gmatch("[^\r\n]+") do
        if line:find('"profile"%s*:%s*"canary"') then
            in_canary = true
        elseif in_canary and line:find('"accuracy"') then
            accuracy = tonumber(line:match(":%s*([%d%.]+)"))
        elseif in_canary and line:find('"macro_f1"') then
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
LUAEOF

cat > /app/src/tags.lua << 'LUAEOF'
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
        if line == tag then
            return true
        end
    end
    return false
end

return M
LUAEOF

cat > /app/src/digest.lua << 'LUAEOF'
local M = {}

local function normalize(value)
    local prefix, body = value:match("^([^:]+):(.*)$")
    if not prefix then
        return value:lower()
    end
    return prefix:lower() .. ":" .. body:lower()
end

function M.digests_equal(left, right)
    return normalize(left) == normalize(right)
end

return M
LUAEOF

cat > /app/src/manifest.lua << 'LUAEOF'
local digest = require("digest")

local M = {}

local MANIFEST_ROOT = "/app/registry/manifests"

function M.digest_registered(model_id, sklearn_pin, artifact_digest)
    local path = MANIFEST_ROOT .. "/" .. model_id .. ".toml"
    local fh = io.open(path, "r")
    if not fh then
        return false
    end
    local content = fh:read("*a")
    fh:close()

    local block_pin = nil
    for line in content:gmatch("[^\r\n]+") do
        local pin = line:match('sklearn_pin%s*=%s*"([^"]+)"')
        if pin then
            block_pin = pin
        end
        local registered = line:match('artifact_digest%s*=%s*"([^"]+)"')
        if registered and block_pin == sklearn_pin then
            if digest.digests_equal(registered, artifact_digest) then
                return true
            end
        end
    end
    return false
end

return M
LUAEOF

cat > /app/src/eval.lua << 'LUAEOF'
local config = require("config")

local M = {}

local EVAL_WINDOW_DAYS = 14

local function parse_date(text)
    local y, m, d = text:match("(%d%d%d%d)%-(%d%d)%-(%d%d)")
    if not y then
        return nil
    end
    return { year = tonumber(y), month = tonumber(m), day = tonumber(d) }
end

local function date_to_ordinal(parts)
    return os.time({ year = parts.year, month = parts.month, day = parts.day, hour = 12 })
end

function M.is_fresh(eval_completed_at)
    local as_of = config.read_as_of_date()
    if not as_of or not eval_completed_at then
        return false
    end
    local as_of_parts = parse_date(as_of)
    local eval_parts = parse_date(eval_completed_at)
    if not as_of_parts or not eval_parts then
        return false
    end
    local earliest = date_to_ordinal(as_of_parts) - (EVAL_WINDOW_DAYS * 86400)
    return date_to_ordinal(eval_parts) >= earliest
end

return M
LUAEOF

cat > /app/src/waiver.lua << 'LUAEOF'
local config = require("config")

local M = {}

local DEFAULT_CEILING = 45.0
local WAIVER_DIR = "/app/archives/comms"

local function waiver_files()
    local entries = {}
    local cmd = string.format("ls -1 %q 2>/dev/null", WAIVER_DIR)
    local fh = io.popen(cmd)
    if not fh then
        return entries
    end
    for line in fh:lines() do
        if line:match("^latency%-waiver%-.+%.eml$") then
            table.insert(entries, WAIVER_DIR .. "/" .. line)
        end
    end
    fh:close()
    table.sort(entries)
    return entries
end

local function batch_mentioned(batch_id, content)
    local escaped = batch_id:gsub("([%-%.%+%[%]%(%)%$%^%%%?%*])", "%%%1")
    local pattern = "%f[%w]" .. escaped .. "%f[%W]"
    return content:match(pattern) ~= nil
end

local function waiver_active(batch_id, waiver_content)
    if not batch_mentioned(batch_id, waiver_content) then
        return false
    end
    local revert = waiver_content:match("Revert after (%d%d%d%d%-%d%d%-%d%d)")
    local as_of = config.read_as_of_date()
    if not revert or not as_of then
        return false
    end
    return as_of < revert
end

function M.latency_ceiling_ms(batch_id)
    local best = DEFAULT_CEILING
    for _, path in ipairs(waiver_files()) do
        local fh = io.open(path, "r")
        if fh then
            local content = fh:read("*a")
            fh:close()
            if waiver_active(batch_id, content) then
                local ceiling = content:match("ceiling from 45 ms to %*%*([%d%.]+) ms%*%*")
                if ceiling then
                    local value = tonumber(ceiling)
                    if value > best then
                        best = value
                    end
                end
            end
        end
    end
    return best
end

return M
LUAEOF

cat > /app/src/policy.lua << 'LUAEOF'
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
LUAEOF

cat > /app/src/json.lua << 'LUAEOF'
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
        '  "approved": ' .. tostring(decision.approved) .. ",",
        '  "candidate_id": "' .. json_escape(decision.candidate_id) .. '",',
        '  "checks": {',
        '    "canary_ok": ' .. tostring(decision.checks.canary_ok) .. ",",
        '    "compose_ok": ' .. tostring(decision.checks.compose_ok) .. ",",
        '    "eval_fresh": ' .. tostring(decision.checks.eval_fresh) .. ",",
        '    "holdout_ok": ' .. tostring(decision.checks.holdout_ok) .. ",",
        '    "latency_ok": ' .. tostring(decision.checks.latency_ok) .. ",",
        '    "manifest_ok": ' .. tostring(decision.checks.manifest_ok) .. ",",
        '    "metrics_ok": ' .. tostring(decision.checks.metrics_ok) .. ",",
        '    "upstream_tag_present": ' .. tostring(decision.checks.upstream_tag_present),
        "  },",
        '  "reasons": [' .. encode_reasons(decision.reasons) .. "],",
        '  "status": "' .. json_escape(decision.status) .. '"',
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
LUAEOF

cat > /app/src/round.lua << 'LUAEOF'
local M = {}

function M.round_metric(value)
    return math.floor(value * 1000 + 0.5) / 1000
end

return M
LUAEOF

cat > /app/src/decision.lua << 'LUAEOF'
local json = require("json")
local round = require("round")
local digest = require("digest")
local manifest = require("manifest")

local M = {}

local HOLDOUT_MINIMUM = 500

function M.evaluate(candidate, compose_labels, baseline, tag_present, ceiling_ms, canary_ok, eval_fresh)
    local metrics_ok = round.round_metric(candidate.accuracy) >= round.round_metric(baseline.accuracy)
        and round.round_metric(candidate.macro_f1) >= round.round_metric(baseline.macro_f1)
    local latency_ok = candidate.latency_p99_ms <= ceiling_ms
    local compose_ok = compose_labels.model_id == candidate.model_id
        and compose_labels.sklearn_pin == candidate.sklearn_pin
        and digest.digests_equal(compose_labels.artifact_digest, candidate.artifact_digest)
    local holdout_ok = candidate.holdout_samples >= HOLDOUT_MINIMUM
    local manifest_ok = manifest.digest_registered(
        candidate.model_id,
        candidate.sklearn_pin,
        candidate.artifact_digest
    )

    local reasons = {}
    if not tag_present then
        table.insert(reasons, "upstream_tag_missing")
    end
    if not metrics_ok then
        table.insert(reasons, "metric_regression")
    end
    if not latency_ok then
        table.insert(reasons, "latency_breach")
    end
    if not compose_ok then
        table.insert(reasons, "compose_metadata_mismatch")
    end
    if not canary_ok then
        table.insert(reasons, "canary_batch_mismatch")
    end
    if not eval_fresh then
        table.insert(reasons, "eval_stale")
    end
    if not holdout_ok then
        table.insert(reasons, "holdout_sample_insufficient")
    end
    if not manifest_ok then
        table.insert(reasons, "artifact_manifest_mismatch")
    end
    table.sort(reasons)

    local approved = #reasons == 0
    return {
        candidate_id = candidate.candidate_id,
        approved = approved,
        status = approved and "approved" or "rejected",
        reasons = reasons,
        checks = {
            canary_ok = canary_ok,
            compose_ok = compose_ok,
            eval_fresh = eval_fresh,
            holdout_ok = holdout_ok,
            latency_ok = latency_ok,
            manifest_ok = manifest_ok,
            metrics_ok = metrics_ok,
            upstream_tag_present = tag_present,
        },
    }
end

function M.write_decision(output_path, decision)
    return json.write_decision(output_path, decision)
end

return M
LUAEOF

cat > /app/src/cli.lua << 'LUAEOF'
local db = require("db")
local compose = require("compose")
local canary = require("canary")
local tags = require("tags")
local policy = require("policy")
local decision = require("decision")
local config = require("config")

local M = {}

local function parse_args(argv)
    local args = { command = nil, candidate = nil, compose = nil }
    local index = 1
    while index <= #argv do
        local token = argv[index]
        if token == "run" then
            args.command = "run"
        elseif token == "--candidate" then
            index = index + 1
            args.candidate = argv[index]
        elseif token == "--compose" then
            index = index + 1
            args.compose = argv[index]
        end
        index = index + 1
    end
    return args
end

function M.main(argv)
    local args = parse_args(argv)
    if args.command ~= "run" or not args.candidate or not args.compose then
        io.stderr:write("usage: atlas-promote run --candidate <id> --compose <path>\n")
        return 2
    end

    local candidate = db.load_candidate("/app/data/eval.db", args.candidate)
    if not candidate then
        io.stderr:write("unknown candidate: " .. args.candidate .. "\n")
        return 1
    end

    local labels = compose.parse_inference_labels(args.compose)
    if not labels or not labels.model_id then
        io.stderr:write("failed to parse compose file\n")
        return 1
    end

    local baseline = canary.load_baseline(candidate.canary_fixture)
    if not baseline then
        io.stderr:write("failed to load canary baseline\n")
        return 1
    end

    local fixture_batch = canary.fixture_batch_id(candidate.canary_fixture)
    if not fixture_batch then
        io.stderr:write("failed to read fixture batch_id\n")
        return 1
    end

    local mirror = config.read_mirror_path()
    if not mirror then
        io.stderr:write("upstream mirror not configured\n")
        return 1
    end

    local tag_present = tags.tag_exists(mirror, candidate.sklearn_pin)
    local ceiling = policy.latency_ceiling_ms(candidate.batch_id)
    local canary_ok = fixture_batch == candidate.batch_id
    local eval_fresh = policy.eval_is_fresh(candidate.eval_completed_at)
    local result = decision.evaluate(
        candidate,
        labels,
        baseline,
        tag_present,
        ceiling,
        canary_ok,
        eval_fresh
    )

    os.execute("mkdir -p /app/output")
    if not decision.write_decision("/app/output/promotion-decision.json", result) then
        io.stderr:write("failed to write decision\n")
        return 1
    end

    return 0
end

return M
LUAEOF
