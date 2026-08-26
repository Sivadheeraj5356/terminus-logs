# CIDR math

We do the address arithmetic ourselves with plain integers rather than leaning
on a library CIDR type, so the rules here are the contract. Everything is IPv4.

## Parsing an address

A dotted-quad `A.B.C.D` is exactly four decimal octets separated by dots. Each
octet is 0 to 255. Parse it into a 32-bit unsigned integer with the first octet
in the high byte:

    value = (A << 24) | (B << 16) | (C << 8) | D

So `192.168.1.10` is `0xC0A8010A`. Anything that is not four in-range octets is
not a valid address. No shorthand, no leading or trailing spaces.

## Parsing a block

A block is `A.B.C.D/P` where `P`, the prefix length, is an integer from 0 to 32.
The address part parses as above.

## The network mask

The mask for a prefix `P` is the 32-bit value with the top `P` bits set and the
rest clear:

- `P = 0` gives the all-zero mask, which matches every address.
- `P = 32` gives all ones, which matches exactly one host.
- otherwise the mask is `0xFFFFFFFF` shifted left by `32 - P` bits.

Watch the shift amount. The number of host bits is `32 - P`, and that is exactly
how far you shift a full mask of ones to the left. Shifting by one too many or
one too few silently widens or narrows every block and quietly changes both the
decisions and the shadowing analysis.

## Canonicalization

A block's canonical form clears its host bits: `base_canonical = base & mask(P)`.
So `10.5.5.5/8` canonicalizes to `10.0.0.0/8` and `192.168.1.128/25` is already
canonical. A block is already canonical when `base == (base & mask(P))`. Loaded
rules are stored and compared in canonical form, and the canonical block is what
the `normalized` note and the shadowing/redundancy analysis use. Two blocks are
equal when their canonical base and prefix are equal.

## Containment

An address `ip` is inside a block `(base, P)` when masking both sides gives the
same network number:

    (ip & mask(P)) == (base & mask(P))

`10.5.5.5` is inside `10.0.0.0/8`; `11.0.0.1` is not.

## Superset

Block X covers block Y (every address of Y is also in X) when X is no more
specific than Y and Y's base falls inside X:

    X.prefix <= Y.prefix  AND  X contains Y.base

This is what the shadowing analysis in `evaluation.md` uses, on both the source
and the destination block.
