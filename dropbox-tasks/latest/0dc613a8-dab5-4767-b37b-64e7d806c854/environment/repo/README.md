# mangle

`mangle` is a small offline command-line tool for expanding a password
candidate list. Given a list of *mangling rules* and a *wordlist*, it applies
every rule to every word and prints the resulting candidates, one per line. It
is the kind of transform stage a wordlist-based password auditor runs before
hashing: cheap, deterministic, and dependency-free.

## Build

```
make
```

produces the `mangle` binary. `make test` builds and runs the in-repo unit
checks.

## Usage

```
mangle <rulefile> <wordlist>
```

Each line of `<rulefile>` is one rule — a sequence of single-character
functions applied left to right (blank lines and lines starting with `#` are
ignored). Each line of `<wordlist>` is one word. For every word, each rule is
applied in turn and each surviving candidate is written to standard output
followed by a newline. Some rules *reject* a word, in which case that pair
produces no line.

```
$ printf 'l\nu\nc$1\n' > rules.txt
$ printf 'Passw0rd\n'  > words.txt
$ mangle rules.txt words.txt
passw0rd
PASSW0RD
Passw0rd1
```

## Layout

- `src/main.c`     — argument handling and the driver loop
- `src/wordio.c`   — rule/wordlist file readers
- `src/rules.c`    — the rule engine (`apply_rule`)
- `docs/rules.md`  — the authoritative rule reference
- `tests/unit.c`   — development unit checks
- `testdata/`      — example rule and word files
