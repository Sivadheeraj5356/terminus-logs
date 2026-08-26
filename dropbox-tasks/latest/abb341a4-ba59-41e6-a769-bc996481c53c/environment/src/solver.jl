# Exact continued fraction of a real algebraic number.
#
# The standard-input to standard-output harness below is complete. Implement the
# `compute` function so the program reports the six exact quantities defined in
# the task. All arithmetic must be exact: use Julia's Rational{BigInt} and BigInt
# and never let floating point affect a decision that changes the answer.

const RB = Rational{BigInt}

# Given the integer polynomial coefficients (c_0, c_1, ..., c_d), the 1-based
# index r of the target real root in increasing order, and the count k, return a
# NamedTuple with fields:
#   count::Int, quotients::Vector{BigInt}, numerators::Vector{BigInt},
#   denominators::Vector{BigInt}, terminated::Int, period::Int.
function compute(coeffs::Vector{BigInt}, r::Int, k::Int)
    error("compute is not implemented")
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
