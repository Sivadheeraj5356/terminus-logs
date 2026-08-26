#pragma once

#include "pam_lab/modules.hpp"

#include <vector>

namespace pam_lab {

std::vector<Event> gather_attempt_staging(const std::vector<Effect>& effects);
std::vector<Event> gather_success_staging(const std::vector<Effect>& effects);

}  // namespace pam_lab
