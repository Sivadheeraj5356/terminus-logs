#pragma once

#include "metrics/types.hpp"

#include <vector>

namespace tone {

std::vector<std::optional<double>> reconstruct_timeline(const ScenarioSpec& spec);

}  // namespace tone
