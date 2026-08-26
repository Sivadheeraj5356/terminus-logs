# bvm — bytecode VM and verifier: behavioural contract

This document defines the exact behaviour of the `bvm` command: the module text
format, the instruction set, the type system and its lattice, and the precise
result of every subcommand. It states *what* each subcommand must produce, not
how to compute it. Where a rule uniquely determines an output (a canonical form,
a typestate, a merge, a verification verdict), that output is fixed and must be
reproduced exactly, byte for byte.

Every invocation writes its result to standard output and exits 0 on success. A
missing `--module`/`--manifest`, an unreadable file, a structurally malformed
module, or an unknown function selector is an error: the command prints a short
message to standard error and exits 2. A *verification* verdict (a module that is
correctly rejected as ill-typed) is a normal result printed on stdout with exit 0,
not an error.

## Types

A value type is one of:

- `int`, `float`, `bool` — the primitives;
- `null` — the null reference (a value type only; not declarable);
- `ref NAME` — a reference to a declared struct type `NAME`;
- `arr ELEM` — an array whose elements have type `ELEM` (any value type,
  recursively, e.g. `arr int`, `arr ref Animal`, `arr arr int`);
- `void` — a function return type only.

An uninitialised local slot has the pseudo-type `uninit`.

**Struct hierarchy.** A `type` declaration introduces a struct with an optional
single parent and an optional brace-delimited field list:

```
type Animal { age: int }
type Dog extends Animal { bark: int }
```

Every struct implicitly descends from the root type `obj`. `S` is a
*descendant* of `T` (written `S <: T` for references) when `S` is `T`, or `T` is
`obj`, or `T` is reached by following `S`'s chain of parents. A struct's fields
are its own declared fields together with every field inherited from its
ancestors; a field name is looked up by walking from the struct up through its
ancestors.

**Subtyping (`<:`).** `S <: T` holds exactly when: `S` and `T` are identical;
or `S` is `null` and `T` is a `ref` type; or both are `ref` types and `S`'s
struct is a descendant of `T`'s struct. Primitives are subtypes only of
themselves. Arrays are **invariant**: `arr S <: arr T` only when `S` and `T` are
identical types.

**Least upper bound (join).** The lub of two stack-slot types is: the type
itself when they are equal; for two references (including `null`), the nearer
one when one is `null`, otherwise `ref A` where `A` is the **nearest common
ancestor** of the two structs in the hierarchy (which is `obj` only when they
share no nearer ancestor). Two types with no common type — for example `int`
with `float`, a primitive with a reference, or two arrays with different element
types — have **no lub**; a join that needs one is an error (see *verify*).

## Module text format

A module is a sequence of lines. `#` starts a comment running to end of line;
blank lines are ignored. Type declarations come first by convention but position
is not significant. A function is:

```
func NAME(T1, T2, ...) -> RET {
  locals K
LABEL:
  <instruction>
  ...
  <terminator>
LABEL:
  ...
}
```

The signature lists parameter types (possibly none) and a return type `RET`
(`void` or a value type). An optional `locals K` line declares `K` additional
local slots beyond the parameters. Local slots are numbered `0..N-1` where the
first `len(params)` slots are the parameters (initially holding their parameter
types) and the remaining `K` slots start `uninit`. A function has one or more
basic blocks, each introduced by a `LABEL:` line and containing a straight-line
list of instructions ending in exactly one terminator (`br`, `br_if`, or `ret`),
which must be the block's last instruction. The first block is the entry.

## Instruction set

Stacks are written with the top on the right. `T` is any value type unless
constrained. Each instruction's stack effect and type rule:

