#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/julia/bin:/opt/verifier-venv/bin:/app/environment/tools:${PATH:-/usr/bin:/bin}"
JULIA_BIN="/usr/local/julia/bin/julia"
test -x "$JULIA_BIN"

cat > "/app/environment/kep_a/kep_a.jl" <<'EOF'
include(joinpath(@__DIR__, "shadow_kep.jl"))

function kep_a(tier_path::String, reload_flag::Int)::Dict{String, Any}
    deck = dirname(tier_path)
    if reload_flag > 0
        best_tier = 0
        best_token = ""
        for (tier, name) in ((1, "workspace_resp.rsp"), (2, "project_resp.rsp"), (3, "env_resp.rsp"))
            p = joinpath(deck, name)
            isfile(p) || continue
            tok = strip(read(p, String))
            isempty(tok) && continue
            if tier >= best_tier
                best_tier = tier
                best_token = tok
            end
        end
        return Dict("effective" => best_token, "tier" => best_tier,
            "scope_hash" => length(best_token) + best_tier, "reload" => true)
    end
    lines = split(read(tier_path, String), '\n')
    in_section = false
    best_tier = 0
    best_token = ""
    cur_tier = 0
    for ln in lines
        s = strip(ln)
        if startswith(s, "layers:")
            in_section = true; continue
        end
        if in_section && startswith(s, "reload:")
            break
        end
        !in_section && continue
        if occursin("tier:", s)
            cur_tier = parse(Int, strip(split(s, ':')[2]))
        elseif occursin("token:", s)
            tok = strip(split(s, ':')[2])
            if cur_tier >= best_tier
                best_tier = cur_tier
                best_token = tok
            end
        end
    end
    return Dict("effective" => best_token, "tier" => best_tier,
        "scope_hash" => length(best_token), "reload" => false)
end
EOF

cat > "/app/environment/bind_h/bind_h.jl" <<'EOF'
include(joinpath(@__DIR__, "shadow_bind.jl"))

function bind_h(argv_hc::Int, wrap_hc::Int, def_sum::Int, epoch::Int, scope_tier::Int, auth_lane::Int, frame_count::Int)::Int
    return (argv_hc * 7 + wrap_hc * 11 + def_sum + epoch * 13 + scope_tier * 3 + (auth_lane * 5) % 241 + (frame_count % 17) * 3) % 241
end
EOF

cat > "/app/environment/lane_g/lane_g.jl" <<'EOF'
include(joinpath(@__DIR__, "shadow_lane.jl"))

function lane_g(status_label::String)::Bool
    return strip(status_label) == "nominal"
end
EOF

cat > "/app/environment/auth_f/auth_f.jl" <<'EOF'
include(joinpath(@__DIR__, "shadow_auth.jl"))

function auth_f(argv_sum::Int, wrap_head::Int, epoch::Int)::Int
    return (argv_sum ⊻ wrap_head ⊻ (epoch * 31)) & 0xffff
end
EOF

cat > "/app/environment/molt_b/molt_b.jl" <<'EOF'
include(joinpath(@__DIR__, "shadow_molt.jl"))

function _argv_decode(raw::Vector{UInt8})::Vector{Dict{String, Any}}
    length(raw) < 4 && return Dict{String, Any}[]
    body = raw[1:end-4]
    rows_all = Dict{String, Any}[]
    i = 1
    while i + 1 < length(body)
        rec_len = Int(body[i]) + 256 * Int(body[i + 1])
        i += 2
        rec_len < 2 && break
        i + rec_len - 1 > length(body) && break
        chunk = body[i:i+rec_len-1]
        i += rec_len
        push!(rows_all, Dict("status" => Int(chunk[1]), "hash_count" => Int(chunk[2]), "key" => String(chunk[3:end])))
    end
    expect = UInt32((sum(Int(b) for b in body) + length(rows_all) * 17) & 0xffffffff)
    footer = UInt32(raw[end-3]) + UInt32(raw[end-2]) << 8 + UInt32(raw[end-1]) << 16 + UInt32(raw[end]) << 24
    expect != footer && return Dict{String, Any}[]
    return [r for r in rows_all if Int(r["status"]) in (1, 2)]
