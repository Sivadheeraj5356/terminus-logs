# Governing rules

Moves and outcomes follow the complete standard rules of Chess960
(Fischer Random Chess), including all special moves and terminal
conditions: normal piece movement and capture, pawn double advance,
pawn promotion, en passant capture, castling under the Chess960 rule
described in fen_notation.md, and every rule that makes a pseudo-legal
move illegal, including leaving or moving into check.

A perft count at a given depth is the total number of leaf positions
reachable by exactly that many consecutive plies of strictly legal play
from the starting position, with every side to move choosing among all
of its own legal moves at every ply.
