include(joinpath(@__DIR__, "shadow_molt.jl"))

function molt_b(raw::Vector{UInt8}, canon_mode::Int)::Vector{Dict{String, Any}}
    rows = Dict{String, Any}[]
    i = 1
    while i + 2 <= length(raw)
        rec_len = Int(raw[i]) + 256 * Int(raw[i + 1])
        i += 2
        rec_len < 2 && break
        chunk = raw[i:min(i + rec_len - 1, end)]
        i += rec_len
        length(chunk) < 2 && continue
        status = Int(chunk[1])
        hc = Int(chunk[2])
        key = String(chunk[3:end])
        push!(rows, Dict("status" => status, "hash_count" => hc, "key" => key))
    end
    return rows
end