| opcode | effect | rule |
|---|---|---|
| `iconst K` | `-> int` | pushes int |
| `fconst X` | `-> float` | pushes float (literal keeps its written form) |
| `bconst B` | `-> bool` | `B` is `0` or `1` |
| `null` | `-> null` | pushes the null reference |
| `pop` | `T ->` | discards the top |
| `dup` | `T -> T, T` | duplicates the top |
| `swap` | `A, B -> B, A` | swaps the top two |
| `load N` | `-> T` | pushes local `N`; **error if local `N` is `uninit`** |
| `store N` | `T ->` | sets local `N`'s type to the popped type |
| `iadd`/`isub`/`imul` | `int, int -> int` | operands must be `int` |
| `fadd`/`fsub`/`fmul` | `float, float -> float` | operands must be `float` |
| `icmp` | `int, int -> bool` | pushes `bool` (less-than at run time) |
| `fcmp` | `float, float -> bool` | pushes `bool` |
| `and`/`or` | `bool, bool -> bool` | operands must be `bool` |
| `not` | `bool -> bool` | operand must be `bool` |
| `new T` | `-> ref T` | `T` a declared struct |
| `getfield T f` | `ref R -> F` | `R <: ref T`; `F` is the type of field `f` looked up on `T` (inherited fields included) |
| `putfield T f` | `ref R, V ->` | `R <: ref T`; `V <: F` where `F` is field `f`'s type |
| `newarray T` | `int -> arr T` | pops a length, pushes an array of element type `T` |
| `aload` | `arr T, int -> T` | pushes the element type |
| `astore` | `arr T, int, V ->` | requires `V <: T` |
| `call g` | `A1..An -> R` | pops `n` arguments (last on top); each `Ai <: param i`; pushes `g`'s return type unless `void` |
| `br L` | terminator | successor: `L` |
| `br_if L` | `bool ->`, terminator | pops a `bool`; successors: `L` then the fall-through block |
| `ret` | terminator | for `void`, the stack must be empty; otherwise pops one value `V <: RET` and the stack must then be empty |

`getfield`/`putfield` name the owning type explicitly; the receiver must be a
subtype of `ref T`. Argument, field-store, array-store and return values are all
checked against the target type with `<:` (so a subtype value is accepted where a
supertype is required, never the reverse).

## Control-flow graph — `cfg`

The successors of a block are: `[L]` for `br L`; `[L, F]` for `br_if L`, where
`F` is the textually next block (which must exist); and none for `ret`. `cfg
--module F --func NAME` (NAME defaults to `main`) prints:

```
entry: <entry label>
<label> -> <succ>, <succ>
<label> -> exit
```

one line per block in source order, successors in successor order, `-> exit`
when a block returns. A block reachable from the entry is *live*; others are
*dead*.

## Straight-line checks — `opcheck`, `stackmap`

`opcheck` and `stackmap` analyse the **entry block** of a function as
straight-line code starting from the entry state (empty stack; locals =
parameter types then `uninit` slots). They do **not** merge across blocks — that
is `verify`'s job. Both stop at the first type error.

`opcheck --module F --func NAME` prints, per instruction, `PC OP :: BEFORE =>
AFTER` where a stack is rendered `[int, ref Dog]` or `[]`; a clean run ends with
a line `ok`, a failing run ends with `type error at PC: <reason>`.

`stackmap --module F --func NAME` prints, before each instruction, `PC:
stack=STACK locals=LOCALS` where locals render as `[int, uninit, ref Dog]`,
followed by an `end:` line with the final state; a failing run ends with `error
at PC: <reason>`.

## Verification — `verify`

`verify --module F` runs abstract interpretation over each function's CFG to a
fixpoint and prints one line per function in source order: `NAME: verified` or
`NAME: rejected (<reason>)`.

The abstract state at a program point is the operand-stack types together with
the per-local types. The entry block starts from the entry state. The state
after a block flows to each successor; a block's entry state is the **join** of
the states arriving from all its predecessors, recomputed until no entry state
changes (a fixpoint, so loops and back-edges are accounted for). Blocks are
processed lowest-source-index first, and the first rejection reached in that
order is the one reported.

