#!/usr/bin/env julia
include(joinpath(@__DIR__, "kq_json.jl"))
include(joinpath(@__DIR__, "KqHandler.jl"))
using .KqHandler

function load_denylist()::Tuple{Set{String}, Int}
    if !haskey(ENV, "KQ_DENYLIST") || !isfile(ENV["KQ_DENYLIST"])
        return Set{String}(), 0
    end
    text = replace(read(ENV["KQ_DENYLIST"], String), r"\s+" => "")
    out = Set{String}()
    m = match(r"\"blocked_keys\":\[([^\]]*)\]", text)
    if m !== nothing
        for km in eachmatch(r"\"([^\"]+)\"", m.captures[1])
            push!(out, km.captures[1])
        end
    end
    width = 0
    wm = match(r"\"required_width\":(\d+)", text)
    wm !== nothing && (width = parse(Int, wm.captures[1]))
    return out, width
end

function parse_args_cli()
    deck = "/app/environment/deck_p/s0"
    out = "/app/output/kq_report.json"
    reload = false
    i = 1
    while i <= length(ARGS)
        if ARGS[i] == "--deck" && i < length(ARGS)
            deck = ARGS[i + 1]
            i += 2
        elseif ARGS[i] == "--out" && i < length(ARGS)
            out = ARGS[i + 1]
            i += 2
        elseif ARGS[i] == "--reload"
            reload = true
            i += 1
        else
            i += 1
        end
    end
    return deck, out, reload
end

function load_bytes(deck::String, scen::Dict, field::String, env_key::String, default_name::String)
    if haskey(ENV, env_key) && isfile(ENV[env_key])
        return read(ENV[env_key])
    end
    hx = get(scen, field * "_hex", "")
    !isempty(hx) && return hex2bytes(hx)
    name = get(scen, field, default_name)
    path = joinpath(deck, name)
    isfile(path) && return read(path)
    return UInt8[]
end

function json_escape(s::String)
    replace(replace(s, "\\" => "\\\\"), "\"" => "\\\"")
end

function write_frame(io, scen::String, gen::Int, kind::String, key::String, value::Int, flags::Int=0)
    println(io,
        "{\"scenario\":\"", json_escape(scen),
        "\",\"generation\":", gen,
        ",\"kind\":\"", kind,
        "\",\"key\":\"", json_escape(key),
        "\",\"value\":", value,
        ",\"flags\":", flags, "}")
end

function ingest_frames(deck::String, deck_obj::Dict, reload_cli::Bool, frames_path::String)
    mkpath(dirname(frames_path))
    rank_path = joinpath(deck, "rank_s0.yml")
    policy_layers = kep_a(rank_path, 0)
    policy_reload = kep_a(rank_path, 1)
    wit_path = "/app/environment/wit_q/libkq_wit.so"
    epoch_path = joinpath(deck, "epoch.txt")
    epoch = isfile(epoch_path) ? parse(Int, strip(read(epoch_path, String))) : 0

    deny, deny_width = load_denylist()
    argv_auth_base = 0
    wrap_auth_base = 0
    open(frames_path, "w") do io
        write_frame(io, "_meta", 0, "epoch", "deck", epoch, 0)
        for (scen, info) in deck_obj["scenarios"]
            gen = Int(info["generation"])
            use_reload = reload_cli || get(info, "reload", false) === true
            policy = use_reload ? policy_reload : policy_layers
            write_frame(io, scen, gen, "scope", "tier",
                Int(get(policy, "scope_hash", length(string(get(policy, "effective", ""))))),
                Int(get(policy, "tier", 0)))

            argv_raw = load_bytes(deck, info, "argv_wire", "KQ_ARGV_WIRE", "argv_wire.bin")
            apply_deny = deny_width == 0 || length(argv_raw) == deny_width
            status_label = string(get(info, "argv_status", "nominal"))
            if lane_g(status_label)
                for rec in molt_b(collect(argv_raw), 0)
                    status = Int(get(rec, "status", 0))
                    status == 0 && continue
                    key = string(rec["key"])
                    apply_deny && key in deny && continue
                    hc = Int(rec["hash_count"])
                    scen == "base_a" && (argv_auth_base += hc)
                    write_frame(io, scen, gen, "argv", key, hc, status)
                end
            end

            blob_name = get(ENV, "KQ_DEFINE_BLOB", get(info, "define_blob", "blob_s0.bin"))
            blob_path = isfile(blob_name) ? blob_name : joinpath(deck, blob_name)
            define_raw = isfile(blob_path) ? read(blob_path) : UInt8[]
            for rec in rune_c(collect(define_raw), 0)
                write_frame(io, scen, gen, "define", string(rec["key"]), Int(get(rec, "eff_tick", rec["tick"])), Int(get(rec, "sentinel", 0)))
            end

            wrap_raw = load_bytes(deck, info, "wrapper_hash", "KQ_WRAP_BIN", "wrapper_hash.bin")
            wrap_rows = molt_b(collect(wrap_raw), 2)
            wrap_hc = isempty(wrap_rows) ? 0 : Int(wrap_rows[1]["hash_count"])
            scen == "base_a" && (wrap_auth_base = wrap_hc)
            write_frame(io, scen, gen, "wrap", "head", wrap_hc, 0)

            if get(info, "native", false)
                bands = volt_d(wit_path, "readelf,nm")
                write_frame(io, scen, gen, "native", "band_reconcile", Int(bands["reconciled"]), 0)
            end
        end
        if get(ENV, "KQ_APPEND_CONTROL", "0") == "1"
            write_frame(io, "control_empty", 0, "wrap", "ctrl", 0, 0)
        end
    end
    auth_lane = auth_f(argv_auth_base, wrap_auth_base, epoch)
    open("/app/output/kq_auth.bin", "w") do io
        write(io, UInt8(auth_lane & 0xff), UInt8((auth_lane >> 8) & 0xff))
    end
end

function main()
    deck, out, reload_cli = parse_args_cli()
    deck_obj = parse_deck_json(read(joinpath(deck, "deck_s0.json"), String))
    frames = "/app/output/kq_frames.ndjson"
    ingest_frames(deck, deck_obj, reload_cli, frames)
    result = zen_e(frames, 0)
    mkpath(dirname(out))
    write_report_json(out, string(result["cache_digest"]), result["rows"])
end

main()