end

function _wrap_decode(raw::Vector{UInt8})::Vector{Dict{String, Any}}
    length(raw) < 7 && return Dict{String, Any}[]
    String(raw[1:4]) != "KQWH" && return Dict{String, Any}[]
    cnt = Int(raw[5]) + 256 * Int(raw[6])
    use_max = length(raw) >= 7 && (Int(raw[7]) & 1) == 1
    off = 8
    total = 0
    seen = false
    for _ in 1:cnt
        off > length(raw) && break
        hc = Int(raw[off])
        tlen = Int(raw[off + 1]) + 256 * Int(raw[off + 2])
        off += 3 + tlen
        if use_max
            total = seen ? max(total, hc) : hc
            seen = true
        else
            total += hc
        end
    end
    return [Dict{String, Any}("status" => 1, "hash_count" => total, "key" => "head")]
end

function molt_b(raw::Vector{UInt8}, canon_mode::Int)::Vector{Dict{String, Any}}
    canon_mode == 2 && return _wrap_decode(raw)
    return _argv_decode(raw)
end
EOF

cat > "/app/environment/rune_c/rune_c.jl" <<'EOF'
include(joinpath(@__DIR__, "shadow_rune.jl"))

function _eff(tick::Int, sentinel::Int, scaled::Bool)
    t = scaled ? tick ÷ 8 : tick
    if sentinel == 1 && t > 0
        t = t % 512
    end
    return t
end

function _canon(raw, off, cnt, scaled)
    rows = Dict{String, Any}[]
    for _ in 1:cnt
        off + 6 > length(raw) && break
        tick = Int(raw[off]) + 256 * Int(raw[off+1]) + 65536 * Int(raw[off+2]) + 16777216 * Int(raw[off+3])
        sentinel = Int(raw[off+4]); klen = Int(raw[off+5]); off += 6
        off + klen - 1 > length(raw) && break
        key = String(raw[off:off+klen-1]); off += klen
        push!(rows, Dict("tick"=>tick,"sentinel"=>sentinel,"key"=>key,"eff_tick"=>_eff(tick,sentinel,scaled)))
    end
    return rows
end

function _perm(raw, off, cnt, scaled)
    rows = Dict{String, Any}[]
    for _ in 1:cnt
        off + 2 > length(raw) && break
        sentinel = Int(raw[off]); klen = Int(raw[off+1]); off += 2
        off + klen - 1 > length(raw) && break
        key = String(raw[off:off+klen-1]); off += klen
        off + 3 > length(raw) && break
        tick = Int(raw[off]) + 256 * Int(raw[off+1]) + 65536 * Int(raw[off+2]) + 16777216 * Int(raw[off+3])
        off += 4
        push!(rows, Dict("tick"=>tick,"sentinel"=>sentinel,"key"=>key,"eff_tick"=>_eff(tick,sentinel,scaled)))
    end
    return rows
end

function rune_c(raw::Vector{UInt8}, canon_mode::Int)::Vector{Dict{String, Any}}
    length(raw) < 12 && return Dict{String, Any}[]
    String(raw[1:4]) != "KQDT" && return Dict{String, Any}[]
    flags = Int(raw[9]) + 256 * Int(raw[10])
    cnt = Int(raw[11]) + 256 * Int(raw[12])
    scaled = (flags & 2) == 2
    rows = (flags & 1) == 1 ? _perm(raw, 13, cnt, scaled) : _canon(raw, 13, cnt, scaled)
    total = isempty(rows) ? 0 : sum(Int(r["eff_tick"]) for r in rows)
    if total > 512 && !isempty(rows)
        scale = 512 / total
        for r in rows
            r["eff_tick"] = max(1, floor(Int, Int(r["eff_tick"]) * scale))
        end
    end
    if (flags & 4) == 4 && !isempty(rows)
        for r in rows
            r["eff_tick"] = max(1, Int(r["eff_tick"]) - 1)
        end
    end
    return rows
