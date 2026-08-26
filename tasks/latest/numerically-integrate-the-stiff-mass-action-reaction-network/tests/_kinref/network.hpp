#pragma once

#include <string>
#include <vector>

struct Reaction {
    std::vector<int> reactants;
    std::vector<int> products;
    double rate;
};

struct Network {
    std::string name;
    std::vector<std::string> species;
    std::vector<Reaction> reactions;
    std::vector<double> initial;
    double t0 = 0.0;
    double t1 = 0.0;
    double rtol = 1.0e-6;
    double atol = 1.0e-9;
};

void derivative(const Network &net, const std::vector<double> &y, std::vector<double> &dy);
