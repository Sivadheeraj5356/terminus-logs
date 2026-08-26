Each challenge in a batch fixes a modulus `n` and publishes a list of rows, each
row a triple `(e, f, c)`. Behind every challenge sit two secret integers, a
message `m` and a mask base `s`, and a row that is authentic satisfies
`c = m^e * s^f (mod n)`. Not every published row is guaranteed to be authentic,
the published values are not guaranteed to be written in canonical form, and
neither `s`, nor the factorization of `n`, nor which rows are authentic is ever
given; there is no decryption oracle. The message of a challenge is exactly `L`
bytes big-endian, `L` is published with the challenge, and the first two bytes of
that encoding are always `0xCA 0xFE`; the authentic rows together with that fixed
header pin down `m` uniquely. The row count, the exponents, the arithmetic
structure those exponents carry, and the modulus size all change from challenge
to challenge and are redrawn for the graded batch. Recover the exact `m` for
every challenge.

Implement your solution in `/app/environment/attack/main.jl` (Julia, standard
library only -- no packages are available or needed, and `Base`'s big-integer
arithmetic is enough). It reads an input file and writes an output file exactly
as `/app/environment/docs/io_contract.md` specifies.
`/app/environment/samples/practice_challenges.txt` holds practice challenges in
the graded input format. No answers ship with them, nothing on this host tells
you which rows of a challenge are authentic, and no ground truth of any kind is
available to you.
`python3 /app/environment/samples/local_check.py julia /app/environment/attack/main.jl`
checks only that your output is well formed and does not check correctness.
Grading reruns your source on fresh hidden challenges under new keys, and every
recovery must be exact.
