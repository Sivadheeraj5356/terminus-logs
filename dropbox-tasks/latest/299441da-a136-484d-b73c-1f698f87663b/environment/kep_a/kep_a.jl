include(joinpath(@__DIR__, "shadow_kep.jl"))

function kep_a(tier_path::String, reload_flag::Int)::Dict{String, Any}
    lines = split(read(tier_path, String), '\n')
    token = ""
    for ln in lines
        if occursin("workspace:", ln)
            token = "ws_alpha"
        end
    end
    return Dict("effective" => token, "reload" => reload_flag > 0)
end