The **join** of two incoming states requires **equal operand-stack heights**
(otherwise `at L join: stack height mismatch (h1 vs h2)`); each stack slot is
combined with the type lub (an absent lub is `at L join: incompatible stack
types at slot i (A vs B)`). Each local slot is combined so that a slot is
carried forward as a concrete type only when it holds that type on **every**
incoming path: merging `uninit` with anything yields `uninit`, and merging two
different concrete types that have no lub also yields `uninit` — the slot becomes
unusable (definite assignment is an all-paths property). A `load N` of an
`uninit` local is rejected as `local N loaded before assignment`. Instruction type errors are
reported as `at L:PC OP: <reason>`.

## Dominators — `dom`

`dom --module F --func NAME` prints the immediate dominator of every block
reachable from the entry, in source order: `idom LABEL = PARENT`, and `idom
ENTRY = (root)` for the entry. Block `d` dominates block `n` when every path from
the entry to `n` passes through `d`; the immediate dominator is the closest such
`d` other than `n` itself. Only reachable blocks are listed.

## Execution — `run`, `trace`

`run --module F` executes `main` (which must take no parameters) and prints
`result: V` (an `int` as a decimal, a `bool` as `true`/`false`, a reference as
`ref NAME` or `null`, an array as `arr ELEM[len]`, `void` for a void return), or
`trap: <reason>` when execution faults (null field access, array bounds, a
negative array length). Arithmetic, comparison (`icmp`/`fcmp` are less-than),
branching, struct/array access and calls behave as their instructions describe;
a freshly allocated struct field or array element starts at its type's zero
(`0`, `0`, `false`, `null`, an empty array). `trace --module F` prints the same
run preceded by one line per executed instruction, `LABEL:PC OP`, before the
final `result:`/`trap:` line.

## Analysis — `analyze`

`analyze --module F` prints, per function: the reachable blocks, the dead
(unreachable) blocks (`(none)` if there are none), and `max_stack`, the greatest
operand-stack depth reached at any program point of any reachable block. Because
a block's entry stack height is inherited from its predecessors, the depth is
measured relative to each block's verified entry state and the maximum is taken
over every reachable block. `max_stack` is `n/a` for a function that does not
verify.

```
func NAME:
  reachable: b0, b1
  dead: b2
  max_stack: 3
```

## Report — `report`

`report --module F` prints a header `types: T  funcs: M`, then per function
`func NAME: verified blocks=B max_stack=S` (or `func NAME: rejected blocks=B`),
then `digest: 0xXXXXXXXX`, the 32-bit FNV-1a hash (offset basis `2166136261`,
prime `16777619`, one byte at a time, `^=` then `*=`, printed `0x` + eight
lowercase hex digits) of the report body (the lines above the digest joined by
newlines).

## Canonical text — `parse`, `disasm`

`disasm --module F` prints the canonical module text: type declarations sorted
by name (`type NAME`, `type NAME extends PARENT`, with ` { f: T, ... }` when the
struct has fields), then each function in source order — signature and ` {`, an
optional `  locals K` line when `K > 0`, then each block as `LABEL:` followed by
its instructions indented two spaces, closed by `}` — with no blank lines. This
round-trips through `parse`.

`parse --module F` prints `types: <names sorted, comma-separated>`, then one line
per function in source order `func NAME(params) -> RET : blocks=B locals=K`, then
`checksum: 0xXXXXXXXX`, the FNV-1a-32 hash (as above) of the canonical `disasm`
text.

## Batch — `batch`

`batch --manifest F` reads a JSON file `{ "op": "verify"|"run", "base": "<dir>",
"models": ["a.bvm", ...] }`. `op` defaults to `verify`; `base` (a directory that
model paths resolve against, relative to the manifest's own directory) defaults
to the manifest's directory. Each model is processed in order. For `verify` a
model prints `NAME: verified` when every function verifies, else `NAME:
rejected`. For `run` it prints `NAME: <result line>`. `NAME` is the model's base
file name without the `.bvm` suffix. After the per-model lines the command prints
`digest: 0xXXXXXXXX`, the FNV-1a-32 hash of the report lines joined by newlines.
