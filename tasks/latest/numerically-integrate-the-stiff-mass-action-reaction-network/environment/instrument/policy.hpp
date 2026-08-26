#pragma once

#include <string>
#include <vector>

#include "network.hpp"
#include "tableau.hpp"

struct StepRecord {
    long index;
    double t;
    double h;
    int accepted;
};

struct RunResult {
    std::string verdict;
    double stop_time = 0.0;
    long accepted = 0;
    long rejected = 0;
    long derivative_evals = 0;
    std::vector<double> final_state;
    std::vector<StepRecord> trace;
};

RunResult integrate(const Network &net, const Tableau &tab, bool keep_trace);
