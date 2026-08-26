# Exact continued fraction of a real algebraic number (reference implementation).
# Reads an integer polynomial, a 1-based real-root index r, and a count k from
# standard input; prints six lines: count, quotients, numerators, denominators,
# terminated, period. All arithmetic is exact (Rational{BigInt}); never floating.

const RB = Rational{BigInt}

pnorm(p::Vector{RB}) = (q = copy(p); while length(q) > 1 && q[end] == 0; pop!(q); end; q)
iszerop(p::Vector{RB}) = length(p) == 1 && p[1] == 0

function pderiv(p::Vector{RB})
    length(p) <= 1 && return RB[0]
    return RB[p[i] * (i - 1) for i in 2:length(p)]
end

function pdivmod(a::Vector{RB}, b::Vector{RB})
    a = pnorm(a); b = pnorm(b)
    (iszerop(a) || length(a) < length(b)) && return (RB[0], a)
    q = RB[0 for _ in 1:(length(a) - length(b) + 1)]
    r = copy(a)
    while !iszerop(pnorm(r)) && length(pnorm(r)) >= length(b)
        r = pnorm(r)
        d = length(r) - length(b)           # 0-based degree offset
        coef = r[end] / b[end]
        q[d + 1] = coef
        for i in 0:length(b) - 1
            r[d + i + 1] -= coef * b[i + 1]
        end
        r = pnorm(r)
    end
    return (pnorm(q), pnorm(r))
end

function pgcd(a::Vector{RB}, b::Vector{RB})
    a = pnorm(a); b = pnorm(b)
    while !iszerop(b)
        _, r = pdivmod(a, b)
        a, b = b, pnorm(r)
    end
    if a[end] != 0
        a = RB[x / a[end] for x in a]
    end
    return pnorm(a)
end

function to_int_primitive(p::Vector{RB})
    p = pnorm(p)
    l = BigInt(1)
    for c in p
        l = l * denominator(c) ÷ gcd(l, denominator(c))
    end
    ints = BigInt[numerator(c * l) for c in p]
    g = BigInt(0)
    for v in ints
        g = gcd(g, abs(v))
    end
    g == 0 && return BigInt[0]
    ints = BigInt[v ÷ g for v in ints]
    ints[end] < 0 && (ints = BigInt[-v for v in ints])
    return ints
end

itorb(v::Vector{BigInt}) = RB[RB(x) for x in v]

function squarefree(P::Vector{RB})
    P = pnorm(P)
    g = pgcd(P, pderiv(P))
    S, _ = pdivmod(P, g)
    return to_int_primitive(S)
end

function poly_eval_sign(p::Vector{BigInt}, x::RB)
    val = RB(0); xp = RB(1)
    for c in p
        val += c * xp
        xp *= x
    end
    return val > 0 ? 1 : (val < 0 ? -1 : 0)
end

gcd_int_poly(a::Vector{BigInt}, b::Vector{BigInt}) = to_int_primitive(pgcd(itorb(a), itorb(b)))
poly_deg(p::Vector{BigInt}) = length(to_int_primitive(itorb(p))) - 1  # length after norm - 1

function sturm_chain(S::Vector{BigInt})
    seq = Vector{RB}[pnorm(itorb(S)), pnorm(pderiv(itorb(S)))]
    while !iszerop(seq[end])
        _, r = pdivmod(seq[end - 1], seq[end])
        r = pnorm(r)
        iszerop(r) && break
        push!(seq, pnorm(RB[-x for x in r]))
    end
    return seq
end

function sign_changes(vals::Vector{RB})
    prev = 0; ch = 0
    for v in vals
        s = v > 0 ? 1 : (v < 0 ? -1 : 0)
        if s != 0
            if prev != 0 && s != prev
                ch += 1
            end
            prev = s
        end
    end
    return ch
end

function make_V(seq::Vector{Vector{RB}})
    return x -> sign_changes(RB[sum(RB[p[i] * x^(i - 1) for i in 1:length(p)]) for p in seq])
end

