# giri board and move notation

## board.spec

Line-oriented. Blank lines and text following `#` on a line are ignored.

- `node <name>` declares an intersection. Names are non-whitespace tokens.
- `edge <a> <b>` declares an undirected edge between two previously declarable
  nodes. Duplicate edges are harmless; an edge to an unknown node, or a self edge,
  is invalid.

## move logs

Each `*.log` file is one recorded game. Blank lines and `#` comments are ignored.
Every other line is exactly one token:

- an intersection name, meaning the moving color plays there, or
- `pass`.

Colors alternate strictly, black playing the first recorded move. A line that is not
`pass` and not a declared intersection, or a line carrying more than one token, makes
the whole log malformed. A malformed log is a hard error and is not replayed.

Illegality of a move (occupied, suicide, superko) is a matter of the rules in
RULES.md and is not a notation error: such a log is well-formed and is replayed up to
the offending move.
