#ifndef CHOMP_HPP
#define CHOMP_HPP

#include <string>
#include <utility>
#include <vector>

// One poset-Chomp position, as read from stdin in the disclosed form.
//
//   n       : number of poset elements, labelled 0 .. n-1. Element 0 is the
//             poison and is the unique minimal element (it lies below every
//             other element under the order).
//   covers  : the Hasse (covering) relation. Each pair {a, b} means a < b is a
//             covering relation (a is immediately below b). The full order is
//             the reflexive-transitive closure of these covers.
//
// The graded position is the full poset: every element is initially present.
// A move eats a non-poison element x and removes the whole up-set
// {y : y >= x}. The player forced to eat the poison loses.
struct PosetPosition {
    int n;
    std::vector<std::pair<int, int>> covers;
};

// Return the answer line "V C G R":
//   V : 'N' or 'P', the game value under the normal poison-loss convention;
//   C : the number of winning first moves (non-poison moves to a P-position);
//   G : the Sprague-Grundy value of the position;
//   R : the remoteness (game length under optimal play).
std::string solve(const PosetPosition &pos);

#endif  // CHOMP_HPP
