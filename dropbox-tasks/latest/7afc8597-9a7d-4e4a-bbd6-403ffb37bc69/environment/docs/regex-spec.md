## rsx regex subset and engine contract

This document defines the exact regex grammar that `rsx` accepts, the byte
alphabet it operates over, the canonical DFA description format emitted by
`rsx compile`, and the match semantics used by `rsx scan`. Anything not
described here is out of scope and must be rejected.

### Alphabet

The engine operates on raw bytes. The input alphabet is the 256 byte values
`0x00..=0xFF`. A pattern is itself a UTF-8 string, but the symbols a pattern
matches are single bytes. Patterns therefore match byte sequences, and all
offsets reported by `rsx scan` are byte offsets.

### Grammar

A pattern is parsed according to the following grammar. `|` denotes
alternation in the grammar meta-language, parentheses group meta-language
constructs, and a trailing `*` in the meta-language means zero or more.

```
regex      = alternation
alternation= concat ( '|' concat )*
concat     = repeat*
repeat     = atom ( '*' | '+' | '?' | counted )*
counted    = '{' number '}' | '{' number ',' '}' | '{' number ',' number '}'
atom       = group | class | dot | anchor | literal
group      = '(' alternation ')'
class      = '[' classbody ']'
dot        = '.'
anchor     = '^' | '$'
literal    = byte that is not a metacharacter, or an escape
```

An empty `concat` (zero repeats) matches the empty string. An empty
alternation branch (e.g. `a|`) is allowed and the empty branch matches the
empty string. An empty whole pattern (`""`) is valid and matches only the
empty string.

### Metacharacters and escapes

