# Oracle for the masked-exponent recovery task. Published data only: the modulus
# and the (e, f, c) rows. A row may be written in a non-canonical residue class,
# a row's value may share a factor with the modulus, not every row is authentic,
# and the mask has to be cancelled by choosing fold coefficients that zero the f
# column -- which in general leaves only a power of the message, so roots are
# extracted over the factors and the disclosed header selects the lift.

const MAGIC = BigInt(0xCAFE)
const ROOT_ORDER_LIMIT = 100
const LIFT_LIMIT = 512

function egcd(a::BigInt, b::BigInt)
    old_r, r = a, b
    old_x, x = BigInt(1), BigInt(0)
    old_y, y = BigInt(0), BigInt(1)
    while r != 0
        q = fld(old_r, r)
        old_r, r = r, old_r - q * r
        old_x, x = x, old_x - q * x
        old_y, y = y, old_y - q * y
    end
    return old_r, old_x, old_y
end

function multi_bezout(vals::Vector{BigInt})
    g = vals[1]
    coeffs = BigInt[1]
    for i in 2:length(vals)
        g2, x, y = egcd(g, vals[i])
        coeffs = BigInt[c * x for c in coeffs]
        push!(coeffs, y)
        g = g2
    end
    return g, coeffs
end

signed_powmod(b, k, m) = k >= 0 ? powermod(b, k, m) : powermod(invmod(b, m), -k, m)

function fold(m, cs::Vector{BigInt}, a::Vector{BigInt})
    acc = BigInt(1)
    for i in 1:length(cs)
        acc = mod(acc * signed_powmod(cs[i], a[i], m), m)
    end
    return acc
end

# Minimal positive G and integer a with sum(a.*es) == G and sum(a.*fs) == 0.
# Eliminating the f column leaves rows spanning exactly the intersection of the
# row lattice with the e axis; the gcd of their e entries is that minimal G.
function lattice_solve(es::Vector{BigInt}, fs::Vector{BigInt})
    t = length(es)
    have_pivot = false
    pf = BigInt(0)
    pe = BigInt(0)
    pu = BigInt[]
    zero_e = BigInt[]
    zero_u = Vector{BigInt}[]
    for i in 1:t
        u = BigInt[j == i ? 1 : 0 for j in 1:t]
        f, e = fs[i], es[i]
        if f == 0
            push!(zero_e, e)
            push!(zero_u, u)
            continue
        end
        if !have_pivot
            have_pivot = true
            pf, pe, pu = f, e, u
            continue
        end
        g, x, y = egcd(pf, f)
        ka, kb = div(pf, g), div(f, g)
        push!(zero_e, -kb * pe + ka * e)
        push!(zero_u, BigInt[-kb * pu[j] + ka * u[j] for j in 1:t])
        pf, pe, pu = g, x * pe + y * e, BigInt[x * pu[j] + y * u[j] for j in 1:t]
    end
    isempty(zero_e) && return nothing
    g, coeffs = multi_bezout(zero_e)
    g == 0 && return nothing
    a = BigInt[0 for _ in 1:t]
    for k in 1:length(coeffs)
        for j in 1:t
            a[j] += coeffs[k] * zero_u[k][j]
        end
    end
    if g < 0
        g = -g
        a = BigInt[-v for v in a]
    end
    return (g, a)
end

function small_dlog(base, target, order, m)
    cur = BigInt(1)
    for x in 0:(order - 1)
        cur == target && return BigInt(x)
        cur = mod(cur * base, m)
    end
    error("no discrete log")
end

function nonresidue(r, q)
    z = BigInt(2)
    while powermod(z, div(q - 1, r), q) == 1
        z += 1
    end
    return z
end

# One r-th root of o modulo the prime q, r prime dividing q-1 to any
# multiplicity (Adleman-Manders-Miller).
function amm_root(o, r, q)
    n = q - 1
    s = n
    t = 0
    while mod(s, r) == 0
        s = div(s, r)
        t += 1
    end
    z = nonresidue(r, q)
    k = BigInt(1)
    while mod(k * s + 1, r) != 0
        k += 1
    end
    alp = div(k * s + 1, r)
    a = powermod(z, r^(t - 1) * s, q)
    b = powermod(o, r * alp - 1, q)
    c = powermod(z, s, q)
    h = BigInt(1)
    for i in 1:(t - 1)
        d = powermod(b, r^(t - 1 - i), q)
        j = d == 1 ? BigInt(0) : -small_dlog(a, d, r, q)
        b = mod(b * signed_powmod(powermod(c, r, q), j, q), q)
        h = mod(h * signed_powmod(c, j, q), q)
        c = powermod(c, r, q)
    end
    return mod(powermod(o, alp, q) * h, q)
