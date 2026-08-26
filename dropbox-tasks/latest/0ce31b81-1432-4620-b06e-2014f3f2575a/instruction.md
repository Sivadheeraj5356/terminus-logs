This task asks for the exact perft node count of a Chess960 (Fischer Random
Chess) position, where the castling rule's king/rook overlap cases are the
central difficulty.

A perft count at a given depth is the total number of leaf positions
reachable by exactly that many consecutive plies of strictly legal play from
a starting position, with every side to move choosing among all of its own
legal moves at every ply.

The full standard rules of chess govern movement and outcomes: normal piece
movement and capture, pawn double advance, promotion, en passant, and every
condition that turns a pseudo-legal move into an illegal one, including
leaving or moving into check. Castling follows the Chess960 rule: the king
always ends the move on the c-file (queenside) or the g-file (kingside) of
its own rank, and the castling rook always ends on the d-file or the f-file
of that same rank, regardless of which files the king and that rook started
on. Because the king and rook can start on any files, their start and end
squares may coincide or cross over one another mid-move, and castling stays
legal only when every square the king passes through or lands on is either
empty or occupied solely by the castling rook itself, and never attacked
while the king transits it.

The exact value for each position has to come from working out this rule
set directly, not from an existing chess engine, move-generation library, or
any precomputed table of positions or answers.

Build with make from /app, producing a binary at /app/build/chess960_perft.
Run it with no arguments. It reads a position file with two lines - an
Extended FEN position on the first line and the perft depth on the second -
from /app/data/position.txt by default, or from the path given by the
POSITION_PATH environment variable when that is set.

The program writes a single JSON object as its entire output to
/app/output.json by default, or to the path given by the OUTPUT_PATH
environment variable when that is set, creating parent directories if
needed and overwriting any existing file there. The object has exactly one
field, perft_nodes, a non-negative integer giving the exact perft count.
The program also prints that same integer to standard output on its own
line.
