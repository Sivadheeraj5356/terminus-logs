#pragma once

#include <string>
#include <vector>

#include "network.hpp"

std::vector<std::string> calibration_names();
bool calibration_network(const std::string &name, Network &out);