end
EOF

cat > "/app/environment/volt_d/volt_d.jl" <<'EOF'
include(joinpath(@__DIR__, "shadow_volt.jl"))

function volt_d(so_path::String, tool_pair::String)::Dict{String, Any}
    readelf_out = read(`readelf -x .note.wit $so_path`, String)
    readelf_band = 0
    for ln in split(readelf_out, '\n')
        m = match(r"0x[0-9a-f]+\s+((?:[0-9a-f]{8}\s*)+)", strip(ln))
        m === nothing && continue
        for wm in eachmatch(r"([0-9a-f]{8})", m.captures[1])
            word = wm.captures[1]
            for i in 1:2:8
                readelf_band += parse(Int, word[i:i+1], base=16)
            end
        end
    end
    nm_addr = 0
    for ln in split(read(`readelf -s $so_path`, String), '\n')
        occursin("kq_wit_export", ln) || continue
        m = match(r":\s+([0-9a-f]+)\s+\d+\s+OBJECT", ln)
        m === nothing && continue
        nm_addr = parse(Int, m.captures[1], base=16)
        break
    end
    nm_band = 0
    for ln in split(read(`readelf -x .data $so_path`, String), '\n')
        m = match(r"0x([0-9a-f]+)\s+(.*)$", strip(ln))
        m === nothing && continue
        base = parse(Int, m.captures[1], base=16)
        bytes = UInt8[]
        for wm in eachmatch(r"([0-9a-f]{8})", m.captures[2])
            word = wm.captures[1]
            for i in 1:2:8
                push!(bytes, parse(Int, word[i:i+1], base=16))
            end
        end
        if nm_addr >= base && nm_addr < base + length(bytes)
            off = nm_addr - base + 1
            nm_band = Int(bytes[off]) + Int(bytes[off+1]) << 8 + Int(bytes[off+2]) << 16 + Int(bytes[off+3]) << 24
        end
    end
    return Dict("readelf" => readelf_band, "nm" => nm_band, "reconciled" => (readelf_band + nm_band) ÷ 2)
end
EOF

cat > "/app/environment/zen_e/zen_e.jl" <<'EOF'
include(joinpath(@__DIR__, "shadow_zen.jl"))
using SHA

function _parse_frame(line::String)
    m = match(r"\"scenario\":\"([^\"]*)\".*\"generation\":(\d+).*\"kind\":\"([^\"]+)\".*\"key\":\"([^\"]*)\".*\"value\":(-?\d+).*\"flags\":(\d+)", line)
    m === nothing && return nothing
    return Dict(
        "scenario" => m.captures[1],
        "generation" => parse(Int, m.captures[2]),
        "kind" => m.captures[3],
        "key" => m.captures[4],
        "value" => parse(Int, m.captures[5]),
        "flags" => parse(Int, m.captures[6]),
    )
end

