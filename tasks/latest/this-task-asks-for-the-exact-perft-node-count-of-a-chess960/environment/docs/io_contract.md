# IO contract

The program reads a position file with exactly two lines of text.

Line 1: a Chess960 position in Extended FEN notation, as described in
fen_notation.md.

Line 2: a single non-negative integer, the perft search depth.

The default input path is /app/data/position.txt. When the environment
variable POSITION_PATH is set, read from that path instead.

The program writes a single JSON object as its entire output. The object has
exactly one field:

perft_nodes: a non-negative integer, the total count of legal move
sequences of exactly the requested depth from the given position, counted
by enumerating every leaf position reachable by that many consecutive
plies of strictly legal play.

The default output path is /app/output.json. When the environment variable
OUTPUT_PATH is set, write to that path instead. Create parent directories if
they do not already exist. Overwrite any existing file at the output path.

The program also prints the same integer to standard output on its own
line.

Performance

Every visible sample position stays within a shallow search depth over a
heavily populated board. The grader also checks a long-sliding endgame with
very few pieces left on the board, searched to a much greater depth than any
visible sample, where the same position is reachable through many different
orders of moves. The program must still finish well within the verifier
time limit on that position.
