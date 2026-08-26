#pragma once

#include <string>
#include "network.hpp"

// Reader for the .net reaction-network files. Deliberately absent from the
// bench instrument, which knows only its compiled-in calibration systems.
bool load_network(const std::string &path, Network &out, std::string &err);
