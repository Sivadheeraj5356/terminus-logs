# I/O contract

Your program runs once:

```
julia main.jl <input_challenges.txt> <output_recovered.txt>
```

## The scheme

A challenge fixes a modulus `n` and two secret integers, a message `m` and a
mask base `s`. It publishes `n` and a list of `t` rows, each row a triple
`(e, f, c)`. A row is *authentic* when

```
c = m^e * s^f  (mod n)
```

Not every published row is guaranteed to be authentic. The value of a row is not
guaranteed to be written as the least nonnegative residue. `s`, the factorization
of `n`, and the identity of the authentic rows are never published, and no
decryption oracle exists.

`m`, `s`, `n`, `t`, the exponents, and the arithmetic structure the exponents
carry are drawn afresh for every challenge.

## The message

`m` is encoded as exactly `L` bytes big-endian, where `L` is published with the
challenge and `8*L` equals the bit length of `n`. The first two bytes of that
encoding are `0xCA` and `0xFE` for every challenge. The authentic rows of a
challenge together with that fixed header pin down exactly one `m`.

## Input

The first line is the challenge count `N`. Each of the following `N` lines is one
challenge:

```
<id> <n> <L> <t> <e_1> <f_1> <c_1> <e_2> <f_2> <c_2> ... <e_t> <f_t> <c_t>
```

`id` is a token, `L` and `t` are integers, and every other field is a decimal big
integer. The `t` rows appear in no particular order.

## Output

For each challenge, one line

```
<id> <hex>
```

where `<hex>` is the recovered `m` as exactly `L` bytes big-endian, so `2*L`
lowercase hex characters left-padded with zeros. Line order does not matter.

## What is graded

Only behavior. Your source is rerun on a fresh hidden batch of challenges under
new keys, and every challenge's line must equal the planted message exactly. A
recovery that is right for some challenges and wrong for others earns nothing.

## Practice, and the absence of ground truth

`/app/environment/samples/practice_challenges.txt` is a batch in exactly the
input format above. It ships with no answers, no indication of which rows are
authentic, and no labels of any kind, and there is no other source of ground
truth on this host.

`python3 /app/environment/samples/local_check.py julia /app/environment/attack/main.jl`
runs your solver over that batch and checks only that the output is well formed:
one line per challenge, the right ids, `2*L` lowercase hex characters, and the
required header. It cannot check correctness, and passing it means nothing beyond
well-formedness.

Offline, CPU-only. Julia standard library only.
