# Challenge contract

This file states every fact that is graded. Hidden challenges used for grading
follow exactly the same contract with fresh secret values.

## The generator

Each challenge is produced by one linear congruential generator. Starting from a
secret seed `X0`, it produces the sequence

```
X_{i+1} = (a * X_i + c) mod m
```

The modulus `m`, the multiplier `a`, and the increment `c` are all secret. The
modulus is exactly `width` bits wide, where `width` is a multiple of eight and is
given to you; that is, `2^(width-1) <= m < 2^width`. The multiplier `a` is never
equal to one. The increment `c` may be zero or nonzero. Every generator output
`X_i` therefore satisfies `0 <= X_i < m`.

## The challenge file

One challenge is one text file of `key=value` lines. The keys are:

- `width` — the modulus width in bits, a multiple of eight.
- `keystream_high_bytes` — a small positive integer `w`, at most `width / 8`.
- `outputs` — a comma separated list of consecutive decimal outputs
  `X0, X1, ..., X{k-1}` that the generator produced starting from its seed. These
  are full width values, not keystream. There are at least six of them.
- `ciphertext` — the encrypted message as lowercase hexadecimal, even length.

Whitespace around values is not significant. Any other line, a missing key, or a
malformed value makes the file invalid.

## How the message was encrypted

The keystream is taken from the generator outputs that come strictly after the
last published output. In other words, if the published run ends at `X{k-1}`, the
keystream is built from `X_k, X_{k+1}, X_{k+2}, ...`. The published outputs are
not part of the keystream.

From each such output `X_i` the encoder writes it as a big endian integer of
exactly `width / 8` bytes and takes the first `w` of those bytes, most
significant first. Concatenating these `w` byte groups across `X_k, X_{k+1}, ...`
gives the keystream. The keystream is used only up to the length of the message.

The ciphertext is the message XORed with that keystream, byte for byte.

## The message

The plaintext is printable ASCII. It begins with the five bytes `FLAG{` and ends
with the single byte `}`. Its length is not fixed across challenges.

## What your program prints

Your program receives the path to one challenge file as its single argument. On a
valid file it prints the recovered plaintext bytes on one line, followed by a
newline, and exits zero. On any invalid file it prints the single line `ERROR`
and exits one. Nothing else is printed; the recovered plaintext is compared byte
for byte.
