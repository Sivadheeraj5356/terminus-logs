# Poset Chomp: game value, Grundy value, and remoteness

Chomp is played on the order ideals of a finite partially ordered set (poset).
For one position you must report four exact quantities under the **normal
poison-loss** convention: the game value, the number of winning first moves, the
Sprague-Grundy value, and the remoteness (optimal game length). Complete the C++
program in `src/` so that `make` builds `./chomp`; it reads one position from
stdin and writes a single line `V C G R` to stdout.

## The poset and the poison

Elements are labelled `0 .. n-1`. The order is the reflexive-transitive closure
of the given **cover** relations: a pair `a b` means `a < b` is a covering
relation (`a` immediately below `b`). Element `0` is the **poison**; it is the
unique minimal element, so `0 < x` for every other element `x`.

A **position** is a down-closed ideal: a set `S` of still-present elements such
that if `y in S` and `x <= y` then `x in S`. The graded position is the full
poset (every element present). The poison belongs to every non-empty ideal.

## Moves and terminal rule

A move eats a **non-poison** element `x` that is present and removes its entire
up-set `{y : y >= x}` from the ideal. The result is again a down-closed ideal.
Eating the poison is not a game move: the player who is forced to eat the poison
**loses**. So the ideal consisting of only the poison is terminal — the player
to move there has no legal move and loses.

## The four quantities

Let the children of a position `S` be the ideals reachable by one non-poison
move.

- **Sprague-Grundy value** `G`: `G(S) = mex { G(child) }`, the least
  non-negative integer that is not the Grundy value of any child. The
  poison-only ideal has `G = mex{} = 0`.
- **Game value** `V`: `N` if `G > 0`, otherwise `P`.
- **Winning-move count** `C`: the number of non-poison moves from the graded
  position whose child is a **P**-position (a child with `G = 0`). For a
  P-position `C = 0`.
- **Remoteness** `R` (optimal game length): the poison-only ideal has `R = 0`.
  Otherwise, if some child has **even** remoteness then
  `R = 1 + min{ R(child) : R(child) even }`; if every child has odd remoteness
  then `R = 1 + max{ R(child) : R(child) odd }`. The winner ends the game as
  quickly as possible; the loser stalls as long as possible. Consequently `R`
  is odd exactly for N-positions and even exactly for P-positions.

## Input (stdin)

- Line 1: two integers `n m` — the number of elements (`2 <= n <= 127`) and the
  number of cover relations `m`.
- The next `m` lines: each is `a b`, a covering relation with `a` immediately
  below `b` (`0 <= a, b < n`). The label written first is the lower element; the
  two labels are not necessarily in numeric order. The covers describe a valid
  poset whose unique minimal element is `0`.

## Output (stdout)

One line: `V C G R`, where `V` is `N` or `P` and `C`, `G`, `R` are base-10
non-negative integers.

## Examples

- `example_1`: input `5 4` / `0 1` / `0 2` / `0 3` / `0 4` (four elements, each
  directly above the poison, mutually incomparable) prints `P 0 0 4`.
- `example_2`: input `2 1` / `0 1` (one element above the poison) prints
  `N 1 1 1`.

## Build and run

Every `src/*.cpp` is built into `./chomp`, which prints the `V C G R` line for
the position it is given. It must answer correctly within the time limit for
every graded position; a position has up to `127` elements. Do not consult an
external game-solving engine or a precomputed answer table — each answer is
checked only against an independent solver run on fresh positions.
