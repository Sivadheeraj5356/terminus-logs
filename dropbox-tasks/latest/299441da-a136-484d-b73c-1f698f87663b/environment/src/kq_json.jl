function parse_scenario_block(block::String)
    info = Dict{String, Any}()
    for fm in eachmatch(r"\"([a-z_]+)\"\s*:\s*(\d+)", block)
        info[fm.captures[1]] = parse(Int, fm.captures[2])
    end
    for fm in eachmatch(r"\"([a-z_]+_hex)\"\s*:\s*\"([^\"]+)\"", block)
        info[fm.captures[1]] = fm.captures[2]
    end
    for fm in eachmatch(r"\"(define_blob)\"\s*:\s*\"([^\"]+)\"", block)
        info[fm.captures[1]] = fm.captures[2]
    end
    for fm in eachmatch(r"\"(argv_status)\"\s*:\s*\"([^\"]+)\"", block)
        info[fm.captures[1]] = fm.captures[2]
    end
    if occursin("\"reload\": true", block)
        info["reload"] = true
    end
    if occursin("\"native\": true", block)
        info["native"] = true
    end
    return info
end

function parse_deck_json(text::String)
    scenarios = Dict{String, Dict{String, Any}}()
    outer = match(r"(?s)\"scenarios\"\s*:\s*\{(.*)\}\s*\n\}", text)
    outer === nothing && return Dict{String, Any}("scenarios" => scenarios)
    body = outer.captures[1]
    idx = 1
    while idx <= length(body)
        m = match(r"\"([a-z0-9_]+)\"\s*:\s*\{", body, idx)
        m === nothing && break
        name = m.captures[1]
        start = m.offset + length(m.match)
        depth = 1
        pos = start
        while pos <= length(body) && depth > 0
            c = body[pos]
            if c == '{'
                depth += 1
            elseif c == '}'
                depth -= 1
            end
            pos += 1
        end
        block = String(body[start:pos-2])
        idx = pos
        parsed = parse_scenario_block(block)
        haskey(parsed, "generation") || continue
        scenarios[name] = parsed
    end
    return Dict{String, Any}("scenarios" => scenarios)
end

function write_report_json(path::String, digest::String, rows::Vector{Dict{String, Any}})
    open(path, "w") do io
        println(io, "{")
        println(io, "  \"cache_digest\": \"", digest, "\",")
        println(io, "  \"rows\": [")
        for (i, r) in enumerate(rows)
            trail = i < length(rows) ? "," : ""
            println(
                io,
                "    {\"scenario\": \"", r["scenario"],
                "\", \"view\": \"", r["view"],
                "\", \"key\": \"", r["key"],
                "\", \"generation\": ", r["generation"],
                ", \"hash_count\": ", r["hash_count"], "}", trail,
            )
        end
        println(io, "  ]")
        println(io, "}")
    end
end
