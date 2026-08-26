#pragma once

#include "mini_json.hpp"

#include <string>
#include <vector>

struct Stop {
    std::string sense;
    long double angle = 0;
    long double stiffness = 0;
};

struct Model {
    long double a1 = 0;
    long double a3 = 0;
    long double a5 = 0;
    long double b1 = 0;
    long double b3 = 0;
    long double theta_min = 0;
    long double theta_max = 0;
    std::vector<Stop> stops;
};

struct Sweep {
    std::string id;
    std::vector<long double> loads;
    long double initial_theta = 0;
};

struct Campaign {
    std::string campaign;
    Model model;
    std::vector<long double> equilibrium_loads;
    std::vector<Sweep> sweeps;
};

struct EqState {
    long double theta = 0;
    long double energy = 0;
    long double tangent_left = 0;
    long double tangent_right = 0;
    std::string stability;
    std::vector<int> active_stops;
};

struct LimitPoint {
    long double theta = 0;
    long double load = 0;
    std::string type;
    std::vector<int> active_stops;
};

struct SweepState {
    long double load = 0;
    long double theta = 0;
    long double energy = 0;
    std::string transition;
};

Campaign parse_campaign(const mj::Value& root);
long double force(const Model& model, long double theta, int side = 0);
long double drive(const Model& model, long double theta);
long double load_curve(const Model& model, long double theta, int side = 0);
long double tangent(const Model& model, long double theta, long double load, int side = 0);
long double energy(const Model& model, long double theta, long double load);
std::vector<int> active_stop_indices(const Model& model, long double theta, int side = 0);
std::string stability_of(const Model& model, long double theta, long double load);
