include(joinpath(@__DIR__, "shadow_frame.jl"))

function frame_h(kind::String, key::String, value::Int, flags::Int=0)::Bool
    return true
end
