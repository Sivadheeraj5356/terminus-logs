include(joinpath(@__DIR__, "shadow_lane.jl"))

function lane_g(status_label::String)::Bool
    return !isempty(strip(status_label))
end
