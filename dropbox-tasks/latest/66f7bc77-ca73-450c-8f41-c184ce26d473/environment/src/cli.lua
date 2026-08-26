-- CLI argument parsing and orchestration.

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

    local mirror = config.read_mirror_path()
    if not mirror then
        io.stderr:write("upstream mirror not configured\n")
        return 1
    end

    local tag_present = tags.tag_exists(mirror, candidate.sklearn_pin)
    local ceiling = policy.latency_ceiling_ms(candidate.batch_id)
    local result = decision.evaluate(
        candidate,
        labels,
        baseline,
        tag_present,
        ceiling,
        true
    )

    os.execute("mkdir -p /app/output")
    if not decision.write_decision("/app/output/promotion-decision.json", result) then
        io.stderr:write("failed to write decision\n")
        return 1
    end

    return 0
end

return M
