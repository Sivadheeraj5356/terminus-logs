A repository at `/app` implements `bvm`, a command-line tool that consumes textual
bytecode-module documents (the `.bvm` format) and produces structured analysis
documents on standard output. The complete data contract — the module text
grammar, the value-type lattice and its subtyping relation, every instruction's
stack effect and typing rule, and the exact output format of each subcommand — is
specified in `/app/docs/bvm-spec.md`. A corpus of input modules is provided under
`/app/data` for you to run the tool against and compare with the specification.

This milestone concerns five subcommands, each of which transforms one module into
a derived document: `parse` (the type list, per-function signatures and the
canonical checksum), `disasm` (the canonical module text), `cfg` (the
control-flow graph of a function), `opcheck` (the per-instruction operand-stack
transition of a function's entry block), and `stackmap` (the operand-stack and
locals state before each entry-block instruction).

For every input there is exactly one correct output document. On some inputs the
current output diverges from what the specification defines. Adjust the
implementation so that each of these five subcommands produces exactly the
specified output — byte for byte — for every module, then rebuild the binary with
`go build -o /app/bin/bvm ./cmd/bvm`.
