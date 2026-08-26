function shadow_volt_pretty(so_path::String)::String
    return read(`nm $so_path`, String)
end