function cauchy_bound(S::Vector{BigInt})
    Sr = pnorm(itorb(S))
    lead = abs(Sr[end])
    m = RB(0)
    for i in 1:length(Sr) - 1
        m = max(m, abs(Sr[i]))
    end
    return 1 + m / lead
end

function rational_roots(S::Vector{BigInt})
    ints = to_int_primitive(itorb(S))
    roots = Set{RB}()
    if ints[1] == 0
        push!(roots, RB(0))
        k = 1
        while k <= length(ints) && ints[k] == 0
            k += 1
        end
        ints = ints[k:end]
    end
    isempty(ints) && return roots
    c0, cd = ints[1], ints[end]
    function divisors(n::BigInt)
        n = abs(n)
        n > BigInt(4000000000000000000) && return Set{BigInt}()
        ds = Set{BigInt}()
        i = BigInt(1)
        while i * i <= n
            if n % i == 0
                push!(ds, i); push!(ds, n ÷ i)
            end
            i += 1
        end
        return ds
    end
    for p in divisors(c0), q in divisors(cd)
        for cand in (RB(p, q), RB(-p, q))
            if poly_eval_sign(ints, cand) == 0
                push!(roots, cand)
            end
        end
    end
    return roots
end

# descriptor: (:rat, value) or (:irr, lo, hi)
function isolate_roots(S::Vector{BigInt})
    Sr = pnorm(itorb(S))
    ints = to_int_primitive(Sr)
    seq = sturm_chain(ints)
    V = make_V(seq)
    Bi = Int(ceil(cauchy_bound(ints))) + 1
    lo0, hi0 = RB(-Bi), RB(Bi)
    rroots = rational_roots(ints)
    function nonroot_mid(a, b)
        m = (a + b) / 2
        poly_eval_sign(ints, m) != 0 && return m
        step = (b - a) / 4
        for _ in 1:80
            m2 = m - step
            if a < m2 < b && poly_eval_sign(ints, m2) != 0
                return m2
            end
            step /= 2
        end
        return m
    end
    descs = Any[]
    stack = Any[(lo0, hi0, V(lo0) - V(hi0))]
    while !isempty(stack)
        a, b, cnt = pop!(stack)
        cnt == 0 && continue
        if cnt == 1
            rr = [r for r in rroots if a < r < b]
            push!(descs, isempty(rr) ? (:irr, a, b) : (:rat, rr[1]))
            continue
        end
        m = nonroot_mid(a, b)
        push!(stack, (a, m, V(a) - V(m)))
        push!(stack, (m, b, V(m) - V(b)))
    end
    keyf(d) = d[1] == :rat ? d[2] : (d[2] + d[3]) / 2
    sort!(descs, by = keyf)
    return descs
end

ffloor(x::RB) = fld(numerator(x), denominator(x))

function floor_and_refine(ints::Vector{BigInt}, lo::RB, hi::RB)
    while ffloor(lo) != ffloor(hi)
        m = (lo + hi) / 2
        if poly_eval_sign(ints, lo) * poly_eval_sign(ints, m) < 0
            hi = m
        else
            lo = m
        end
    end
    a = ffloor(lo)
    while !(lo > a && hi < a + 1)
        m = (lo + hi) / 2
        if poly_eval_sign(ints, lo) * poly_eval_sign(ints, m) < 0
            hi = m
        else
            lo = m
        end
    end
    return a, lo, hi
end

function taylor_shift(ints::Vector{BigInt}, a::BigInt)
    work = copy(ints)
    out = BigInt[]
    while !isempty(work)
        m = length(work)              # 1-based highest index
        tmp = BigInt[0 for _ in 1:length(work)]
        tmp[m] = work[m]
        for i in m - 1:-1:1
            tmp[i] = work[i] + a * tmp[i + 1]
        end
        push!(out, tmp[1])
        work = tmp[2:end]
    end
    return out
end

function reverse_poly(ints::Vector{BigInt})
    r = reverse(ints)
    while length(r) > 1 && r[end] == 0
        pop!(r)
    end
    return r
end

