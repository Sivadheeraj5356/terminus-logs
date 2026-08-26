include(joinpath(@__DIR__, "shadow_rune.jl"))

function rune_c(raw::Vector{UInt8}, canon_mode::Int)::Vector{Dict{String, Any}}
    rows = Dict{String, Any}[]
    length(raw) < 12 && return rows
    magic = String(raw[1:4])
    magic != "KQDT" && return rows
    cnt = Int(raw[11]) + 256 * Int(raw[12])
    off = 13
    for _ in 1:cnt
        off + 6 > length(raw) && break
        tick = Int(raw[off]) + 256 * Int(raw[off + 1]) + 65536 * Int(raw[off + 2]) + 16777216 * Int(raw[off + 3])
        sentinel = Int(raw[off + 4])
        klen = Int(raw[off + 5])
        off += 6
        off + klen - 1 > length(raw) && break
        key = String(raw[off:off + klen - 1])
        off += klen
        push!(rows, Dict("tick" => tick, "sentinel" => sentinel, "key" => key))
    end
    return rows
end
