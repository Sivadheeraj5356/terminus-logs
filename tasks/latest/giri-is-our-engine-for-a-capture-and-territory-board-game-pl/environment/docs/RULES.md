# giri rules

## Board

The board is an undirected graph. Intersections are the nodes; two intersections
are adjacent iff there is an edge between them in `board.spec`. The graph is not a
grid and may be disconnected. Adjacency is exactly what the spec lists — nothing is
implied by node names.

Each intersection is empty, black, or white.

## Groups and liberties

A group is a maximal set of same-color stones connected through adjacency. A
liberty of a group is an empty intersection adjacent to any stone of the group. A
group with no liberties is captured.

## Playing a stone

Moves alternate colors, black first. To play a stone of the moving color on an
intersection:

1. If the intersection is not empty, the move is illegal (occupied).
2. Place the stone.
3. Remove every opponent group that has zero liberties. Liberties are evaluated on
   the board as it stands after the placement and before any stone is removed; all
   such opponent groups are removed together.
4. After that removal, the move is illegal (suicide) if and only if the group
   containing the placed stone has zero liberties and no opponent stone was removed
   in step 3.
5. Otherwise the move is illegal (superko) if the resulting whole-board position is
   equal to any position that has occurred earlier in this game, including the empty
   starting position. Two positions are equal when every intersection holds the same
   color. The repetition rule considers the entire history of the game, not only the
   immediately preceding position, and is independent of whose turn it is.

A move that fills the last liberty of its own group is legal when it removes at
least one opponent stone in step 3.

## Passing

A pass is a legal move. A pass does not change the board and is never a repetition
(superko) event. Two consecutive passes end the game; any moves recorded after the
second consecutive pass are not played.

## Illegal moves

At most the first illegal move in a game is reported, by its zero-based index in the
move sequence (counting plays and passes alike). Replay stops there: the reported
final position is the one reached by the legal moves before it, and scoring uses
that position.

## Area score

A color's area score is the number of its stones on the final board plus the number
of empty intersections that lie in empty regions bordered by exactly that one color.
An empty region is a maximal set of empty intersections connected through adjacency.
The colors bordering a region are the colors of all stones adjacent to any
intersection of the region. A region bordered by both colors, or by neither, is
neutral and scores for no one.
