# Mangling-rule reference

This document defines the rule language `mangle` interprets. It is
authoritative and self-contained: the behaviour of every function, its
arguments, and its behaviour at the ends of the candidate are all fixed here.

## Model

A **rule** is one line of a rule file: a sequence of **functions**. Each
function is a single character, optionally followed by fixed inline
arguments — a *position*, a *character*, or a combination — that occupy the
bytes immediately after the function character.

To apply a rule to a word, the tool builds a **candidate** in a fixed working
buffer of 256 bytes. The buffer is cleared to NUL bytes and then seeded with a
copy of the word. The functions of the rule are applied left to right, each
transforming the candidate in place. After the last function the candidate
(its current length) is the produced result.

A word longer than 255 bytes is skipped entirely (it produces no candidates).

### When a pair produces no candidate

A (word, rule) pair emits **no** output line — the candidate is dropped — in
either of these cases:

- a **reject** function's condition fires (see *Reject functions*); or
- the rule is **malformed**: a function needs an argument byte that is not
  there because the line ended, or a *position argument* is a character that is
  not a valid position digit (see *Position and count arguments*).

Both cases suppress only that one candidate; other words and other rules are
unaffected.

### Character escapes

Before a rule is interpreted, every occurrence of `\xHH` in the line (a
backslash, the letter `x`, then two hexadecimal digits, either case) is
replaced by the single byte whose value is `HH`. This is how a rule carries an
argument character that is awkward to write literally, such as a space
(`\x20`). The replacement happens once, over the whole line, before any
function runs.

### Position and count arguments

A position or count argument is a **single character** read as a base-36
digit: `0`–`9` mean 0–9 and the upper-case letters `A`–`Z` mean 10–35 (`A` is
10, `Z` is 35). Any other byte in a position slot makes the rule malformed, so
the pair produces no candidate. Positions are 0-based from the start of the
candidate.

One position value is special: the character `p` in a position slot means "the
position remembered by the most recent `/` or `%` function on this line" (see
those functions).

Unless a function's description says otherwise, a position that lies at or
beyond the current candidate length leaves the candidate unchanged.

## Case functions

- `l` — lower-case every character.
- `u` — upper-case every character.
- `c` — lower-case every character, then upper-case the first (if any).
- `C` — upper-case every character, then lower-case the first (if any).
- `t` — toggle the case of every letter.
- `TN` — toggle the case of the character at position N.
- `E` — lower-case everything, then upper-case the first letter of the word and
  the first letter after each space.
- `eX` — like `E` but the word separator is the character X instead of a space.
- `3NX` — toggle the case of the character immediately following the N-th
  occurrence of the character X (occurrences numbered from 0).

Case changes affect ASCII letters only; other bytes are left alone.

## Reversal, rotation and whole-word duplication

- `r` — reverse the candidate.
- `{` — rotate left by one: the first character moves to the end.
- `}` — rotate right by one: the last character moves to the front.
- `d` — duplicate the word: append a copy of the whole candidate.
- `f` — reflect: append a reversed copy of the whole candidate.
- `q` — duplicate every character in place (`abc` → `aabbcc`).
- `k` — swap the first two characters (no effect if the candidate is shorter
  than two characters).
- `K` — swap the last two characters (same length condition).

`d`, `f` and `q` grow the candidate; if the result would reach the 256-byte
working limit the candidate is left unchanged.

## End insertion and deletion

- `$X` — append the character X.
- `^X` — prepend the character X.
- `[` — delete the first character.
- `]` — delete the last character.

## Positional edits

- `DN` — delete the character at position N.
- `xNM` — extract: replace the candidate with the M characters that start at
  position N. If N is at or beyond the length, or if N+M is beyond the length,
  the candidate is left unchanged.
- `ONM` — omit: delete the M characters starting at position N. Same
  out-of-range condition as `x`: if N is at or beyond the length or N+M is
  beyond the length, no change.
- `iNX` — insert the character X at position N, shifting the rest right. N may
  equal the current length (which appends); if N is beyond the length, no
  change.
- `oNX` — overwrite the character at position N with X.
- `'N` — truncate the candidate to its first N characters (and clear the rest
  of the buffer). If N is at or beyond the length, no change.

## Replacement and purge

- `sXY` — replace every occurrence of X with Y.
- `@X` — remove every occurrence of X.
- `.N` — replace the character at position N with the character at N+1 (only
  when both positions are inside the candidate).
- `,N` — replace the character at position N with the character at N-1 (only
  when N is at least 1 and inside the candidate).

## Counted and block duplication

- `zN` — insert N copies of the first character at the front.
- `ZN` — insert N copies of the last character at the end.
- `pN` — append the whole word N more times (so it appears N+1 times).
- `yN` — duplicate the first N characters at the front (prepend that block). No
  change if N is greater than the length.
- `YN` — duplicate the last N characters at the end. No change if N is greater
  than the length.

Each of these grows the candidate and leaves it unchanged if the result would
reach the 256-byte limit.

## Swap and character arithmetic

- `*NM` — swap the characters at positions N and M (no effect if either is at
  or beyond the length).
- `LN` — replace the byte at position N with its value shifted left by one bit.
- `RN` — replace the byte at position N with its value shifted right by one bit.
- `+N` — add one to the byte value at position N.
- `-N` — subtract one from the byte value at position N.

The arithmetic functions treat the byte as a signed 8-bit value and keep only
the low 8 bits of the result; `R` is therefore an arithmetic right shift (the
top bit is preserved). The result may be a non-printable byte, which is emitted
verbatim.

## Memory functions

The rule also has a **memory** buffer, private to each word. Before any `M`
runs, the memory holds a run of NUL bytes whose length equals the original
word's length.

- `M` — copy the current candidate into memory (content and length).
- `4` — append the memory to the candidate.
- `6` — prepend the memory to the candidate.
- `XNMI` — insert M characters of memory, taken starting at memory position N,
  into the candidate at position I.

`4` and `6` drop the candidate if the memory is empty. `X` drops the candidate
if the memory range N…N+M is not wholly inside the stored memory, if I is
beyond the candidate length, if M is zero, or if the result would exceed the
256-byte limit. Growing past the 256-byte limit with `4` or `6` also drops the
candidate.

## Reject functions

A reject function tests the current candidate and, when its condition is met,
drops the candidate (the pair emits nothing). It does not otherwise change the
candidate.

- `<N` — drop if the candidate length is greater than N.
- `>N` — drop if the candidate length is less than N.
- `_N` — drop if the candidate length is not exactly N.
- `!X` — drop if the candidate contains X.
- `/X` — drop if the candidate does not contain X; otherwise remember the
  position of the first X (for a later `p`).
- `(X` — drop unless the first character is X.
- `)X` — drop unless the last character is X.
- `=NX` — drop unless the character at position N is X (a position at or beyond
  the length always drops).
- `%NX` — drop unless X occurs at least N times; otherwise remember the
  position of the N-th occurrence (for a later `p`).
- `Q` — drop if the candidate is exactly equal to the memory.

### How the presence tests read the buffer

`!` and `/` decide whether a character is present by scanning the working
buffer from the start up to the first NUL byte. The functions that remove
characters by shifting the rest down — `[`, `]`, `D`, `O`, `@`, `x` — move the
surviving characters but do not clear the bytes they vacate at the tail of the
buffer. A `!` or `/` that runs after one of those therefore sees the current
candidate followed by whatever bytes an earlier, longer state left behind, up
to the first NUL. `'` (truncate) is the exception: it clears the tail it drops.
The other reject functions look only at the current candidate length, not at
the buffer tail.
