#include "netfile.hpp"

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <vector>

namespace {

int species_index(const Network &net, const std::string &name) {
    for (std::size_t i = 0; i < net.species.size(); ++i) {
        if (net.species[i] == name) return (int)i;
    }
    return -1;
}

// "A + B" -> [idx(A), idx(B)]
bool parse_side(const Network &net, const std::string &text, std::vector<int> &out, std::string &err) {
    std::istringstream iss(text);
    std::string tok;
    bool expect_species = true;
    while (iss >> tok) {
        if (tok == "+") {
            if (expect_species) { err = "malformed reaction side: " + text; return false; }
            expect_species = true;
            continue;
        }
        if (!expect_species) { err = "malformed reaction side: " + text; return false; }
        int idx = species_index(net, tok);
        if (idx < 0) { err = "unknown species in reaction: " + tok; return false; }
        out.push_back(idx);
        expect_species = false;
    }
    if (out.empty() || expect_species) { err = "malformed reaction side: " + text; return false; }
    return true;
}

}  // namespace

bool load_network(const std::string &path, Network &out, std::string &err) {
    std::ifstream in(path);
    if (!in) { err = "cannot open network file: " + path; return false; }

    out = Network();
    std::vector<std::pair<std::string, std::pair<double, std::string> > > pending;
    std::string line;
    bool have_horizon = false;

    while (std::getline(in, line)) {
        if (line.empty()) continue;
        std::istringstream iss(line);
        std::string key;
        iss >> key;

        if (key == "network") {
            iss >> out.name;
        } else if (key == "species") {
            std::string s;
            while (iss >> s) out.species.push_back(s);
            out.initial.assign(out.species.size(), 0.0);
        } else if (key == "initial") {
            std::string s;
            double v = 0.0;
            iss >> s >> v;
            int idx = species_index(out, s);
            if (idx < 0) { err = "initial names an unknown species: " + s; return false; }
            out.initial[idx] = v;
        } else if (key == "reaction") {
            double rate = 0.0;
            iss >> rate;
            std::string rest;
            std::getline(iss, rest);
            std::size_t arrow = rest.find("->");
            if (arrow == std::string::npos) { err = "reaction lacks an arrow: " + rest; return false; }
            Reaction rx;
            rx.rate = rate;
            if (!parse_side(out, rest.substr(0, arrow), rx.reactants, err)) return false;
            if (!parse_side(out, rest.substr(arrow + 2), rx.products, err)) return false;
            out.reactions.push_back(rx);
        } else if (key == "horizon") {
            iss >> out.t0 >> out.t1;
            have_horizon = true;
        } else if (key == "rtol") {
            iss >> out.rtol;
        } else if (key == "atol") {
            iss >> out.atol;
        }
    }

    if (out.species.empty()) { err = "network declares no species: " + path; return false; }
    if (out.reactions.empty()) { err = "network declares no reactions: " + path; return false; }
    if (!have_horizon) { err = "network declares no horizon: " + path; return false; }
    return true;
}
