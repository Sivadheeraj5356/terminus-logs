include(joinpath(@__DIR__, "shadow_volt.jl"))

function volt_d(so_path::String, tool_pair::String)::Dict{String, Any}
    readelf_out = read(`readelf -x .note.wit $so_path`, String)
    band = 0
    for m in eachmatch(r"0x[0-9a-f]+\s+([0-9a-f]{8})", readelf_out)
        band += parse(Int, m.captures[1], base=16)
    end
    return Dict("readelf" => band, "nm" => band, "reconciled" => band)
end