The metacharacters are: `. ^ $ * + ? ( ) [ ] { } | \`. Outside a character
class, a metacharacter must be escaped with `\` to be used as a literal, and
escaping a metacharacter is always valid: outside a class, a backslash followed
by any one of the metacharacters `. ^ $ * + ? ( ) [ ] { } | \` produces that
literal metacharacter byte. For example `\.` matches a literal dot byte `0x2E`,
`\*` a literal `*` (0x2A), `\+` a literal `+`, `\(` a literal `(`, `\|` a
literal `|`, and `\\` a literal backslash `0x5C`; the same holds for every
metacharacter in the list.

The following escapes are recognised everywhere (outside and inside classes):

```
\n  byte 0x0A      \t  byte 0x09      \r  byte 0x0D
\f  byte 0x0C      \v  byte 0x0B      \0  byte 0x00
\\  byte 0x5C      \xHH  the byte with two-hex-digit value HH
```

Outside a character class the metacharacter escapes `\. \^ \$ \* \+ \? \( \)
\[ \] \{ \} \|` are recognised in addition to the list above, each producing
its literal metacharacter byte. Inside a character class the additional escapes
`\] \^ \- \\` produce the literal bytes `] ^ - \` (the plain metacharacters such
as `.` or `*` are already literal inside a class and are not escaped there). Any
escape sequence not covered above — a backslash followed by a byte that is
neither a recognised control/`\x` escape nor, in its context, a valid
metacharacter escape — is a parse error. `.` matches any single byte except the
newline byte `0x0A`.

### Character classes

A class `[ ... ]` matches exactly one byte from the set it denotes. An empty
class `[]` is permitted and denotes the empty set, so it matches no byte and
makes the whole pattern accept nothing. A leading
`^` immediately after `[` negates the class: the negated class matches any
single byte (all 256 values, including `0x0A`) that is NOT in the denoted set.

Inside a class body the following items may appear, concatenated in any order:

- a single byte (literal or escape), which adds that byte to the set;
- a range `a-z`, where the low and high endpoints are single bytes (literal or
  escape) and the low byte value must be `<=` the high byte value; the range
  adds every byte in `[low, high]` inclusive;
- a named POSIX-style set written `[[:name:]]`, which adds the bytes of that
  named set (see below);
- a class subtraction operator `--` followed by a nested class `[ ... ]`; the
  operator removes the bytes of the nested class from the set accumulated so
  far in the current class body.
- a class intersection operator `&&` followed by a nested class `[ ... ]`; the
  operator keeps only the bytes that are in BOTH the set accumulated so far in
  the current class body AND the nested class (it removes every byte not in the
  nested class). A single `&` that is not part of a `&&` immediately followed by
  `[` is an ordinary literal `&` byte, exactly as a single `-` outside a range
  is a literal hyphen; likewise a `&&` not followed by `[` is two literal `&`
  bytes.

Named sets (the only names accepted; any other name is a parse error):

```
[[:digit:]]    0x30..=0x39
[[:lower:]]    0x61..=0x7A
[[:upper:]]    0x41..=0x5A
[[:alpha:]]    lower + upper
[[:alnum:]]    alpha + digit
[[:space:]]    0x09 0x0A 0x0B 0x0C 0x0D 0x20
[[:hexdigit:]] digit + 0x41..=0x46 + 0x61..=0x66
[[:punct:]]    0x21..=0x2F + 0x3A..=0x40 + 0x5B..=0x60 + 0x7B..=0x7E
```

A class body is evaluated strictly left to right, one item at a time, over a
running byte set that starts empty. Each item mutates that running set in the
order written: a byte or range or named set unions its bytes into the running
set; a `--[ ... ]` subtracts the operand's bytes from the running set as it
currently stands; a `&&[ ... ]` intersects the running set as it currently
stands with the operand's bytes. The two operators `--` and `&&` have no
precedence relative to one another or to plain additions — they are applied in
exactly the position they appear. In particular an item written AFTER an
operator is applied on top of the operator's result: `[a-z--[a-c]abc]` first
removes `a b c` from `a-z` and then unions `a b c` back in, so it denotes all of
`a-z`; and `[abc--[b]d&&[c-e]]` evaluates as `{a,b,c}` minus `{b}` = `{a,c}`,
then union `d` = `{a,c,d}`, then intersect `{c,d,e}` = `{c,d}`. Each operator
binds to the entire running set on its left and to exactly the single nested
class on its right, and chained operators apply left to right: `[a-z--[aeiou]]`
is the consonants, `[[:alnum:]--[[:digit:]]--[_]]` is the alphabetic letters,
and `[a-z&&[m-z]&&[p-t]]` is `p-t`. The nested class operand of `--`/`&&` is
itself a full class body and may contain ranges, named sets, a leading `^`
negation, and further `--`/`&&` operators, all resolved recursively before the
operator is applied; thus `[a-z--[a-m--[a-f]]]` removes `a-m` minus `a-f`
(i.e. `g-m`) from `a-z`, leaving `a-f` and `n-z`.

Note that subtraction and intersection are only meaningful inside a class body:
the two bytes `--` that appear outside any class are simply two literal hyphen
bytes in a concatenation, so `[[:alnum:]]--[[:digit:]]` denotes an alnum byte,
then a hyphen, then a hyphen, then a digit byte. A `-` is a literal byte when it
is the first or last item of a class body, or when it is escaped; otherwise a
`-` between two endpoints forms a range, and a doubled `--` followed by `[` is
the subtraction operator. Negation with `^` is applied ONCE, AFTER the entire
class body (all additions, subtractions, and intersections) has been resolved:
so `[^a-z&&[a-m]]` first computes `a-z` intersect `a-m` = `a-m` and then negates,
matching every byte that is not in `a-m`. An empty class `[]` denotes the empty
set (matches no byte); its negation `[^]` denotes all 256 bytes.

### Counted repetition

`{m}` means exactly `m` copies. `{m,}` means `m` or more copies. `{m,n}` means
between `m` and `n` copies inclusive, and requires `m <= n`. The counts `m` and
`n` are decimal integers with `0 <= m` and `n <= 1024`. Counted repetition is
expanded into concatenation and optional copies before automaton construction,
so `a{2,4}` is equivalent to `aa(a(a)?)?` in terms of the language accepted.

### Anchors

`^` matches at the start of the input only. `$` matches at the end of the input
only. Anchors are zero-width. For `rsx compile`, anchors are encoded in the DFA
using two reserved pseudo-bytes appended to the alphabet, but they do not
appear in the canonical transition table because compile reports the structure
over the 256 real byte labels plus the two anchor labels `^` and `$` only when
the pattern uses them (see the canonical format). For the subset of patterns
used as scan patterns, anchors constrain where a match may begin or end in the
scanned input.

### rsx compile canonical DFA format

`rsx compile '<regex>'` parses the pattern, builds a Thompson NFA, performs
subset construction to a DFA over the byte alphabet, minimises the DFA with
Hopcroft's algorithm, and prints a canonical textual description to stdout. On
a parse error it prints nothing to stdout and exits with a nonzero status.

The DFA is made canonical by relabelling its states with a deterministic
breadth-first numbering: the start state is `0`; states are then numbered in
the order they are first reached by a BFS that, at each state, follows
outgoing transitions in ascending order of their (label, target-before-
relabel) key. Only reachable, non-dead states are kept: a dead state is a
non-accepting state from which no accepting state is reachable; all transitions
into the dead state are omitted. After minimisation every kept state that is
not the start may still be the target of transitions.

The start state is the single exception to dead-state pruning: it is always
retained and always numbered `0`, even when the pattern's language is empty and
the start state is therefore dead itself. As a result the state count is never
zero: the smallest possible output has exactly one state, a lone start state
`0` that is non-accepting and has no outgoing transitions. So an empty-language
pattern such as `[]` compiles to `states 1`, an `accept` line with nothing
after it, and a single state line `0:` with no transitions.

Transition labels are byte values. To keep the table compact and canonical,
the 256 outgoing byte transitions of a state are grouped: consecutive byte
values that go to the same target state are emitted as a single range. A range
is written as `lo-hi=>t` when `lo < hi` and `b=>t` when a single byte `b`. The
bytes are rendered as two-digit lowercase hex (e.g. `61` for `a`). Within one
state's line, ranges are sorted by `lo` ascending.

The exact output is:

```
states <N>
start 0
accept <space-separated ascending state ids, empty line content if none>
<for each state id 0..N-1, in ascending order:>
<id>: <range>;<range>;...
```

A state with no outgoing transitions prints `<id>:` followed by nothing after
the colon. There is a single trailing newline at the end of the output and no
blank lines. The `accept` line lists accepting state ids in ascending order
separated by single spaces; if there are no accepting states the line is
exactly `accept` with nothing after it.

The DFA recognises the anchored full-string language of the pattern: `rsx
compile` treats the pattern as if it must match the entire input string. That
is, leading `^` and trailing `$` in the pattern are dropped for the purpose of
compile (compile always reports the whole-string automaton), and the automaton
accepts exactly the set of byte strings the pattern can match end to end.

### rsx scan match semantics

`rsx scan --patterns <file> --input <file>` reads one pattern per non-empty
line of the patterns file (lines are raw pattern text; no surrounding quotes;
a trailing newline is stripped; blank lines are skipped). For each pattern it
finds all non-overlapping matches in the input using leftmost-longest (POSIX)
semantics:

- scanning proceeds left to right by candidate start offset;
- at the current start offset, among all matches that begin there, the longest
  one is selected (longest match wins, not the first alternative);
- if no match begins at the current offset, advance the start offset by one
  byte;
- after a match of length `L >= 1` is taken at offset `s`, scanning resumes at
  offset `s + L`;
- a zero-length match (length 0) at offset `s` is reported and then scanning
  advances by one byte to `s + 1` to guarantee progress.

A leading `^` anchor restricts matches to begin at offset 0; a trailing `$`
anchor restricts matches to end at the input length. Both may appear. Anchors
anywhere other than the very start or very end of a pattern are parse errors.

Matches are reported as half-open byte spans `[start, end)`.

### rsx scan output format

`rsx scan` prints a single canonical JSON object to stdout followed by one
trailing newline. The object has one key `"patterns"` whose value is an array
with one entry per input pattern, in the order the patterns appear in the
patterns file (blank lines skipped). Each entry is an object:

```
{"pattern": "<the raw pattern text>", "matches": [[s, e], ...]}
```

The matches array lists spans in ascending order of start offset. Object keys
appear in the fixed order `pattern` then `matches`. Every comma in the output
is written as `, ` — a comma followed by exactly one space — and there is no
other insignificant whitespace (no newlines or indentation). This single
spacing rule applies uniformly at every level: the two integers inside a span
array `[s, e]` are separated by `, `, consecutive spans inside a `matches`
array are separated by `, `, the two keys of an entry object are separated by
`, `, and consecutive entries in the top-level `patterns` array are separated
by `, `. Concretely the serialiser produces, for one entry:
`{"pattern": "<p>", "matches": [[s, e], [s, e]]}`, and the top-level wrapper is
`{"patterns": [<entry>, <entry>]}`. Pattern strings are
JSON-escaped: `"` becomes `\"`, `\` becomes `\\`, and bytes `<0x20` are escaped
as `\u00XX` (lowercase hex), all other bytes are emitted verbatim.

If a pattern fails to parse, `rsx scan` exits nonzero and prints nothing to
stdout.
