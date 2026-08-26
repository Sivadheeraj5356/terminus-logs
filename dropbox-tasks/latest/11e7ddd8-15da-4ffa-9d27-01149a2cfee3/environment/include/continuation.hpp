#ifndef CONTINUATION_HPP
#define CONTINUATION_HPP

#include <string>
#include <vector>

// Number of interior grid nodes in the discretised boundary-value problem.
const int kNodes = 15;

struct CurvePoint {
    double lambda;
    std::vector<double> u;  // kNodes entries; u[i] is the value at node i+1
};

// Returns the point of the traced branch at each requested arclength, in the
// order the arclengths are given. `problem` is "bratu" or "cubic"; `k` selects
// the branch for "cubic" and is 0 for "bratu".
std::vector<CurvePoint> trace_branch(const std::string &problem, int k,
                                     const std::vector<double> &arclengths);

#endif
