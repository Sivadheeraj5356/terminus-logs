#include "systems.hpp"

#include <cstddef>

namespace {

struct Spec {
    const char *name;
    const char *species[8];
    double initial[8];
    struct RxSpec {
        int reactants[2];
        int products[2];
        double rate;
    } reactions[10];
    int n_species;
    int n_reactions;
    double t0;
    double t1;
    double rtol;
    double atol;
};

const Spec SPECS[] = {
    {"ring_isomerase",
     {"A", "B", "C"},
     {1.0, 0.0, 0.0},
     {{{0, -1}, {1, -1}, 0.8},
      {{1, -1}, {2, -1}, 1.3},
      {{2, -1}, {0, -1}, 0.5}},
     3, 3, 0.0, 20.0, 1.0e-6, 1.0e-9},

    {"autocat_dimer",
     {"A", "B", "C"},
     {1.0, 0.0, 0.0},
     {{{0, -1}, {1, -1}, 0.04},
      {{1, 1}, {2, 1}, 30000000.0},
      {{1, 2}, {0, 2}, 10000.0}},
     3, 3, 0.0, 40.0, 1.0e-6, 1.0e-9},

    {"michaelis_relay",
     {"S", "E", "P", "F"},
     {1.0, 0.2, 0.0, 0.0},
     {{{0, 1}, {2, 1}, 12.0},
      {{2, 1}, {0, 1}, 0.4},
      {{1, -1}, {3, -1}, 0.05},
      {{3, -1}, {1, -1}, 0.02}},
     4, 4, 0.0, 8.0, 1.0e-6, 1.0e-9},

    {"proton_shuttle",
     {"H", "M", "N", "Q"},
     {0.9, 0.1, 0.0, 0.0},
     {{{0, 1}, {2, 1}, 220.0},
      {{2, -1}, {3, -1}, 3.5},
      {{3, 1}, {0, 1}, 45.0},
      {{1, -1}, {2, -1}, 0.6}},
     4, 4, 0.0, 6.0, 1.0e-7, 1.0e-10},

    {"redox_couple",
     {"X", "Y", "Z"},
     {0.7, 0.3, 0.0},
     {{{0, 1}, {1, 2}, 5200.0},
      {{2, -1}, {0, -1}, 1.8},
      {{1, -1}, {2, -1}, 0.9}},
     3, 3, 0.0, 10.0, 1.0e-6, 1.0e-9},

    {"catalytic_cycle",
     {"A", "K", "B", "C"},
     {1.0, 0.05, 0.0, 0.0},
     {{{0, 1}, {2, 1}, 90.0},
      {{2, 1}, {3, 1}, 40.0},
      {{3, -1}, {0, -1}, 0.25},
      {{1, -1}, {3, -1}, 0.01}},
     4, 4, 0.0, 15.0, 1.0e-6, 1.0e-9},

    {"ligand_exchange",
     {"L", "R", "S", "T", "U"},
     {0.6, 0.4, 0.0, 0.0, 0.0},
     {{{0, 1}, {2, 3}, 65.0},
      {{2, -1}, {3, -1}, 7.0},
      {{3, 4}, {0, 4}, 130.0},
      {{4, -1}, {1, -1}, 0.35},
      {{1, -1}, {4, -1}, 0.8}},
     5, 5, 0.0, 9.0, 1.0e-7, 1.0e-10},

    {"radical_pair",
     {"R", "P", "D"},
     {1.0, 0.0, 0.0},
     {{{0, -1}, {1, -1}, 0.02},
      {{1, 1}, {2, 1}, 80000000.0},
      {{1, 2}, {0, 2}, 25000.0}},
     3, 3, 0.0, 5.0, 1.0e-7, 1.0e-10},

    {"chain_transfer",
     {"M", "G", "H", "J"},
     {0.5, 0.5, 0.0, 0.0},
     {{{0, 1}, {2, 3}, 18.0},
      {{2, -1}, {0, -1}, 2.2},
      {{3, -1}, {1, -1}, 1.1},
      {{2, 3}, {0, 1}, 6.0}},
     4, 4, 0.0, 25.0, 1.0e-6, 1.0e-9},

    {"phase_swap",
     {"U", "V", "W"},
     {0.8, 0.2, 0.0},
     {{{0, -1}, {1, -1}, 3.0},
      {{1, -1}, {2, -1}, 150.0},
      {{2, -1}, {0, -1}, 0.4},
      {{0, 2}, {1, 2}, 22.0}},
     3, 4, 0.0, 18.0, 1.0e-6, 1.0e-9},

    {"substrate_sink",
     {"A", "B", "C", "D", "E"},
     {1.0, 0.0, 0.0, 0.0, 0.0},
     {{{0, -1}, {1, -1}, 1.5},
      {{1, -1}, {2, -1}, 0.7},
      {{2, -1}, {3, -1}, 0.3},
      {{3, -1}, {4, -1}, 0.12},
      {{4, -1}, {0, -1}, 0.05}},
     5, 5, 0.0, 30.0, 1.0e-8, 1.0e-11},

    {"enzyme_ladder",
     {"S", "E", "F", "G", "P", "Q"},
     {1.0, 0.3, 0.0, 0.0, 0.0, 0.0},
     {{{0, 1}, {4, 1}, 260.0},
      {{1, -1}, {2, -1}, 4.0},
      {{2, -1}, {3, -1}, 1.6},
      {{3, -1}, {1, -1}, 0.9},
      {{4, 2}, {5, 2}, 55.0},
      {{5, -1}, {0, -1}, 0.6}},
     6, 6, 0.0, 14.0, 1.0e-7, 1.0e-10}};

const int SPEC_COUNT = static_cast<int>(sizeof(SPECS) / sizeof(SPECS[0]));

}  // namespace

std::vector<std::string> calibration_names() {
    std::vector<std::string> out;
    for (int i = 0; i < SPEC_COUNT; ++i) out.push_back(SPECS[i].name);
    return out;
}

bool calibration_network(const std::string &name, Network &out) {
    for (int i = 0; i < SPEC_COUNT; ++i) {
        const Spec &s = SPECS[i];
        if (name != s.name) continue;
        out.name = s.name;
        out.species.clear();
        out.reactions.clear();
        out.initial.clear();
        for (int j = 0; j < s.n_species; ++j) {
            out.species.push_back(s.species[j]);
            out.initial.push_back(s.initial[j]);
        }
        for (int j = 0; j < s.n_reactions; ++j) {
            Reaction rx;
            rx.rate = s.reactions[j].rate;
            for (int c = 0; c < 2; ++c) {
                if (s.reactions[j].reactants[c] >= 0) rx.reactants.push_back(s.reactions[j].reactants[c]);
                if (s.reactions[j].products[c] >= 0) rx.products.push_back(s.reactions[j].products[c]);
            }
            out.reactions.push_back(rx);
        }
        out.t0 = s.t0;
        out.t1 = s.t1;
        out.rtol = s.rtol;
        out.atol = s.atol;
        return true;
    }
    return false;
}
