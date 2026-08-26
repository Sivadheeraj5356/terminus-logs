#pragma once

#include "model.hpp"

#include <vector>

std::vector<long double> find_limit_thetas(const Model& model);
std::vector<long double> equilibria_at(const Model& model, long double load);
std::vector<LimitPoint> limit_points(const Model& model);
std::vector<SweepState> run_sweep(const Model& model, const Sweep& sweep);
mj::Value build_report(const Campaign& campaign);