function zen_e(frames_path::String, sentinel_mode::Int)::Dict{String, Any}
    auth_lane = 0
    if isfile("/app/output/kq_auth.bin")
        raw = read("/app/output/kq_auth.bin")
        length(raw) >= 2 && (auth_lane = Int(raw[1]) + Int(raw[2]) << 8)
    end
    frames = Dict{String, Any}[]
    for ln in eachline(frames_path)
        isempty(strip(ln)) && continue
        fr = _parse_frame(ln)
        fr === nothing && continue
        push!(frames, fr)
    end
    epoch = 0
    for fr in frames
        if fr["scenario"] == "_meta" && fr["kind"] == "epoch"
            epoch = Int(fr["value"])
        end
    end
    by = Dict{String, Vector{Dict{String, Any}}}()
    for fr in frames
        fr["scenario"] == "_meta" && continue
        push!(get!(by, string(fr["scenario"]), Dict{String, Any}[]), fr)
    end
    frame_count = count(fr -> string(fr["scenario"]) != "_meta", frames)
    rows = Dict{String, Any}[]
    stage_extra = Dict{String, Any}[]
    for (scen, frs) in by
        if scen == "control_empty"
            gen = Int(frs[1]["generation"])
            for fr in frs
                string(fr["kind"]) == "wrap" &&
                    push!(stage_extra, Dict("scenario"=>scen,"view"=>"wrapper_hash_bin","key"=>string(fr["key"]),
                        "generation"=>gen,"hash_count"=>Int(fr["value"])))
            end
            continue
        end
        gen = Int(frs[1]["generation"])
        argv_hc = 0
        wrap_hc = 0
        def_sum = 0
        scope_tier = 0
        for fr in frs
            kind = string(fr["kind"])
            if kind == "scope"
                scope_tier = Int(fr["flags"])
                push!(rows, Dict("scenario"=>scen,"view"=>"scope","key"=>string(fr["key"]),
                    "generation"=>gen,"hash_count"=>Int(fr["value"])))
            elseif kind == "argv"
                argv_hc += Int(fr["value"])
                Int(fr["flags"]) == 1 &&
                    push!(rows, Dict("scenario"=>scen,"view"=>"argv_text","key"=>string(fr["key"]),
                        "generation"=>gen,"hash_count"=>Int(fr["value"])))
            elseif kind == "define"
                def_sum += Int(fr["value"])
                push!(rows, Dict("scenario"=>scen,"view"=>"define_trace","key"=>string(fr["key"]),
                    "generation"=>gen,"hash_count"=>Int(fr["value"])))
            elseif kind == "wrap"
                wrap_hc += Int(fr["value"])
                push!(rows, Dict("scenario"=>scen,"view"=>"wrapper_hash_bin","key"=>string(fr["key"]),
                    "generation"=>gen,"hash_count"=>Int(fr["value"])))
            elseif kind == "native"
                push!(rows, Dict("scenario"=>scen,"view"=>"witness","key"=>string(fr["key"]),
                    "generation"=>gen,"hash_count"=>Int(fr["value"])))
            end
        end
        push!(rows, Dict("scenario"=>scen,"view"=>"ledger_bind","key"=>"bind",
            "generation"=>gen,"hash_count"=>bind_h(argv_hc, wrap_hc, def_sum, epoch, scope_tier, auth_lane, frame_count)))
        has_native = any(fr -> string(fr["kind"]) == "native", frs)
        if !has_native && argv_hc != wrap_hc && wrap_hc > 0
            total = argv_hc + wrap_hc
            avg = (total + (total % 2)) ÷ 2
            push!(rows, Dict("scenario"=>scen,"view"=>"witness","key"=>"band_reconcile",
                "generation"=>gen,"hash_count"=>avg))
        end
    end
    mkpath("/app/output")
    staged_rows = vcat(rows, stage_extra)
    open("/app/output/kq_stage.ndjson", "w") do io
        for r in staged_rows
            println(io, string(r["scenario"], ",", r["view"], ",", r["key"], ",", r["generation"], ",", r["hash_count"]))
        end
    end
    staged = readlines("/app/output/kq_stage.ndjson")
    sort!(staged)
    body = join(staged, '\n') * '\n'
    return Dict("cache_digest" => bytes2hex(sha256(Vector{UInt8}(codeunits(body)))), "rows" => rows)
end
EOF

"$JULIA_BIN" "/app/environment/src/kq_handler.jl" --deck "/app/environment/deck_p/s0" --out /app/output/kq_report.json
test -s /app/output/kq_report.json
test -s /app/output/kq_frames.ndjson
test -s /app/output/kq_stage.ndjson