end

function is_small_prime(d)
    d < 2 && return false
    i = BigInt(2)
    while i * i <= d
        mod(d, i) == 0 && return false
        i += 1
    end
    return true
end

# Every x in GF(F) with x^g == val. `nothing` means the case is declined.
function field_roots(val, g, F)
    val = mod(val, F)
    val == 0 && return BigInt[0]
    n = F - 1
    d = gcd(g, n)
    if d == 1
        return BigInt[powermod(val, invmod(mod(g, n), n), F)]
    end
    (d > ROOT_ORDER_LIMIT || !is_small_prime(d)) && return nothing
    powermod(val, div(n, d), F) != 1 && return BigInt[]
    _, x, _ = egcd(g, n)
    w = powermod(val, mod(x, n), F)
    x0 = amm_root(w, d, F)
    zeta = powermod(nonresidue(d, F), div(n, d), F)
    out = BigInt[]
    cur = x0
    for _ in 1:d
        push!(out, cur)
        cur = mod(cur * zeta, F)
    end
    return sort(unique(out))
end

function crt(r1, m1, r2, m2)
    _, s, _ = egcd(m1, m2)
    return mod(r1 + m1 * mod((r2 - r1) * s, m2), m1 * m2)
end

has_magic(x, L) = (0 <= x < (BigInt(1) << (8 * L))) && (x >> (8 * (L - 2))) == MAGIC

function find_factor(n, cs::Vector{BigInt})
    for c in cs
        c == 0 && continue
        g = gcd(c, n)
        (1 < g < n) && return g
    end
    return BigInt(0)
end

function subset_roots(F, cs::Vector{BigInt}, a::Vector{BigInt}, g)
    vals = BigInt[mod(c, F) for c in cs]
    all(v -> v == 0, vals) && return BigInt[0]
    any(v -> v == 0, vals) && return nothing
    return field_roots(fold(F, vals, a), g, F)
end

function recover(n, es::Vector{BigInt}, fs::Vector{BigInt}, craw::Vector{BigInt}, L)
    cs = BigInt[mod(c, n) for c in craw]
    p = find_factor(n, cs)
    t = length(es)
    counts = Dict{BigInt,Int}()
    bump(x) = counts[x] = get(counts, x, 0) + 1
    for mask in 1:((1 << t) - 1)
        idx = [i for i in 1:t if (mask >> (i - 1)) & 1 == 1]
        length(idx) < 2 && continue
        sol = lattice_solve(es[idx], fs[idx])
        sol === nothing && continue
        g, a = sol
        sub_c = cs[idx]
        if p == 0
            (g != 1 || any(c -> gcd(c, n) != 1, sub_c)) && continue
            bump(fold(n, sub_c, a))
            continue
        end
        q = div(n, p)
        rp = subset_roots(p, sub_c, a, g)
        rq = subset_roots(q, sub_c, a, g)
        (rp === nothing || rq === nothing) && continue
        (isempty(rp) || isempty(rq)) && continue
        length(rp) * length(rq) > LIFT_LIMIT && continue
        for u in rp, v in rq
            bump(crt(u, p, v, q))
        end
    end
    best = BigInt(-1)
    bestkey = (-1, BigInt(0))
    for (x, cnt) in counts
        has_magic(x, L) || continue
        k = (cnt, -x)
        if k > bestkey
            bestkey = k
            best = x
        end
    end
    return best < 0 ? BigInt(0) : best
end

function main()
    lines = readlines(ARGS[1])
    open(ARGS[2], "w") do io
        for line in lines[2:end]
            s = strip(line)
            isempty(s) && continue
            tok = split(s)
            length(tok) < 4 && continue
            id = tok[1]
            n = parse(BigInt, tok[2])
            L = parse(Int, tok[3])
            t = parse(Int, tok[4])
            length(tok) < 4 + 3 * t && continue
            es = BigInt[]
            fs = BigInt[]
            cs = BigInt[]
            for k in 0:(t - 1)
                push!(es, parse(BigInt, tok[5 + 3k]))
                push!(fs, parse(BigInt, tok[6 + 3k]))
                push!(cs, parse(BigInt, tok[7 + 3k]))
            end
            m = recover(n, es, fs, cs, L)
            println(io, "$id $(lpad(string(m, base = 16), 2L, '0'))")
        end
    end
end

main()
