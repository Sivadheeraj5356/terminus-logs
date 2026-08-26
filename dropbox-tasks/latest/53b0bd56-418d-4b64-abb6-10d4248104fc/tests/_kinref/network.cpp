#include "network.hpp"

#include <cstddef>

void derivative(const Network &net, const std::vector<double> &y, std::vector<double> &dy) {
    const std::size_t n = net.species.size();
    dy.assign(n, 0.0);
    for (std::size_t r = 0; r < net.reactions.size(); ++r) {
        const Reaction &rx = net.reactions[r];
        double flux = rx.rate;
        for (std::size_t i = 0; i < rx.reactants.size(); ++i) {
            flux *= y[rx.reactants[i]];
        }
        for (std::size_t i = 0; i < rx.reactants.size(); ++i) {
            dy[rx.reactants[i]] -= flux;
        }
        for (std::size_t i = 0; i < rx.products.size(); ++i) {
            dy[rx.products[i]] += flux;
        }
    }
}
