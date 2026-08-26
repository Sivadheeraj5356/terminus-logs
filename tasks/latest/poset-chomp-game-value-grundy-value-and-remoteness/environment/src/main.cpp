#include <iostream>

#include "chomp.hpp"

// Reads one poset-Chomp position in the disclosed format and prints "V C G R".
// Parsing here only tokenizes the compact description (element count, cover
// count, then the cover edges). Building the order closure, generating moves,
// and computing the value/count/Grundy/remoteness are up to solve().
int main() {
    PosetPosition pos;
    int m = 0;
    if (!(std::cin >> pos.n >> m)) {
        return 0;
    }
    for (int e = 0; e < m; ++e) {
        int a = 0, b = 0;
        if (!(std::cin >> a >> b)) return 0;
        pos.covers.emplace_back(a, b);
    }
    std::cout << solve(pos) << "\n";
    return 0;
}
