#include "chomp.hpp"

// Starter stub: it does not compute the game value, winning-move count, Grundy
// value, or remoteness.
//
// Replace this with a real solver. You need to:
//   1. build the order closure from the covers (so that up-set(x) = {y : y>=x}
//      is available for every element);
//   2. represent a down-closed ideal as the set of elements still present and
//      generate successors by removing the up-set of a chosen non-poison cell;
//   3. run a memoized retrograde over the reachable ideals with the poison-loss
//      base case (the poison-only ideal is terminal: value P, Grundy 0,
//      remoteness 0);
//   4. from the full poset report V (N iff Grundy > 0), C (non-poison moves
//      whose child is a P-position), G (the mex of the children's Grundy
//      values), and R (the remoteness under optimal play).
//
// The returned line must be exactly "V C G R" as described in instruction.md.
std::string solve(const PosetPosition &pos) {
    (void)pos;
    return "P 0 0 0";
}
