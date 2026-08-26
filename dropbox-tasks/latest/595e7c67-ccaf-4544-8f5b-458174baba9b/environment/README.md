# fpfold

fpfold is a constant folder for a tiny floating-point expression language. It
reads one expression, evaluates the parts that are already constant, removes
operands that cannot change the result, and prints the reduced expression.

The language and the folding contract are described in `docs/grammar.md` and
`docs/semantics.md`. Read those before changing anything.

Build the tool with `./build.sh`, which compiles the sources under `src/` into
`/app/foldc`. Run it on a program file, for example `./foldc programs/sample1.fp`,
and it writes the folded expression on one line.

Example programs and their expected folded output are under `programs/`. The
sources under `src/` are a lexer, a recursive-descent parser, the folder, and a
canonical printer.
