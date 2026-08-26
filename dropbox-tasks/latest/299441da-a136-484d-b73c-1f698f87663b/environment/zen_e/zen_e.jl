include(joinpath(@__DIR__, "shadow_zen.jl"))

function zen_e(frames_path::String, sentinel_mode::Int)::Dict{String, Any}
    return Dict("cache_digest" => "0"^64, "rows" => Dict{String, Any}[])
end
