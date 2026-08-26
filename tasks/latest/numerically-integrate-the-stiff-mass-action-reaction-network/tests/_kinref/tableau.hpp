#pragma once

#include <string>

struct Tableau {
    double node[6];
    double a[6][6];
    double upper[6];
    double lower[6];
};

bool load_tableau(const std::string &path, Tableau &out, std::string &err);