function reisolate_select(Q1::Vector{BigInt}, nlo::RB, nhi::RB)
    for d in isolate_roots(Q1)
        if d[1] == :rat
            nlo < d[2] < nhi && return (d[2], d[2])
            continue
        end
        _, clo, chi = d
        while true
            (clo >= nlo && chi <= nhi) && return (clo, chi)
            (chi <= nlo || clo >= nhi) && break
            m = (clo + chi) / 2
            if poly_eval_sign(Q1, clo) * poly_eval_sign(Q1, m) < 0
                chi = m
            else
                clo = m
            end
        end
    end
    return (nlo, nhi)
end

function eq_complete(QA::Vector{BigInt}, loA::RB, hiA::RB, QB::Vector{BigInt}, loB::RB, hiB::RB)
    jlo, jhi = max(loA, loB), min(hiA, hiB)
    jlo >= jhi && return false
    G = gcd_int_poly(QA, QB)
    poly_deg(G) < 1 && return false
    sa, sb = poly_eval_sign(G, jlo), poly_eval_sign(G, jhi)
    (sa == 0 || sb == 0) && return false
    return sa * sb < 0
end

function compute(coeffs::Vector{BigInt}, r::Int, k::Int)
    S = squarefree(itorb(coeffs))
    descs = isolate_roots(S)
    r > length(descs) && error("r exceeds number of real roots")
    alpha = descs[r]

    quotients = BigInt[]
    completes = Any[]
    term_flag = 0
    if alpha[1] == :rat
        x = alpha[2]
        terminated = false
        for _ in 1:k
            push!(completes, (:rat, x))
            a = ffloor(x)
            push!(quotients, a)
            frac = x - a
            if frac == 0
                terminated = true
                break
            end
            x = 1 // frac
        end
        term_flag = terminated ? 1 : 0
    else
        _, lo, hi = alpha
        Q = copy(S)
        for _ in 1:k
            push!(completes, (:irr, copy(Q), lo, hi))
            a, lo, hi = floor_and_refine(Q, lo, hi)
            push!(quotients, a)
            Qs = taylor_shift(Q, a)
            ylo, yhi = lo - a, hi - a
            Q = to_int_primitive(itorb(reverse_poly(Qs)))
            nlo, nhi = RB(1) / yhi, RB(1) / ylo
            lo, hi = reisolate_select(Q, nlo, nhi)
        end
        term_flag = 0
    end

    m = length(quotients)
    H = BigInt[]; K = BigInt[]
    h2, h1, k2, k1 = BigInt(0), BigInt(1), BigInt(1), BigInt(0)
    for a in quotients
        h = a * h1 + h2
        kk = a * k1 + k2
        push!(H, h); push!(K, kk)
        h2, h1, k2, k1 = h1, h, k1, kk
    end

    period = 0
    found = false
    for i in 1:m
        for j in 1:i - 1
            ci, cj = completes[i], completes[j]
            eq = false
            if ci[1] == :rat && cj[1] == :rat
                eq = ci[2] == cj[2]
            elseif ci[1] == :irr && cj[1] == :irr
                eq = eq_complete(ci[2], ci[3], ci[4], cj[2], cj[3], cj[4])
            end
            if eq
                period = i - j
                found = true
                break
            end
        end
        found && break
    end

    return (count = m, quotients = quotients, numerators = H,
            denominators = K, terminated = term_flag, period = period)
end

function main()
    toks = split(read(stdin, String))
    idx = 1
    d = parse(Int, toks[idx]); idx += 1
    coeffs = BigInt[parse(BigInt, toks[idx + i]) for i in 0:d]
    idx += d + 1
    r = parse(Int, toks[idx]); idx += 1
    k = parse(Int, toks[idx])
    res = compute(coeffs, r, k)
    println("count = ", res.count)
    println("quotients = ", join(string.(res.quotients), " "))
    println("numerators = ", join(string.(res.numerators), " "))
    println("denominators = ", join(string.(res.denominators), " "))
    println("terminated = ", res.terminated)
    println("period = ", res.period)
end

if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
