#pragma once

#include "lockcore/types.hpp"

namespace lockcore {

double applyFlowCap(double q, double maximum_abs_flow_m3_s);

// Bidirectional orifice-style gate law. Positive flow is from `h_from`
// toward `h_to`.
double gateFlow(double h_from, double h_to, double control, double discharge_coefficient, double area_m2,
                 double gravity_m_s2, double maximum_abs_flow_m3_s);

// Submerged broad-crested weir law. Never negative.
double weirFlow(double h_from, double h_to, double control, double discharge_coefficient, double width_m,
                 double crest_level_m, double maximum_abs_flow_m3_s);

// Controlled pump. Nonnegative from `from_node` to `to_node`.
double pumpFlow(double control, double maximum_abs_flow_m3_s);

double linkFlow(const LinkSpec& link, double h_from, double h_to, double control, double gravity_m_s2);

}  // namespace lockcore
