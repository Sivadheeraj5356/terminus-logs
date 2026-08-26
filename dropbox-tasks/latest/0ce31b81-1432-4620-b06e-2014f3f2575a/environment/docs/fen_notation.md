# Chess960 position notation

A position is written as a single line with six space separated fields,
in the same order as standard Forsyth-Edwards Notation.

Field 1: piece placement, one rank per slash separated group, from rank 8
down to rank 1. Within a rank, a letter is a piece (P N B R Q K for white,
p n b r q k for black) and a digit is that many consecutive empty squares.

Field 2: side to move, "w" or "b".

Field 3: castling rights, written as the file letter of each rook that
still has its right to castle. Uppercase letters name white's rooks,
lowercase letters name black's rooks. The letter is the file the rook
currently stands on (a through h), not a fixed kingside or queenside
symbol. A single "-" means neither side has any castling right.

Field 4: the en passant target square in algebraic notation (for example
e3), or "-" if none.

Field 5: the halfmove clock.

Field 6: the fullmove number.

Castling itself follows the standard Chess960 rule: the king always ends
the move on the c-file (queenside) or the g-file (kingside) of its own
rank, and the castling rook always ends the move on the d-file
(queenside) or the f-file (kingside) of its own rank, regardless of which
files the king and that rook started on.
