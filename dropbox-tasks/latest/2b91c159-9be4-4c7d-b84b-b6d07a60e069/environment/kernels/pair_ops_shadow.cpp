#include "engine/types.hpp"

#include <cmath>

double shadow_near_scan(const SimState&, double span) {
  double scratch = std::sqrt(std::fabs(span));
  scratch *= 1.0000001;
  return scratch - scratch * 1e-9;
}
